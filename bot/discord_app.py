"""Torch on Discord: slash commands into the GameService, a loop that advances the game and delivers its outbox.

    python -m bot.discord_app

Every player-facing reply is ephemeral (only the player sees it). The game's clock runs on real time; a GM picks
the length of a day when starting (5 minutes for pilots). News goes to #news, radio to #radio, results by DM with
/results as the fallback when DMs are closed.
"""
import asyncio
import json
import datetime
import logging
import os
import random
import time

import discord
from discord import app_commands

from . import config as cfg
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
                           self.conf.aliases, season)

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
            return                                    # unchanged, or news still going out: wait until it's above
        ch = self.channels["news"]
        if state.get("message_id"):
            try:
                old = await ch.fetch_message(int(state["message_id"]))
                await old.delete()
            except discord.HTTPException:
                pass                                  # already gone
        msg = await ch.send(text, allowed_mentions=NONE)
        try:
            await msg.pin(reason="Torch status board")
        except discord.HTTPException:
            pass                                      # no pin rights: the board still sits at the bottom of #news
        json.dump({"key": list(key), "message_id": str(msg.id)}, open(path, "w", encoding="utf-8"))

    async def deliver(self):
        async with self.send_lock:
            await self._deliver()

    async def _deliver(self):
        for intent in self.game.pending_outbox():
            text = self.game.outbox_text(intent)
            to = intent["to"]
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
        try:
            async with bot.lock:
                menu = bot.game.play_menu(key(i))
        except GameError as e:
            return await private(i, f"⚠️ {e}")
        await i.response.send_message(menu["header"], view=PlayView(bot, key(i), menu), ephemeral=True,
                                      allowed_mentions=NONE)

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
        try:
            async with bot.lock:
                menu = bot.game.radio_menu(key(i))
        except GameError as e:
            return await private(i, f"⚠️ {e}")
        if not menu["available"]:
            return await private(i, "📻 You've already used today's radio message. It goes out with the morning news.")
        await i.response.send_message("📻 Pick a line. It goes out anonymously with the morning news.",
                                      view=RadioView(bot, key(i), menu), ephemeral=True, allowed_mentions=NONE)

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
    async def add_sims(i: discord.Interaction, count: app_commands.Range[int, 1, 20]):
        if await gm_only(i):
            await call(i, lambda: (bot.game.gm_add_sims(count, rng=random.Random()), f"Added {count} sim colleagues.")[1])

    @gm.command(name="start", description="Start the game")
    @app_commands.describe(events="Wilderness events: bananas, gorillas, hidden idols (about one a night)")
    @app_commands.choices(events=[app_commands.Choice(name="off", value="off"),
                                  app_commands.Choice(name="gentle (about 1 a night)", value="gentle")])
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
