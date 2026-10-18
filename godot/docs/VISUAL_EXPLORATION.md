# Visual exploration: how should the game look?

**Written:** 18 Oct 2026, by the client session. **For:** the owner, and any design agent given this file as a brief.
**Live step tracker:** https://claude.ai/artifact/VKRpFqztv8KqqmLudfb7aK (updated as the build moves)
**Rules of the game:** `docs/MECHANICS.md` (exact), `docs/ARENA.md` (the live-room rules). This file never overrides them.

**Nothing waits on this document.** The build does not need a choice from it: screens are built first in neutral
placeholder layouts, and a look only changes the theme and the arrangement later. You do not have to pick one of the
three; they are there to react to ("this part", "not that"), whenever you want to. Section 7 is optional.

**Drawn frames:** `godot/docs/visual/STORYBOARDS.md` and `storyboards.html` (15 frames: the three treatments on the five
moments below), also at https://claude.ai/artifact/72JE4MgPTHYfdnuNmAhAGn.

| Part | What it is | Who writes it |
|---|---|---|
| 1. Where this fits | Which tracker steps produce the pictures you will look at | fixed |
| 2. The crux | Why the game is the game, in one page | fixed |
| 3. Everything that must be drawn | The full inventory: moves, night, events, goals, radio, end, screens, privacy | fixed (from MECHANICS) |
| 4. Constraints | What any look must obey | fixed |
| 5. The exploration process | How to go from brief to a chosen look | fixed |
| 6. Pass 1: three treatments | Three different ways to illustrate all of it | the agent (first pass, 18 Oct 2026) |
| 7. Owner reactions and decision log | Optional blank tables, for whenever you have a reaction | the owner |

---

## 1. Where this fits in the build (point at the tracker)

Steps 1 to 3 in the tracker are plumbing and show nothing on screen. Everything you will actually look at starts at step 4.

| Tracker step | What appears | What this document decides there |
|---|---|---|
| 4. Screens: title, lobby, round, upgrade, settings, overlays, end | The first drawn screens (placeholder shapes and plain words) | The layout of the **round screen** (the one you spend most time on) and how the timer, lock and move picker look |
| 5. Stage and reveal animation; second theme "night" | The night playing out, and the same game reskinned | The **reveal** (what a theft, a catch, an event looks like) and what a second theme changes |
| 6. Autopilot and first windowed run with screenshots | Real screenshots of every screen, saved to disk | The five storyboard moments in section 5.3, captured for each look |
| 7. Design pass on the rendered screens | Phone and desktop width, before and after | Whether the chosen look reads in seconds, with the alias and the timer first |
| 8. You drive the Windows build | You, playing | Your acceptance of the look |
| 9. Windows debug export and Android debug APK | The same on your phone | Nothing new; checks it survives a phone |

**Rule from the build:** screens know nothing about this game's words or art. A look is delivered as a **theme** (words, colours, icons, effects) plus a **layout**; the game's logic never changes. So three looks can be tried without touching the rules.

---

## 2. The crux of the game

Ten nights on an island (the Discord version says "office"; the words belong to the theme). Four people in a live room. **Only one of the four gets the helicopter seat.** Every night everyone secretly picks one of five moves; they all resolve together; you learn only what happened to you plus a public news bulletin that **never says who did it**.

| Tension | How it shows up in play |
|---|---|
| Food is life | Everyone starts with 7 rations and eats 1 a night. At 0 you become a **bandit**: you may only steal or investigate until you scrape together 3 |
| Greed against fear | Stealing takes 2 (a bandit takes 1). A **guard** catches thieves and takes 2 from them. An **investigator** exposes a thief, who must give the loot back and pay 1 |
| Secrets | Your alias is secret. Your exact food is secret (others see only a band). Your goal is secret. Bots look exactly like people |
| Suspicion | An anonymous **radio**, one message a night from 8 fixed phrases. It can lie |
| Cooperation | A **gift** of 1 or 2 is worth 1 more to the receiver than it costs the giver, so kindness grows food |
| Luck | Scavenging finds 0, 1 or 2. A wilderness **event** each night helps or hurts someone |
| Time pressure (live rooms) | 3 minutes to decide. You **lock in** to make it final. When every human has locked, the night resolves at once. A 20 second reveal, then the next night |
| The ending | After night 10 the helicopter takes the richest survivor(s). Points: seat 3, secret goal met 2, survived without a seat 1 |

