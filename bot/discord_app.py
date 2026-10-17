"""Torch on Discord: slash commands into the GameService, a loop that advances the game and delivers its outbox.

    python -m bot.discord_app

Every player-facing reply is ephemeral (only the player sees it). The game's clock runs on real time; a GM picks
the length of a day when starting (5 minutes for pilots). News goes to #news, radio to #radio, results by DM with
/results as the fallback when DMs are closed.
"""
import asyncio
import io
import json
import datetime
import logging
import os
import random
import time

import discord
from discord import app_commands

from . import config as cfg
from . import hall
from .game import GameError, GameService
from .store import IdentityStore, JsonlEventStore, TextStore

log = logging.getLogger("torch.discord")
NONE = discord.AllowedMentions.none()


class Torch(discord.Client):
    def __init__(self, conf):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.conf = conf
        self.tree = app_commands.CommandTree(self)
        self.lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()   # one delivery at a time, or two callers send the same message twice
        self.game = self.open_season()
        self.channels = {}
        register(self)

    # ---------------- seasons ----------------
    def open_season(self):
        d = self.conf.data_dir
        os.makedirs(d, exist_ok=True)
        season = open(os.path.join(d, "season_id.txt")).read().strip() if os.path.exists(os.path.join(d, "season_id.txt")) \
            else self._new_season_id()
        return GameService(self.conf.rules, JsonlEventStore(os.path.join(d, "season.jsonl")),
                           IdentityStore(os.path.join(d, "identity.json")), TextStore(os.path.join(d, "texts.json")),
                           self.conf.aliases, season, avoid_aliases=self._last_season_aliases())

    def _last_season_aliases(self):
        """Aliases used in the newest archived season, so nobody is handed last game's name (it looks like their own)."""
        import glob
        import json
        newest = sorted(glob.glob(os.path.join(self.conf.data_dir, "archive-*", "identity.json")))
        try:
            return {v["alias"] for v in json.load(open(newest[-1], encoding="utf-8")).values()} if newest else set()
        except (OSError, ValueError, KeyError):
            return set()

    def _new_season_id(self):
        sid = datetime.datetime.now().strftime("season-%Y%m%d-%H%M%S")
        with open(os.path.join(self.conf.data_dir, "season_id.txt"), "w") as f:
            f.write(sid)
        return sid

    def archive_and_reset(self):
        d = self.conf.data_dir
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        arch = os.path.join(d, f"archive-{stamp}")
        os.makedirs(arch)
        for name in ("season.jsonl", "identity.json", "texts.json", "season_id.txt"):
            if os.path.exists(os.path.join(d, name)):
                os.replace(os.path.join(d, name), os.path.join(arch, name))
        self._new_season_id()
        self.game = self.open_season()
        log.info("new season; old one archived in %s", arch)

    # ---------------- lifecycle ----------------
    async def setup_hook(self):
        guild = discord.Object(id=self.conf.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.add_view(BoardView(self))           # the board's buttons keep working across restarts
        self.loop.create_task(self.heartbeat())

    async def on_ready(self):
        guild = self.get_guild(self.conf.guild_id)
        cat = next((c for c in guild.categories if c.name.lower() == self.conf.category.lower()), None)
        if not cat:
            raise SystemExit(f"category {self.conf.category} not found; run bot/tools/setup_channels.py --apply")
        self.channels = {c.name: c for c in cat.text_channels}
        missing = {"news", "radio", "town-square"} - set(self.channels)
        if missing:
            raise SystemExit(f"missing channels: {missing}")
        log.info("ready as %s in %s; season %s, started=%s, night=%d", self.user, guild.name,
                 self.game.season_id, self.game.started, self.game.night)

    async def on_guild_join(self, guild):
        if guild.id != self.conf.guild_id:
            log.warning("invited to another server (%s); leaving", guild.id)
            await guild.leave()

    async def heartbeat(self):
        await self.wait_until_ready()
        while not self.channels and not self.is_closed():     # on_ready finds #news/#radio; nothing sends before
            await asyncio.sleep(1)
        while not self.is_closed():
            try:
                async with self.lock:
                    self.game.tick(time.time())
                await self.deliver()
                await self.refresh_board()
            except Exception:
                log.exception("heartbeat failed")
            await asyncio.sleep(5)

    async def refresh_board(self):
        """Keep one live status board at the bottom of #news: when its content changes (start, each night's news,
        the end), delete the old one and post a fresh one, pinned when Torch may pin. Runs after the outbox, so the
        board always sits under the latest news."""
        async with self.lock:
            b = self.game.board()
        if b is None:
            return
        key, text = b
        path = os.path.join(self.conf.data_dir, "board.json")
        try:
            state = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if state.get("key") == list(key) or self.game.pending_outbox():
            return                                    # unchanged, or news still going out
        ch = self.channels["news"]
        msg = None
        if state.get("message_id"):                   # owner, 17 Oct 2026: no repost spam. One pinned board, edited
            try:                                      # in place (an edit makes no sound and no "pinned" notice)
                msg = await ch.fetch_message(int(state["message_id"]))
                await msg.edit(content=text, view=BoardView(self), allowed_mentions=NONE)
            except discord.HTTPException:
                msg = None                            # deleted by hand: post a new one below
        if msg is None:
            msg = await ch.send(text, view=BoardView(self), allowed_mentions=NONE, silent=True)
            try:
                await msg.pin(reason="Torch status board")
            except discord.HTTPException:
                pass                                  # no pin rights: it still works, just unpinned
        if not msg.pinned:
            try:
                await msg.pin(reason="Torch status board")
            except discord.HTTPException:
                pass
        json.dump({"key": list(key), "message_id": str(msg.id)}, open(path, "w", encoding="utf-8"))

    async def deliver(self):
        async with self.send_lock:
            await self._deliver()

    async def _deliver(self):
        radio = []                                    # owner: one radio post per round, silent, not a ping per line
        for intent in self.game.pending_outbox():
            text = self.game.outbox_text(intent)
            to = intent["to"]
            if to == "radio":
                radio.append((intent, text))
                continue
            try:
                if to == "news" and intent.get("image") == "reveal" and (pic := self.reveal_picture()):
                    head = text.split("\n\n**The reveal**")[0]
                    msg = await self.channels[to].send(head[:1990], file=discord.File(pic, "reveal.png"),
                                                       allowed_mentions=NONE)
                    ref = str(msg.id)
                elif to in ("news", "radio"):
                    body = text if to == "news" else f"📻 *Anonymous on the radio:* {discord.utils.escape_markdown(text)}"
                    msg = await self.channels[to].send(body[:1990], allowed_mentions=NONE)
                    ref = str(msg.id)
                elif to.startswith("dm:"):
                    key = self.game.identity.key_for(int(to[3:]))
                    try:
                        user = await self.fetch_user(int(key))
                        msg = await user.send(text[:1990], allowed_mentions=NONE)
                        ref = str(msg.id)
                    except discord.Forbidden:
                        ref = "dm_closed"          # /results shows the same lines
                else:
                    ref = "unknown_target"
                async with self.lock:
                    self.game.mark_sent(intent["id"], ref)
            except discord.HTTPException:
                log.exception("sending %s failed; will retry", intent["id"])
                return
        if radio:
            lines = [f"- {discord.utils.escape_markdown(t)}" for _, t in radio]
            chunks, cur = [], "📻 **On the radio last night** (anonymous)"
            for line in lines:                       # stay under Discord's 2000-character limit
                if len(cur) + len(line) + 1 > 1990:
                    chunks.append(cur)
                    cur = "📻 *(more)*"
                cur += "\n" + line
            chunks.append(cur)
            try:
                ref = None
                for chunk in chunks:
                    msg = await self.channels["radio"].send(chunk, allowed_mentions=NONE, silent=True)
                    ref = ref or str(msg.id)
                async with self.lock:
                    for intent, _ in radio:
                        self.game.mark_sent(intent["id"], ref)
            except discord.HTTPException:
                log.exception("sending the radio bundle failed; will retry")

    def reveal_picture(self):
        """The reveal table as PNG bytes, or None (then the text reveal goes out instead: it must never go missing)."""
        try:
            import io
            from .reveal_image import render
            rows, winners = self.game.reveal_data()
            return io.BytesIO(render(rows, winners))
        except Exception:
            log.exception("reveal picture failed; posting the text reveal")
            return None

    def is_gm(self, interaction):
        return interaction.user.id in self.conf.gm_ids or interaction.user.id == interaction.guild.owner_id


async def private(interaction, text):
    """The only way Torch answers a player: ephemeral, so nobody else sees who did what."""
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True, allowed_mentions=NONE)
    else:
        await interaction.response.send_message(text, ephemeral=True, allowed_mentions=NONE)


