# Survivors

Everything for the office survival game, driven by one rules file. **New here? Read `HANDOVER.md` first.**

```
HANDOVER.md      status, decisions, full test history, open questions and next steps
docs/            snapshots of the rules doc and the video script doc (the live Claude docs are the masters)
game.json        every rule and number in the game (the one place to change things)
sim/             balance simulator, player brains, experiment runner and all results (sim/results/)
video/           explainer video kit: specs, captions and an agent brief, all generated from game.json
```

## Changing a rule

1. Edit `game.json`.
2. Check balance: `python3 sim/survivors_sim.py batch` and `python3 sim/survivors_sim.py extremes`.
3. Regenerate the video specs: `python3 video/build.py`. `video/build/TODO.md` lists only what the change affects.
4. Update the rules doc (Survivors: Office Game Rules) to match. It's written by hand.

## Making the video

Point the agent that has the Craft apps over MCP at `video/AGENT.md`. It covers the order, what each tool reads and writes, and how to mark work done so changes only redo what they touch.

## Simulator quick reference

```
python3 sim/survivors_sim.py reel                    one game as #news posts, with what really happened
python3 sim/survivors_sim.py batch --runs 100        stats over many games, with automatic warnings
python3 sim/survivors_sim.py extremes                players going all-in on one action
python3 sim/survivors_sim.py compare baseline v1_original steal_1
python3 sim/survivors_sim.py rules                   every knob, variant and personality
python3 sim/survivors_sim.py batch --brain adaptive  players that learn from what paid off
python3 sim/survivors_sim.py reel --brain jev --smart 5   Jev decides for 5 players (needs TYPESAFE_API_KEY)
python3 sim/experiments.py                           rerun the whole test history into sim/results/
python3 sim/check_invariants.py                      engine sanity checks
python3 sim/survivors_sim.py reel --log game.jsonl   write the complete replay log of one game
python3 sim/replay.py game.jsonl                     rebuild and tell a game from its log (--player, --frames, --check)
```

Everything is plain Python 3 with no installs.