**Feelings the pictures must carry** (the reason to look at anything): relief (found food), greed, suspicion, betrayal, getting caught, being exposed, desperation (bandit), the comeback, the last night, the helicopter.

---

## 3. Everything that must be drawn

### 3.1 Actors, resources and states

| Thing | Facts (from MECHANICS) | Public or private |
|---|---|---|
| Player | 4 per room; each has a secret alias. Bots fill empty seats and are indistinguishable | Aliases are shown; whether a seat is a bot is never shown |
| Food ("rations") | Start 7. Eat 1 a night (not on a feast night) | Exact count: yours only. Others: a band |
| Bands (morning board) | well fed 7+, getting by 3 to 6, starving 1 to 2, bandit | Public |
| Bandit | At 0 food. Only steals (takes 1) or investigates. Cannot take a helicopter seat. Rejoins at 3 food | Public the morning it happens |
| Shield (guard) | Covers tonight and tomorrow night. Up to 3 per game. Finds nothing while guarding | Yours: private. Others': only when it catches someone, or when an event drops it |
| Idol charm | A hidden one-use charm: the next thief gets nothing | Private to the holder until it saves them |
| Secret goal | One of 6 types, worth 2 points | Private until the end |

### 3.2 The five moves

| Move | Target | What it does | Result you see | What the public sees |
|---|---|---|---|---|
| Scavenge | none | Find 0 to 2 rations | "You found N" | nothing |
| Guard | none | Shield yourself 2 nights; thieves who hit you pay 2 (the guard keeps up to 2) | "You're on guard" | only if it catches someone |
| Steal | a player | Try to take 2 (bandit 1). Several thieves on one victim share what is there | Stole N / found nothing / someone beat you to it / caught by a guard and paid 2 | "Someone hit X, X is down N" (thief unnamed), or "CAUGHT: guard caught thief" |
| Investigate | a player | Learn what the target chose tonight. If it was a steal, the thief is exposed | "You watched X: they chose …", plus the exposure and a bounty of 1 | "EXPOSED: an investigator saw thief rob victim" (investigator unnamed) |
| Gift | a player, 1 or 2 | Give food; the receiver gets 1 extra | "You gave X n" | nothing; the receiver is told who gave |

### 3.3 The night, in the order it resolves (the order of the reveal)

