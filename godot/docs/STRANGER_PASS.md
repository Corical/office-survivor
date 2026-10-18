# Stranger pass: review the game as a first-time player

You are a player who has never seen this game. You did not build it, you have not read its code, tests or design notes,
and you must not. Your only job is to launch the real build, use it the way a person would, and write down everything
that feels wrong, off, slow, ugly, confusing or broken. Be hostile. "Looks fine" is not a finding.

Previous reviews of this game were done from code, headless tests and still screenshots, and they missed things a
player saw in seconds: a laggy logo, button text sitting low on the button, a red "can't reach the server" banner on
first launch because the default address was wrong, a banner that looked like failure while merely connecting.
Assume more of that is still there.

## What the game is (one paragraph, enough to play)

A live 4-player survival game. Each round ("night") every player secretly picks a move (Forage, Keep watch, Stake out,
Steal, Give), most moves also need a target player, then everyone locks in. A timer runs. Then a reveal plays what
happened. After 10 nights the end screen ranks the players. It is played over the network against a server.

## Run the real build

| Item | Value |
|---|---|
| Windows build | `C:\Personal\office-survivor\godot\build\windows\SurvivorsArena.exe` (there is also `SurvivorsArena.console.exe`, which shows a console with the log) |
| Server | already set as the default: `wss://raspberrypi.tail87b476.ts.net:8470` (tailnet only; this PC reaches it) |
| Window | start it full screen (Alt+Enter) AND windowed at roughly phone shape (540x960) |
| Reset to a first launch | delete the folder `%APPDATA%\Godot\app_userdata\Survivors Arena` before starting |
| Android | `godot\build\android\SurvivorsArena.apk` if a phone is available (`adb install -r`) |

If the exe is missing or stale, ask the owner to rebuild it; do not rebuild or edit code yourself.

You need four players for a full game. Run four copies of the exe (one creates a camp, three join with the code), or
ask the owner whether bots are available on the server. Playing the first round or two is enough for most checks.

## Rules for you

- Do NOT read source code, tests, docs/MECHANICS.md or any design notes. A stranger would not have them.
- Do NOT fix anything. Report only.
- Do NOT create rooms on the server more than needed; it is the owner's real server.
- Judge only what you can see, hear, measure or time yourself. Say how you measured.

## The checklist (cover every row; add rows as you find things)

| Area | Look for |
|---|---|
| First launch | Does the first screen make sense in 3 seconds? Is there an error, red text or a warning before you did anything? What happens on the first tap of Create camp: how long until something responds, and what does it show while waiting? |
| Connection states | Connecting, connected, failed and reconnecting must each look different and proportionate. Calm while connecting; alarming only when it is a real failure. Pull the network (disable the adapter for 20 s) and watch what the player is told. |
| Motion and smoothness | Every moving thing: the logo bobbing, button presses, screen transitions, the timer, the reveal animation, embers and clouds. Does anything stutter, jitter, shimmer, pop or lag? Capture it: `ffmpeg -f gdigrab -framerate 30 -t 10 -i desktop out.mp4`, then step through frames (`ffmpeg -i out.mp4 -vf fps=30 f_%03d.png`) and compare consecutive frames of the logo and the timer. Note frame-to-frame jumps. Run it with `SurvivorsArena-new.console.exe --print-fps` and report the frames per second on each screen. |
| Text and alignment | For every button and label: is the text visually centred on the lit face of the button, horizontally and vertically? Zoom into screenshots. Is any text clipped, overlapping a border, wrapping oddly, too small to read on a phone, or low contrast against the background? Use the longest name you can type. |
| Touch and size | Phone size: is every tap target large enough for a thumb? Anything hidden behind the bottom dock or off-screen that you have to scroll to find? |
| Round screen | Can you tell, without instructions, what to do? What is selected and what is not? Is it obvious when you are locked in, and who else is locked? Does the timer feel urgent at the end? |
| Reveal | Can you follow what happened? Does the animation match the text log? Do any labels, numbers or effects overlap or land in the wrong place? Is anything shown that a player should not know (another player's exact food, who is a bot)? |
| End screen | Is the ranking clear, including ties? Is anything cut off? Can you get back to the start? |
| Wide window | Full screen on a large monitor: dead space, tiny elements, or stretched art? |
| Settings | Does each setting do what it says? Does it survive a restart? (Known: reduced motion does not.) |
| Errors | Anything in the console window: warnings, errors, repeated lines. Copy them exactly. |
| Overall | Would you keep playing? Would it pass as a game on the Play Store? What is the single thing that most breaks that? |

## Report format

Reply with one table, worst first, then the verdict. No introduction.

| # | Severity (blocker / major / minor) | Where (screen, state, window size) | What you saw | How to reproduce | Evidence (file path of a screenshot or frame) |
|---|---|---|---|---|---|

Then three lines:

1. **Verdict:** would a stranger keep playing, yes or no, and the one reason.
2. **Not checked:** everything on the checklist you could not do, and why.
3. **Surprises:** anything not on the checklist that you noticed.

Save the screenshots and frames you reference in a folder named `stranger-pass-<date>` next to your report and give
full paths.