BUTTONS = {"scavenge": ("🥫", "Scavenge"), "guard": ("🛡️", "Guard"), "steal": ("🥷", "Steal"),
           "investigate": ("🔍", "Investigate"), "gift": ("🎁", "Gift")}
VERB = {"steal": "Steal from whom?", "investigate": "Watch whom?", "gift": "Give to whom?"}


class RadioView(discord.ui.View):
    """Radio by clicks: pick a line, then (if it names someone) a player. Torch words it, so nobody's writing style
    gives them away. Only the sender sees this; the message goes out anonymously with the morning news."""

    def __init__(self, bot, user_key, menu):
        super().__init__(timeout=600)
        self.bot, self.user_key, self.menu = bot, user_key, menu
        self.show_lines()

    def show_lines(self):
        self.clear_items()
        sel = discord.ui.Select(placeholder="📻 What should the radio say?",
                                options=[discord.SelectOption(label=t[:100], value=k) for k, t in self.menu["lines"]])

        async def cb(i):
            phrase = sel.values[0]
            if not GameService.radio_needs_player(phrase):
                return await self.send(i, phrase)
            self.clear_items()
            who = discord.ui.Select(placeholder="About whom?",
                                    options=[discord.SelectOption(label=a) for a in self.menu["about"][:25]])

            async def cb2(i2):
                await self.send(i2, phrase, who.values[0])
            who.callback = cb2
            self.add_item(who)
            back = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)

            async def go_back(i3):
                self.show_lines()
                await i3.response.edit_message(view=self)
            back.callback = go_back
            self.add_item(back)
            await i.response.edit_message(view=self)
        sel.callback = cb
        self.add_item(sel)

    async def send(self, i, phrase, about=None):
        try:
            async with self.bot.lock:
                text = self.bot.game.radio(self.user_key, phrase, about)
        except GameError as e:
            text = f"⚠️ {e}"
        self.stop()
        await i.response.edit_message(content=f"📻 {text}", view=None, allowed_mentions=NONE)
        await self.bot.deliver()


