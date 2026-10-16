# Survivors: Office Game Rules

> Snapshot of the Claude doc "Survivors: Office Game Rules", taken 16 Oct 2026. The live doc (https://claude.ai/code/artifact/25ac394f-6632-4708-b011-4324fc9b2e65) is the master copy; update it first, then refresh this file.

Oct 16, 2026 · @Corne

Survivors is a two-week, opt-in Discord game for the whole company, about two minutes a day. Rations are scarce, every action is secret, and betrayal is always on the table: you'll know what happened, rarely who did it.

## Aliases

Everyone plays under a secret alias the bot gives them when they join, like RustyKettle or QuietBadger. Everything in the game uses aliases: #news, #radio, investigations, the helicopter and the final stats. During the season nobody can look up who's behind an alias, not even the Game Master.

- **#town-square is normal chat.** People talk as themselves and role-play about aliases: "RustyKettle got me last night." Nobody knows who RustyKettle is, so the mystery holds. Giving yourself away is your own call, and lying is fair game.
- **Keep it light.** About two minutes a day: one move, the morning news, and banter if you feel like it. No extra messaging systems, nothing that pulls people away from work.
- **The reveal shows aliases, never real names.** People will work plenty out from timing and style, but nothing official ever confirms it. Anyone can unmask themselves if they want to.
- **Across seasons (open):** keep your alias and build a legend, or get a new one each season with luck tied to you behind the scenes.

## The daily loop

Each weekday is one round: pick one secret action before midnight, and the results land in #news at 07:30, just before morning coffee.

- **Length:** 10 rounds over two weeks, weekdays only.
- **Start:** 7 rations each. Every night costs 1.
- **Deadline:** actions lock at 23:59. You can change your mind until then; the last one counts.
- **Missed the deadline?** You scavenge by default, so nobody dies from a busy day.
- **The news:** the bot reports in character. Victims are named by alias; thieves are not, unless they got caught.

How a night resolves, in order:

1. Guards go up.
2. Steals hit guards first: a caught thief is named publicly and pays the guard 2.
3. Other steals take 2 each (bandits take 1). Several thieves on one target split what's there.
4. Scavengers roll 0–2.
5. Gifts go through.
6. Everyone eats 1.
7. Anyone at 0 becomes a bandit.
8. Investigators get their private DM. A target caught stealing is exposed in #news and pays the investigator 1. #news posts at 07:30.

## Actions

You get one action per night, and nobody sees it but you. Guard beats Steal, and Investigate is the only way to know anything for sure.

| Action | What it does | The catch |
| --- | --- | --- |
| Scavenge | Gain 0–2 rations at random | Break-even on average, and you're a sitting target |
| Steal @player | Take 2 rations, anonymously | Hit someone on Guard and you're named publicly and pay them 2 |
| Guard | Protects you tonight and tomorrow night. Any thief who tries is named and pays you 2 | Only 3 guards per game, and you gain nothing the night you set one |
| Investigate @player | The bot DMs you what they did that night. Catch them stealing and they're exposed in #news and pay you 1 | No income that night. Anything else you learn is yours to use, sell or lie about |
| Gift @player [amount] | Hand over rations | Only you and the receiver know, unless one of you talks |

The bot never confirms or denies anything a player claims. Lying about what you did is part of the game.

## Mystery layers

Three extra layers make sure nobody can read anyone's motives with confidence.

**Secret objectives.** Everyone gets one private goal card at the start, worth bonus points at the end. The kind player might just be farming a generosity card. Example cards:

- Finish with more rations than @player.
- Get robbed at least once and still extract.
- Steal at least three times without ever being caught.
- Give away 3 rations over the game.
- Successfully rob @player at least once.

**Radio.** `/radio` posts one anonymous message a day to #radio, up to 280 characters. Use it for tips, accusations, lies and framing.

**Bandits.** At 0 rations you come back as a bandit. Bandits don't eat, can only steal or investigate, and take just 1 per steal. A bandit who gets back to 3 rations rejoins as a survivor. Nobody is ever out, and the dead have nothing to lose.

## Extraction

On the final night a chopper arrives with seats for about a third of the survivors (5 seats for 15 players). Seats go to the top ration holders once the last night resolves. Ties go to whoever gave away the most rations during the game, then a coin flip announced live. Bandits can't extract.

Expect the last night to be carnage: allies turned, last-minute raids, and someone you trusted for two weeks taking your seat.

| Result | Points |
| --- | --- |
| Extracted | 3 |
| Secret objective completed | 2 |
| Survived but didn't extract | 1 |

Highest total wins, and a tie goes to whoever gave away the most. Prizes stay trivial (coffee, bragging rights).

**The reveal.** The final #news post unmasks everything: every objective, every theft and every betrayal, night by night. That post is what people will still be talking about a month later.

## Camps (phase 2)

Camps switch on in phase 2, once everyone has played a first game without them.

Camps are the alliance system: a shared stash that outsiders can't touch, and that any member can empty overnight.

- **Form one:** `/camp create`, then `/camp invite @player`. Max 4 members, and you can only be in one camp.
- **Deposit:** members pool rations with `/camp deposit`. Outside steals can't reach the stash.
- **Withdraw:** openly, any time. The rest of the camp sees who took what.
- **Loot:** use your night action to take the whole stash. #news only says the camp was emptied by one of its own, the camp dissolves, and nobody is named.
- **Double cross:** if two members loot the same night, they split it, and both know someone else had the same idea.
- **Leaving** is public, so walking out looks suspicious too.

This is the shot-in-the-back moment: three suspects, zero proof, and only an Investigate on the right person that night would have caught it.

## Luck and random events (proposed, behind the scenes)

These ideas aren't in the rules yet. Each gets simulated before it goes in. The aim: keep every move worth trying, add surprises nobody can plan for, and give people a reason to come back next season.

**Players are never told how any of this works.** They just enjoy it: the apparition shows up, someone gets lucky, a storm hits. The odds, the underdog bonus and how luck builds exist only for balancing, so this section stays out of the explainer video and any player-facing rules.

**Random events.** Once a day, at a random time, the bot rolls for an event; most days nothing happens. Most events are private, so someone suddenly has food they can't explain, and the accusations write themselves.

- **The apparition** (private DM): something appeared at your tent last night and left 1 ration.
- **Lucky find** (private): your scavenge turns up an extra ration.
- **Rats** (private): 1 ration gone. Only you know it wasn't a thief.
- **Mystery item** (private, one use): a lantern for a free investigation, or a decoy tin a thief takes instead of real food.
- **Supply drop** (public): a crate lands; everyone who claims it before midnight splits it.
- **Storm** (public): nobody can scavenge tonight.

Every roll is saved, and the final reveal shows them all.

**Underdog bonus.** Whichever action the fewest people chose that night has a chance of a lucky find. If the office stops guarding, guarding starts paying, so no move ever dies out. Nobody knows tonight's lucky move in advance.

**Luck across seasons.** Luck carries over between games and slightly improves your odds of good events. You earn it by playing interestingly (catching a thief, being generous, surviving a betrayal), not just by winning. It's capped at +3 and partly fades between seasons, so it never locks in.

**Beginner's luck.** First-season players get a hidden boost that fades over their first game, so veterans can't run away with it. Nobody knows who's lucky, which makes a newcomer's good run look suspicious.

**Titles.** Discord roles like "Season 1 Survivor" or "Most Trusted Liar". All bragging rights, no effect on balance.

**Already tested:** a flat 50% chance of +1 for guarding didn't bring guarding back among players who learn from results, and it made a lone thief stronger (1.04× to 1.30× a fair share of wins). That's why the bonus goes to the least-chosen action instead of always to guarding.

**Still to test:** how often events fire and how big they are, the underdog bonus, and several seasons back to back with luck and beginner's luck, to check veterans keep a small edge without running away with it.

## Dials

The rules above use the recommended pick for each dial. Each one changes the feel, so it's worth deciding before the bot is built.

| Dial | Recommended | Alternatives |
| --- | --- | --- |
| Thief anonymity | Hidden unless caught by a guard or an investigator | Always hidden · a clue on every steal ("the thief's name has 5 letters") |
| Secret roles | None for the first game | Informant sees one random action per night · Medic revives one bandit |
| Extraction seats | Top ration holders | Group vote, which turns the finale into pure politics |
| Length | 10 weekday rounds | 5 rounds as a one-week pilot |
| Camp size (phase 2) | Max 4 | Max 3 for sharper suspicion · no limit |
| Steal size | 2 | 1, which makes crime pay much less and robberies less dramatic |

## Balance testing

These rules were tuned by simulating the office: 300 games per rule set, 15 players with mixed personalities. The first draft killed most of the office and let one dedicated thief win almost twice as often as anyone else; the current rules fix both.

| Per game (average) | First draft | Current rules |
| --- | --- | --- |
| Still alive at the end | 7 of 15 | 11 of 15 |
| Hit zero at some point | 11 | 5 |
| Bandit comebacks | 5.6 | 1.5 |
| Steals caught by a guard | 13% | 24% |
| Robberies per night | 2.6 | 2.0 |
| Last seat decided by coin flip | 39% | 18% |
| Chopper seats won by heavy thieves | 49% | 26% |
| Best all-in strategy, vs a fair share of wins | 1.9× (always steal) | 1.0× (always steal) |

Going all-in on one action no longer beats mixing it up. Guarding every night starves you, and an office where everyone only scavenges gets ten quiet nights, which is why a lone thief always has an opening. The simulated players don't adapt like real people, so treat this as a stress test, not a prediction.

## Guardrails

The betrayals stay inside the game, so nobody walks into Monday feeling genuinely wronged.

- **Opt-in:** join with `/join`, leave any time with `/quit`, no questions asked.
- **In-game only:** rations are the only currency. No work tasks, real money or real-world favours.
- **Radio is logged:** anonymous to players, with the sender's alias kept in the log. Only abuse justifies looking up who's behind it. Anything personal or nasty gets deleted and costs the sender their radio.
- **A neutral Game Master:** whoever runs the bot either sits out or never looks at the database mid-game.
- **No noise:** one #news post a day and no reminder pings.

**Everything is logged.** Players are told when they join that every move is recorded and replayed after the game, so the season can end with an animated recap of how it all happened.

- The log uses aliases. The link to real Discord accounts sits in a separate, locked table.
- The log stays locked until the reveal, so the Game Master can't peek.
- Moves are kept to balance future seasons. Radio posts are deleted once the recap is made, and anyone can ask for their data to be deleted.
- Open chat in #town-square goes into the replay only if players are told that up front.
- Game data stays separate from work systems. After a season, its moves can be loaded into their own space for analysis.

## Build notes

The bot is a small Python service on the Pi, separate from the existing bot there, with its own token and its own systemd service.

| Piece | Plan |
| --- | --- |
| Channels | #town-square (open chat), #news and #radio (bot posts only) |
| Commands | `/join`, `/status`, `/scavenge`, `/steal`, `/guard`, `/investigate`, `/gift`, `/radio`, `/quit`. All replies are ephemeral. |
| Schedule | Actions lock at 23:59; the night resolves and #news posts at 07:30, weekdays only |
| Stack | Python, discord.py, SQLite |
| Data | Players, actions per round, and a complete replay log: every command, change of mind, random roll, ration change, message and DM, in order and timestamped. The whole game can be checked, replayed and animated afterwards. Same format the simulator already writes (sim/LOG_FORMAT.md) |
| Fairness | A seeded random roll per round, so every result can be audited after the game |
| Aliases | Assigned at /join from a list of fun names and sent by private reply. Game tables and the log only use aliases; the alias-to-account link lives in a separate, locked table |

Build order: the core loop first (rations, the five actions, the nightly resolve, the #news post), then the mystery layers. Camps come in phase 2.