| Phase | What happens | Visual verb |
|---|---|---|
| 0 | Wilderness event(s) change food before the night starts | something arrives from the sky or the world |
| 1 | Guards go up | a shield appears |
| 2 | Thieves who targeted a guard are caught and pay 2 | a trap springs, food flows from thief to guard |
| 3 | Other thefts land (shared from a fixed snapshot; tonight's loot cannot be re-stolen) | food leaves a victim for an unseen hand |
| 4 | Scavengers find 0 to 2 | food appears from nowhere |
| 5 | Gifts go through (+1 bonus to the receiver) | a parcel travels from giver to receiver |
| 6 | Investigations: the thief is exposed, hands the loot back, pays the bounty of 1 | a mark on the thief, food flows back |
| 7 | Everyone eats 1; anyone on 0 becomes a bandit; a bandit with 3 rejoins | food consumed; a status change |

### 3.4 Wilderness events (12 kinds; each has several tellings the theme may reword)

| Event | Scope | Effect | Public | Tellings |
|---|---|---|---|---|
| bananas | one player | +1 | yes | 7 |
| coconut | one player | +1 | yes | 7 |
| cache | one player | +2 | yes | 3 |
| idol | one player | gets the hidden charm | **no** | 1 |
| snake | one player | -1 (never below 1) | yes | 7 |
| rain | one player | -1 (never below 1) | yes | 7 |
| shelter | one player | their guard collapses for tonight | yes | 1 |
| storm | whole camp | nobody finds food tonight | yes | 4 |
| feast | whole camp | nobody eats tonight | yes | 4 |
| rats_top | the richest | each loses 1 | yes | 5 |
| rats | whole camp | everyone holding 7+ loses 1 | yes (never drawn in Torch's gentle mode) | 1 |
| raid | one rich player | -2 | yes (never drawn in Torch's gentle mode) | 6 |

An event arrives from the server as a finished English sentence **plus** its id, its scope (one player or the whole camp) and who it hit (since 11:02 on 18 Oct 2026). The story **variant** (which of the tellings) is not available: the engine does not record it, so a theme words an event by its id, not by variant.

### 3.5 The six secret goals

| Goal | In plain words |
|---|---|
| beat | finish with more food than a named player |
| robbed and extract | get robbed once and still get a helicopter seat |
| clean thief | steal 3 times before ever being caught |
| give | give away 3 rations over the game |
| grudge | rob a named player once |
| detective | expose a thief at least once |

Progress states a goal card can show: open, done, failed, "decided at the end". The server now sends a goal and its progress as a code plus values, so a theme words them itself. A 4-seat room deals only 4 of the 6 goal types (no grudge, no detective).

### 3.6 The radio

| Fact | Detail |
|---|---|
| Limit | one message per player per night, no typing |
| The 8 phrases | "I saw {a} sneaking around last night" · "Don't trust {a}" · "{a} is lying about their rations" · "{a} is guarding. Don't waste your night on them" · "{a} looks like an easy target" · "{a} is innocent. Leave them alone" · "Someone should watch {a}'s back tonight" · "I'm innocent. Leave me alone" |
| Delivery | all of a night's messages arrive together with the morning news, anonymous, ordered by wording (not by who sent first) |
| Truth | not checked; radio can lie |

### 3.7 Time, lock and rhythm (live rooms)

| Element | Value |
|---|---|
| Rounds | 10 |
| Decide | 180 s per night; pick freely, then **Lock** makes it final; after Lock the picker is read-only |
| Early finish | when every connected human has locked, the night resolves at once; bots lock like people at random moments |
| Reveal | 20 s, or until everyone presses Continue |
| Countdown | in Torch the last 3 nights get a "nights left" line and the last is "LAST NIGHT"; whether the live room shows it is open |
| Indicator | "N of M locked in" is a **count only**; never who |

### 3.8 The ending

| Element | Detail |
|---|---|
| Helicopter | seats = a third of the players, minimum 1 (4 players: 1 seat). Goes to the survivors with the most food; ties break by most given away, then fewest times caught |
| Points | seat 3, secret goal met 2, survived without a seat 1; bandits and quitters 0 |
| Results table | points, seat, rations, stole, robbed, gave away, goal met or missed |
| Highlights | top of points, rations, stole, gave away are highlighted; the client shows **robbed** but never ranks or highlights it (the Hall of Fame is "praise only", with no most-robbed list) |
| Awards | Torch's reveal picture has four award cards: Biggest thief, Most robbed, Most generous, Biggest stash. Whether the live end screen shows award cards is open |

### 3.9 Screens the client has

| Screen | Shows |
|---|---|
| Title / join | create a room, enter a code, server address |
| Lobby | room code, "N of 4 seats", Start for the host |
| Round | your alias, the timer, your food, the five moves and their targets, Lock, "N of M locked", goal card, radio, the other homes with their bands |
| Reveal | the night playing out, the written log, your private lines, the radio, Continue |
| End | helicopter, winners, results table |
| Upgrade | "update the app" |
| Overlays | reconnecting, can't reach the server, notices |

### 3.10 What a picture may and may not reveal (privacy)

| Allowed | Never |
|---|---|
| Your exact food, your shield, your goal, your idol | Another player's exact food (only the band) |
| Another player's band (if ranges are on) | Who stole from whom, unless a guard caught them or an investigator exposed them |
| A thief named when **caught** or **exposed** | Who the investigator was |
| That a guard dropped (the shelter event) | Whether a seat is a bot or a human |
| "N of M locked in" | Who has locked, or in what order |
| The radio text | Who sent a radio message |
| Anyone's alias | Real names or account names, ever |

Practical consequence for every look: **an unseen hand** must be drawable: an actor that comes from off-screen and belongs to no home.

---

## 4. Constraints any look must obey

| Constraint | Why |
|---|---|
| Theme-neutral structure | A look is a theme (words, colours, icons, effects) over fixed screens. The same game must be re-skinnable by changing a folder |
| Draws only the latest server view | The client has no rules; it never works out what is legal or what happened |
| Portrait phone first (540 by 960 logical) and a desktop window | You play on both |
| Readable in seconds | 3 minutes to decide; the alias and the timer are what the eye lands on first |
| No colour-only meaning | Bands, states and teams need a shape or label too |
| No typing | The only text input is the room code and server address |
| No emoji in text | Icons are textures, not font glyphs |
| Cheap to start | Everything first exists as plain shapes and words; art arrives later |
| Four players | Layouts are for exactly 4 homes (you plus 3) |

### 4.1 The beat vocabulary the Stage already understands

Every line the server sends is turned into one or more of these. A look must give each one a visual:

| Beat kind | Meaning | Example |
|---|---|---|
| move_resource | food moves from A to B (A or B may be off-screen) | a theft, a gift, finding food, eating |
| shield_on | a shield goes up | guard |
| blocked | an attempt hit a shield or charm | caught by a guard, an idol saves someone |
| empty | an attempt found nothing | broke in, nothing there |
| learn | I learn what someone chose | investigate |
| marked | someone is publicly caught in the act | exposed |
| status | someone becomes, or stops being, a bandit | night end |
| camp | something happens to everyone | storm, feast, rats |
| charm | I secretly hold a charm | idol |
| total | my food is now N | end of the reveal |
| quiet | nothing happened | a quiet night |
| event | a world event, as a sentence for now | bananas, snake |
| unknown | something this client does not know | fallback |

---

## 5. The exploration process

### 5.1 Steps

| # | Step | Output | Who |
|---|---|---|---|
| 1 | Read sections 2 to 4 | shared picture of what must be drawn | agent |
| 2 | **Diverge**: produce three treatments that differ in *kind*, not in colour | three one-page concepts (section 6) | agent |
| 3 | **Storyboard** each treatment on the five moments in 5.3 | 5 frames per treatment, as sketches or plain shapes | agent |
| 4 | **React** | the owner marks what excites and what feels wrong (section 7) | owner |
| 5 | **Cheapest prototype** | the same two moments built with the placeholder theme in the real client | agent |
| 6 | **Converge** | one look, or a named blend, written to the decision log | owner and agent |
| 7 | **Theme spec** | words, palette, icon list, effect list for the chosen look (tracker step 5) | agent |

### 5.2 How to judge (qualitative; nothing here is measured)

| Question | Why it matters |
|---|---|
| Can a new player find "my food, my timer, my move, Lock" in 3 seconds? | 3 minutes is short |
| Does a theft read as a theft **without** naming the thief? | The privacy rule |
| Does being caught, exposed, or turning bandit feel like something? | The emotional beats |
| Does the reveal fit in 20 seconds? | Real nights have up to about 13 beats (the longest measured: 12.4 s at 1 second a beat) |
| Does it still read on a phone in sunlight, in greyscale? | No colour-only meaning |
| Does it reskin by changing words and icons only? | Theme-neutral |
| How much art does it need before it is playable? | Cheap to start |
| Is it fun to watch for the three players who are not acting? | Rooms are social |

### 5.3 The five storyboard moments (the same for every treatment)

| # | Moment | Why this one |
|---|---|---|
| 1 | A quiet night: you scavenge and find 1 | the baseline; must not be boring |
| 2 | You steal; a guard catches you; the public bulletin names you | privacy plus the sting of being caught |
| 3 | Someone you never saw takes 2 from you ("someone hit you") | the unseen hand |
| 4 | You run out of food and become a bandit; two nights later you rejoin | the long arc of one state |
| 5 | Night 10 ends: the helicopter arrives and takes one of four | the payoff |

### 5.4 Questions for the owner (answers go in section 7)

| # | Question |
|---|---|
| 1 | Island camp, office, or something that belongs to neither? (the words are a theme; the layout is not) |
| 2 | Should the reveal be a short film you watch, or a log you read with small animations beside it? |
| 3 | Should your own home be bigger than the others, or all four equal? |
| 4 | Should bots and people ever look different to you? (the rules say no) |
| 5 | Phone first, desktop first, or both equal? |
| 6 | Sound: silent, ambient, or cues for the big moments? |
| 7 | How cartoonish or how serious? |

### 5.5 Copy-paste brief for a design agent

```
You are the visual design agent for a live four-player survival game. Read godot/docs/VISUAL_EXPLORATION.md
sections 2 to 4 in full, and docs/MECHANICS.md only for detail. Produce three treatments that differ in KIND (for
example spatial, tabletop, abstract), not in colour. For each: the metaphor in one sentence; the round screen as a
wireframe; how each of the five moves looks while choosing and while resolving; how each of the 13 beat kinds looks;
events, bandit, guard, idol, bands, radio, lock, timer, end; phone versus desktop; how the unseen hand is drawn
without naming anyone; what a second theme changes; what art is needed before it is playable; the biggest risk.
Then storyboard the five moments in section 5.3 for each. Do not choose a winner. Do not change any rule.
```

---

## 6. Pass 1: three treatments (the agent, 18 Oct 2026)

These are design proposals, not facts about the game. Each is built to cover every item in section 3 and every beat in 4.1.

### 6.1 Treatment A: "The Camp" (spatial, a living diorama)

**Metaphor.** A top-down camp at night. Four shelters sit around a central fire. Everything that happens, you *see happen*, as little figures walking between shelters.

**Round screen (portrait)**

```
+------------------------------------+
| Round 4 of 10        [ fire = timer ]|   timer = the fire burning down, with a number
|                                    |
|        (shelter: Kiwi)             |
|   (shelter: Fig)     (shelter: Plum)|   others: small, pile of food sized by band
|                                    |
|            ( FIRE )                |
|                                    |
|        [ YOUR SHELTER ]            |   yours: large, your exact food as a visible pile, your shield, your goal card
|  food 7   shield 2   goal [card]   |
+------------------------------------+
| (scavenge)(guard)(steal)(investigate)(gift) |   the five moves as round tokens
| tap a move, then tap a shelter     |
| [ 2 of 4 locked ]      [ LOCK IN ] |
+------------------------------------+
```

| Element | Look |
|---|---|
| Timer | the central fire burns lower; the last 10 seconds it flickers; a number sits in it |
| Choosing | a token flies from the tray to the shelter you target; a dotted line shows your pick (only you see it) |
| Lock | you press and hold a seal; the token locks into place and your shelter dims slightly; "2 of 4 locked" is lanterns lit on the fire's rim, with no names |
| Bands | pile size and a banner shape (full, medium, thin, torn) in each shelter, never a number |
| Reveal | the screen dims to night; the log scrolls beside it (below on a phone); figures walk |

| Moment | How it plays |
|---|---|
| Scavenge | your figure leaves, a rustle in the bushes, returns with 0, 1 or 2 crates |
| Steal | a hooded silhouette crosses the dark from the screen edge to a shelter; the edge is the "unseen hand" |
| Guard | a lantern lights over a shelter and stays lit for two nights |
| Caught | the lantern flares into a spotlight on the thief; the thief's name and the guard's appear on a bulletin board |
| Investigate | a figure with a spyglass peers at a shelter; a card flips showing what they did |
| Gift | a wrapped parcel arcs from one shelter to another |
| Exposed | a red stamp lands on the thief's shelter; food returns, a coin goes to a hidden hand |
| Bandit | the shelter goes dark, a tattered flag rises, the figure is hooded; rejoining relights it |
| Events | weather over the whole camp (storm, fog = no foraging; feast = a big shared fire); a creature or object visits one shelter; the idol is a glowing carving that only its owner sees |
| Radio | a crackling set on a log by the fire; at dawn, speech bubbles rise from it one by one |
| End | dawn; a helicopter lands in the clearing; the winner's figure climbs in; the others watch it leave |

| Question | Answer |
|---|---|
| Phone vs desktop | portrait ring fits a phone; desktop adds the log beside the camp |
| Privacy | thefts come from the edge; only caught or exposed thieves are named |
| Second theme | an office floor with desks around a coffee machine; same layout, different icons |
| Art needed before playable | low: circles for shelters, a flame shape, simple figures; art can grow |
| Risk | the reveal must fit 20 seconds when 13 things happen; walking figures are slow, so figures must move fast and overlap |

### 6.2 Treatment B: "The Table" (tabletop, tactile)

**Metaphor.** A felt table. Each player has a stack of chips, a hand of five move cards, and a face-down card slot. The night is a dealer resolving cards in order.

**Round screen (portrait)**

```
+------------------------------------+
| Round 4 of 10                 (sand)|   timer = a ring of sand around your slot
|  [Kiwi]      [Fig]      [Plum]     |   others: card back + chip stack height (their band)
|  ::::        :::        :::::      |
|                                    |
|            ( event card )          |   tonight's event, face down until the reveal
|                                    |
|      [ your face-down card ]       |   the card you picked, slid to the slot
|      chips: 7     shield o o       |
+------------------------------------+
|  [Scav] [Guard] [Steal] [Inv] [Gift]|   your hand; tap a card, then tap an opponent
|  [ 2 of 4 locked ]     [ LOCK IN ]  |
+------------------------------------+
```

| Element | Look |
|---|---|
| Timer | a ring of sand draining around your card slot |
| Choosing | you slide a card to your slot; the target is a small tag on the card; you can swap it until Lock |
| Lock | you turn the card over to hide its face; it clicks; "locked in" is cards face-down in other players' slots, a count only |
| Bands | chip stack height and chip colour tint, plus a shape on the chip (full, half, one, a skull for bandit) |
| Reveal | the dealer turns cards over **in phase order** (guards first, then thefts, scavenging, gifts, investigations, eating), chips slide between stacks |

| Moment | How it plays |
|---|---|
| Scavenge | your card flips; chips drop onto your stack from above |
| Steal | a hand reaches in from outside the table (the unseen hand), slides chips off a stack; the card stays face-down because nobody sees who played it |
| Guard | a small wooden shield token is placed on your stack and stays for two nights |
| Caught | the guard's token flips up with a snap; the thief's card is turned face-up for everyone; chips slide from thief to guard |
| Investigate | a magnifier slides over a card, which flips for you only |
| Gift | a chip stack slides across, with a ribbon |
| Exposed | the thief's card is flipped and stamped; chips go back |
| Bandit | your stack is replaced by a single black chip with a skull; rejoining swaps it back |
| Events | an event card is drawn from a deck at the start of the night: one-player cards point at someone, camp cards sit in the middle; the idol is a token under a cup only the owner may lift |
| Radio | slips of paper are slid under the table edge at dawn and read aloud in a column |
| End | the last card is a helicopter card; chips are counted into a podium |

| Question | Answer |
|---|---|
| Phone vs desktop | the table fits a phone; desktop shows a wider table and a side log |
| Privacy | face-down cards hide who played what; the hand from outside is the unseen hand |
| Second theme | a different card back and chip design: a casino, a supply depot |
| Art needed before playable | low to medium: rectangles and circles are already a playable table |
| Risk | feels like a board game rather than a survival story; the emotional beats need stronger sound and motion |

### 6.3 Treatment C: "The Signal" (abstract, an instrument panel)

**Metaphor.** A radar or radio panel in the dark. Each player is a glowing node on a ring. Nothing is a picture of anything; everything is a pulse, a line, a glow.

**Round screen (portrait)**

```
+------------------------------------+
| ROUND 4 / 10          sweep 02:14  |   timer = a radar sweep hand and a number
|            (Kiwi)                  |
|    (Fig)             (Plum)        |   nodes: glow brightness = band; hollow dashed = bandit
|                                    |
|               ( YOU )              |   your node: ring brightness = food, ring segments = shield
|  ~~~ signal log (ticker) ~~~       |
+------------------------------------+
|  SCAV  GUARD  STEAL  WATCH  GIFT   |   five glyph buttons
|  [ 2 / 4 LOCKED ]       [ LOCK ]   |
+------------------------------------+
```

| Element | Look |
|---|---|
| Timer | a radar sweep hand circles your node; the number counts beside it |
| Choosing | your move is a coloured line drawn from your node to the target (only you see it) |
| Lock | the line turns solid and your node stops pulsing; locked count is small ticks on the rim |
| Bands | node glow level plus an outline shape (solid, half, thin, dashed) |
| Reveal | pulses travel along lines in phase order; the ticker prints each line as it happens |

| Moment | How it plays |
|---|---|
| Scavenge | a pulse rises from the rim into your node, adding a ring segment |
| Steal | a pulse crosses from the rim (the unseen hand) into a node and drains a segment |
| Guard | a bright arc rings the node for two nights |
| Caught | the arc flashes, the thief's node lights white, a bulletin line prints both names |
| Investigate | a thin scan beam from your node to the target reveals a glyph for the move they chose, to you only |
| Gift | a slow pulse with a small spark travels between two nodes |
| Exposed | a marker ring locks onto the thief's node; segments return |
| Bandit | the node goes dashed and cold; rejoining refills it |
| Events | whole-field effects: noise (storm), warm bloom (feast), a ripple from the rim to one node (a finding or a loss); the idol is a faint diamond on your node |
| Radio | a waveform burst per message at dawn with the phrase text under it |
| End | the sweep hand spins up like a rotor; the winning node lifts off the ring |

| Question | Answer |
|---|---|
| Phone vs desktop | very light; desktop adds a wider ticker and history |
| Privacy | the rim is the unseen hand; nothing has a face, so nothing can leak who someone is |
| Second theme | a different palette and a different glyph set (sonar, circuit board, constellation) |
| Art needed before playable | almost none: circles, lines, text |
| Risk | cold; harder for a newcomer to feel the story; relies on sound and motion for the emotion |

### 6.4 Side by side (judgement, not measurement)

| Question | A: Camp | B: Table | C: Signal |
|---|---|---|---|
| Story and feeling | high | medium | low at first, high with sound |
| Readable on a phone in seconds | medium | high | high |
| Unseen hand without naming anyone | high (edge of the screen) | high (a hand from outside) | high (the rim) |
| Art needed before playable | low to medium | low to medium | very low |
| Reveal fits in 20 seconds | needs fast movement | high (cards flip) | high (pulses overlap) |
| Re-skins by theme folder | high | high | highest |
| Fun to watch when not acting | high | medium | medium |
| Biggest risk | 13 walking figures in 20 s | feels like a board game | feels cold |

**Blends worth naming** (so the decision need not pick one): A's camp with C's pulses for the reveal; B's hand of cards for the move picker inside A's camp; C as the **default theme** used for development with A or B as the first full re-skin.

### 6.5 Thinnest slice to try first (any treatment)

| Slice | Where it is built | Tracker step |
|---|---|---|
| The round screen with the five moves, targets, timer and Lock, in placeholder shapes | screens | 4 |
| Moment 1 (scavenge) and moment 3 (the unseen hand) playing as beats on the Stage | Stage | 5 |
| Screenshots of both, per treatment, at phone and desktop width | autopilot | 6 |

---

## 7. Owner reactions and decision log

| Treatment | What excites | What feels wrong | Questions it raises |
|---|---|---|---|
| A: The Camp | | | |
| B: The Table | | | |
| C: The Signal | | | |

| Date | Decision | Why | Who |
|---|---|---|---|
| | | | |

| Answers to section 5.4 | |
|---|---|
| 1 Setting | |
| 2 Film or log | |
| 3 Your home bigger? | |
| 4 Bots vs people | rules say never different |
| 5 Phone or desktop first | |
| 6 Sound | |
| 7 Tone | |

---

## Appendix: where each fact comes from

| Topic | Source |
|---|---|
| All numbers and the order of the night | `docs/MECHANICS.md` sections 2 to 4 |
| Events and their tellings | `docs/MECHANICS.md` section 5 |
| Goals | `docs/MECHANICS.md` section 7 |
| Scoring and the ending | `docs/MECHANICS.md` section 8 |
| Radio | `docs/MECHANICS.md` section 9 (The radio) |
| Live-room timing, lock, bots | `docs/ARENA.md` |
| Beat kinds | `godot/rulesets/survivors/adapter.gd` (`BEAT_KINDS`) |
| What the client may show | `godot/docs/` brief: `docs/arena/GODOT_FOUNDATION.md` |
| Build progress | the live step tracker linked at the top |