class PlayView(discord.ui.View):
    """/play: buttons for tonight's legal moves, then a player list, then (gifts) the amount. Only the player sees it;
    every click is still checked by GameService.submit, judged at the click's own timestamp."""

    def __init__(self, bot, user_key, menu):
        super().__init__(timeout=600)
        self.bot, self.user_key, self.menu = bot, user_key, menu
        self.show_moves()

    def show_moves(self):
        self.clear_items()
        for kind, (emoji, label) in BUTTONS.items():
            if kind in self.menu["moves"]:
                b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)
                b.callback = self._pick(kind)
                self.add_item(b)
        if self.menu.get("radio"):                         # today's anonymous message, on its own row
            r = discord.ui.Button(label="Radio", emoji="📻", style=discord.ButtonStyle.primary, row=1)
            r.callback = self._radio
            self.add_item(r)

    async def _radio(self, i):
        try:
            async with self.bot.lock:
                menu = self.bot.game.radio_menu(self.user_key)
        except GameError as e:
            return await i.response.edit_message(content=f"⚠️ {e}", view=None)
        self.stop()
        await i.response.edit_message(content="📻 Pick a line. It goes out anonymously with the morning news, "
                                              "and you still choose tonight's move with /play.",
                                      view=RadioView(self.bot, self.user_key, menu))

    def _pick(self, kind):
        async def cb(i):
            targets = self.menu["moves"][kind]
            if not targets:
                return await self.finish(i, kind)
            self.clear_items()
            sel = discord.ui.Select(placeholder=VERB[kind], options=[discord.SelectOption(label=a) for a in targets[:25]])
            sel.callback = self._target(kind, sel)
            self.add_item(sel)
            self._back()
            await i.response.edit_message(view=self)
        return cb

    def _target(self, kind, sel):
        async def cb(i):
            target = sel.values[0]
            amounts = self.menu["gift_amounts"]
            if kind != "gift" or len(amounts) == 1:
                return await self.finish(i, kind, target, amounts[0] if kind == "gift" else 0)
            self.clear_items()
            for a in amounts:
                b = discord.ui.Button(label=f"Give {a}", emoji="🎁", style=discord.ButtonStyle.secondary)
                b.callback = self._amount(target, a)
                self.add_item(b)
            self._back()
            await i.response.edit_message(view=self)
        return cb

    def _amount(self, target, amount):
        async def cb(i):
            await self.finish(i, "gift", target, amount)
        return cb

    def _back(self):
        b = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        async def cb(i):
            self.show_moves()
            await i.response.edit_message(view=self)
        b.callback = cb
        self.add_item(b)

    async def finish(self, i, kind, target=None, amount=0):
        try:
            async with self.bot.lock:
                text = self.bot.game.submit(self.user_key, kind, target, amount, at=i.created_at.timestamp())
        except GameError as e:
            text = f"⚠️ {e}"
        self.stop()
        await i.response.edit_message(content=text, view=None, allowed_mentions=NONE)
        await self.bot.deliver()


async def open_play(bot, i):
    """The private move menu, for /play and the board's Play button alike."""
    try:
        async with bot.lock:
            menu = bot.game.play_menu(str(i.user.id))
    except GameError as e:
        return await private(i, f"⚠️ {e}")
    await i.response.send_message(menu["header"], view=PlayView(bot, str(i.user.id), menu), ephemeral=True,
                                  allowed_mentions=NONE)


async def open_radio(bot, i):
    """The private radio picker, for /radio and the board's Radio button alike."""
    try:
        async with bot.lock:
            menu = bot.game.radio_menu(str(i.user.id))
    except GameError as e:
        return await private(i, f"⚠️ {e}")
    if not menu["available"]:
        return await private(i, "📻 You've already used today's radio message. It goes out with the morning news.")
    await i.response.send_message("📻 Pick a line. It goes out anonymously with the morning news.",
                                  view=RadioView(bot, str(i.user.id), menu), ephemeral=True, allowed_mentions=NONE)


class BoardView(discord.ui.View):
    """Buttons on the status board in #news. Persistent (fixed custom ids, no timeout, re-registered at startup), so
    they keep working on the pinned message after Torch restarts. Every reply is private to whoever tapped."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Play", emoji="🎮", style=discord.ButtonStyle.primary, custom_id="torch:play")
    async def play(self, i, _button):
        await open_play(self.bot, i)

    @discord.ui.button(label="Radio", emoji="📻", style=discord.ButtonStyle.secondary, custom_id="torch:radio")
    async def radio(self, i, _button):
        await open_radio(self.bot, i)

    @discord.ui.button(label="My status", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="torch:status")
    async def status(self, i, _button):
        try:
            async with self.bot.lock:
                text = self.bot.game.status(str(i.user.id))
        except GameError as e:
            text = f"⚠️ {e}"
        await private(i, text)


def register(bot):
    tree = bot.tree

    async def call(interaction, fn, *args, **kw):
        try:
            async with bot.lock:
                text = fn(*args, **kw)
            await private(interaction, text)
        except GameError as e:
            await private(interaction, f"⚠️ {e}")
        await bot.deliver()

    async def alias_complete(interaction, current):
        return [app_commands.Choice(name=a, value=a) for a in bot.game.alias_list(str(interaction.user.id))
                if current.lower() in a.lower()][:25]

    def key(i):
        return str(i.user.id)

    def at(i):
        return i.created_at.timestamp()

    @tree.error
    async def on_error(interaction, error):
        log.exception("command failed", exc_info=error)
        await private(interaction, "Something went wrong on Torch's side. Your move may not have been saved; "
                                   "check /status.")

    @tree.command(description="Join the game and get your secret alias")
    async def join(i: discord.Interaction):
        await call(i, bot.game.join, key(i))

    @tree.command(description="Make tonight's move: just click")
    async def play(i: discord.Interaction):
        await open_play(bot, i)

    @tree.command(description="Look for food tonight (0 to 2 rations)")
    async def scavenge(i: discord.Interaction):
        await call(i, bot.game.submit, key(i), "scavenge", at=at(i))

    @tree.command(description="Protect yourself tonight and tomorrow night")
    async def guard(i: discord.Interaction):
        await call(i, bot.game.submit, key(i), "guard", at=at(i))

    @tree.command(description="Steal rations from someone tonight")
    @app_commands.autocomplete(target=alias_complete)
    async def steal(i: discord.Interaction, target: str):
        await call(i, bot.game.submit, key(i), "steal", target, at=at(i))

    @tree.command(description="Watch someone tonight and see what they do")
    @app_commands.autocomplete(target=alias_complete)
    async def investigate(i: discord.Interaction, target: str):
        await call(i, bot.game.submit, key(i), "investigate", target, at=at(i))

    @tree.command(description="Secretly give someone 1 or 2 rations")
    @app_commands.autocomplete(target=alias_complete)
    @app_commands.choices(amount=[app_commands.Choice(name="1", value=1), app_commands.Choice(name="2", value=2)])
    async def gift(i: discord.Interaction, target: str, amount: app_commands.Choice[int]):
        await call(i, bot.game.submit, key(i), "gift", target, amount.value, at=at(i))

    @tree.command(description="Your rations, guards left, secret goal and tonight's move")
    async def status(i: discord.Interaction):
        await call(i, bot.game.status, key(i))

    @tree.command(description="What happened to you last night")
    async def results(i: discord.Interaction):
        await call(i, bot.game.results, key(i))

    @tree.command(description="Send an anonymous rumour by clicks (posted with the morning news)")
    async def radio(i: discord.Interaction):
        await open_radio(bot, i)

    @tree.command(name="quit", description="Leave the game (your food leaves with you)")
    async def quit_(i: discord.Interaction):
        await call(i, bot.game.quit, key(i))

    gm = app_commands.Group(name="gm", description="Game Master")

    async def gm_only(i):
        if not bot.is_gm(i):
            await private(i, "Game Master only.")
            return False
        return True

    @gm.command(name="add-sims", description="Add simulated colleagues (before the start)")
    @app_commands.describe(cast="balanced: one of each personality before any repeat; office: random office mix")
    @app_commands.choices(cast=[app_commands.Choice(name="balanced", value="balanced"),
                                app_commands.Choice(name="office", value="office")])
    async def add_sims(i: discord.Interaction, count: app_commands.Range[int, 1, 20],
                       cast: app_commands.Choice[str] = None):
        if await gm_only(i):
            kind = cast.value if cast else "balanced"
            await call(i, lambda: (bot.game.gm_add_sims(count, rng=random.Random(), cast=kind),
                                   f"Added {count} sim colleagues.")[1])

    @gm.command(name="start", description="Start the game")
    @app_commands.describe(events="Wilderness events: bananas, gorillas, hidden idols (about one a night)")
    @app_commands.choices(events=[app_commands.Choice(name="off", value="off"),
                                  app_commands.Choice(name="gentle", value="gentle")])
    @app_commands.describe(ranges="Post everyone's ration range in #news each morning (🟢 🟡 🔴 🏴‍☠️, never exact)")
    async def start(i: discord.Interaction, day_minutes: app_commands.Range[float, 1, 1440] = 5.0,
                    events: app_commands.Choice[str] = None, ranges: bool = False):
        if await gm_only(i):
            mode = events.value if events else "off"

            def go():
                bot.game.gm_start(day_seconds=day_minutes * 60, news_delay=10, now=time.time(), events=mode,
                                  ranges=ranges)
                return (f"Started: {len(bot.game.players)} players, a day every {day_minutes:g} minutes, "
                        f"events {mode}, ranges {'on' if ranges else 'off'}.")
            await call(i, go)

    @gm.command(name="who-moved", description="Who has chosen tonight's move (never rations)")
    async def who_moved(i: discord.Interaction):
        if await gm_only(i):
            def show():
                done, waiting = bot.game.gm_who_moved()
                return f"Moved: {', '.join(done) or 'nobody'}\nWaiting: {', '.join(waiting) or 'nobody'}"
            await call(i, show)

    @gm.command(name="pilot", description="One step: new season, you join, add sims, start (defaults = usual pilot)")
    @app_commands.describe(sims="Simulated colleagues", day_minutes="Minutes per round",
                           events="Wilderness events", ranges="Morning ration ranges in #news",
                           confirm="Needed only if a game is still running: it gets archived unfinished",
                           cast="balanced: one of each personality before any repeat; office: random office mix")
    @app_commands.choices(events=[app_commands.Choice(name="gentle", value="gentle"),
                                  app_commands.Choice(name="off", value="off")],
                          cast=[app_commands.Choice(name="balanced", value="balanced"),
                                app_commands.Choice(name="office", value="office")])
    async def pilot(i: discord.Interaction, sims: app_commands.Range[int, 1, 20] = 8,
                    day_minutes: app_commands.Range[float, 1, 1440] = 5.0,
                    events: app_commands.Choice[str] = None, ranges: bool = True, confirm: bool = False,
                    cast: app_commands.Choice[str] = None):
        if not await gm_only(i):
            return
        mode = events.value if events else "gentle"
        async with bot.lock:
            running = bot.game.started and not bot.game.finished
            if running and not confirm:
                return await private(i, "⚠️ A game is still running. Nothing changed. To end it unfinished and start "
                                        "a new one, run /gm pilot again with confirm: True.")
            if bot.game.started:                     # a waiting season keeps whoever already joined
                bot.archive_and_reset()
            try:
                alias = bot.game.join(key(i)).split("**")[1]
                bot.game.gm_add_sims(sims, rng=random.Random(), cast=cast.value if cast else "balanced")
                bot.game.gm_start(day_seconds=day_minutes * 60, news_delay=10, now=time.time(), events=mode,
                                  ranges=ranges)
            except GameError as e:
                return await private(i, f"⚠️ {e}")
        await private(i, f"🔥 Started: you're **{alias}** (secret), {sims} sims, a round every {day_minutes:g} "
                         f"minutes, events {mode}, ranges {'on' if ranges else 'off'}. Tap 🎮 Play on the board "
                         f"in #news.")
        await bot.deliver()

    def who(i, key_):
        m = i.guild.get_member(int(key_)) if i.guild and key_.isdigit() else None
        return m.display_name if m else f"<left the server {key_[-4:]}>"

    @gm.command(name="history", description="Who played which alias, in FINISHED seasons only (private to you)")
    @app_commands.describe(member="Only this person's seasons")
    async def history_cmd(i: discord.Interaction, member: discord.Member = None):
        if not await gm_only(i):
            return
        rows = hall.history(hall.load_seasons(bot.conf.data_dir), str(member.id) if member else None)
        if not rows:
            return await private(i, "No finished seasons yet" + (f" for {member.display_name}." if member else "."))
        lines = [f"`{datetime.datetime.fromtimestamp(r['started']).strftime('%d %b %H:%M')}` **{who(i, r['key'])}** "
                 f"was {r['alias']} · {r['points']} pts{' · 🚁' if r['seat'] else ''}{' · 🏆' if r['won'] else ''}"
                 for r in rows[:40]]
        await private(i, "📜 **Finished seasons, newest first**\n" + "\n".join(lines))

    @gm.command(name="hall-of-fame", description="Totals per person over finished seasons; post:True puts it in #news")
    @app_commands.describe(since="Only seasons started on or after this date, e.g. 2026-10-01",
                           post="Post it in #news for everyone (default: only you see it)")
    async def hall_cmd(i: discord.Interaction, since: str = None, post: bool = False):
        if not await gm_only(i):
            return
        try:
            ts = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp() if since else None
        except ValueError:
            return await private(i, "⚠️ since must look like 2026-10-01.")
        tot = hall.totals(hall.load_seasons(bot.conf.data_dir), since=ts)
        if not tot:
            return await private(i, "No finished seasons in that period.")
        lines = [f"{e} **{title}** ({meaning}): {', '.join(who(i, k) for k in keys)} ({v})"
                 for e, title, meaning, keys, v in hall.hall_of_fame(tot)]
        games = max(r["games"] for r in tot.values())
        text = (f"🏛️ **Survivors Hall of Fame**{f' since {since}' if since else ''} · {len(tot)} players · "
                f"up to {games} games each\n" + "\n".join(lines))
        pic = None
        try:
            from .hall_image import render as render_hall
            rows = [{"name": who(i, k), **v} for k, v in tot.items()]
            awards = [(t, m, [who(i, k) for k in keys], v) for _, t, m, keys, v in hall.hall_of_fame(tot)]
            pic = render_hall(rows, awards, subtitle=f"{len(tot)} players" + (f" · since {since}" if since else ""))
        except Exception:
            log.exception("hall of fame picture failed; text only")
        file = lambda: discord.File(io.BytesIO(pic), "hall-of-fame.png") if pic else discord.utils.MISSING  # noqa: E731
        if post:
            await bot.channels["news"].send(text[:1990], file=file(), allowed_mentions=NONE)
            return await private(i, "Posted in #news.")
        await i.response.send_message(text + "\n\n*Only you see this. Run again with post: True to share it in #news.*",
                                      file=file(), ephemeral=True, allowed_mentions=NONE)

    @gm.command(name="new-season", description="Archive this game and start an empty one")
    async def new_season(i: discord.Interaction, confirm: bool):
        if await gm_only(i):
            if not confirm:
                await private(i, "Nothing changed. Run again with confirm: True.")
                return
            async with bot.lock:
                bot.archive_and_reset()
            await private(i, f"New season {bot.game.season_id}. The old one is archived.")

    tree.add_command(gm)


def main():
    logging.basicConfig(level=os.environ.get("TORCH_LOG", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    conf = cfg.load()
    Torch(conf).run(conf.token, log_handler=None)


if __name__ == "__main__":
    main()
