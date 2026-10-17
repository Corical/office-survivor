# Rations visibility sweep

3000 games per row, same seeds 1..3000 in every row, current rules (game.json), 15 players, 10 nights, no wilderness events. ± is the 95% margin; the 'change vs today' columns are per-seed differences from the first row, so their margins are tighter than the columns beside them. Ranges 7/3/1 = well fed 7+, getting by 3-6, starving 1-2, bandit; ranges 9/5/2 = 9+, 5-8, 2-4, 1, bandit. Human memory = follows 3 players closely (2 by recent dealings, 1 random), estimates of the rest close 40% of the gap to the camp average each night without news, a guard is forgotten 25% of the time and never remembered for players not followed. Blind hit = a theft attempt on a player holding 2 or fewer rations at the start of that night. Personality columns are a multiple of a fair share (1.00 = fair).

| Visibility / memory | N5 leader takes a seat % | N5 leader wins % | Seat change vs today (pts, paired) | Win change vs today (pts, paired) | Spearman N5 rations vs final score | Bandits created / game | Theft attempts / game | Blind hits (target <= 2 rations) / game | Blind-hit change vs today (paired) | Bandit comebacks / game | Alive at end (of 15) | Biggest personality win× (who) | Smallest personality win× (who) | Biggest personality seat× (who) | Unbooked-food games |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden / bot-accurate (today) | 78.5 ±1.3 | 22.0 ±1.4 | - | - | 0.422 ±0.008 | 5.92 ±0.08 | 33.63 ±0.33 | 3.86 ±0.10 | - | 1.55 ±0.04 | 10.64 ±0.07 | 1.57 (shark) | 0.57 (detective) | 1.30 (shark) | 0 of 3000 |
| hidden / human | 80.5 ±1.3 | 23.2 ±1.4 | +2.0 ±1.7 | +1.2 ±1.8 | 0.442 ±0.008 | 5.92 ±0.08 | 33.59 ±0.32 | 4.15 ±0.10 | +0.3 ±0.1 | 1.58 ±0.04 | 10.66 ±0.07 | 1.40 (shark) | 0.58 (detective) | 1.22 (paranoid) | 0 of 3000 |
| ranges 7/3/1 / bot-accurate | 70.0 ±1.5 | 18.4 ±1.3 | -8.5 ±2.0 | -3.6 ±1.9 | 0.344 ±0.009 | 4.82 ±0.08 | 31.33 ±0.32 | 0.86 ±0.05 | -3.0 ±0.1 | 1.15 ±0.04 | 11.33 ±0.07 | 1.34 (shark) | 0.52 (detective) | 1.15 (opportunist) | 0 of 3000 |
| ranges 7/3/1 / human | 70.3 ±1.5 | 20.3 ±1.3 | -8.2 ±2.0 | -1.7 ±1.9 | 0.389 ±0.008 | 5.25 ±0.08 | 32.12 ±0.32 | 2.00 ±0.07 | -1.9 ±0.1 | 1.28 ±0.04 | 11.03 ±0.07 | 1.43 (shark) | 0.56 (detective) | 1.17 (paranoid) | 0 of 3000 |
| exact / bot-accurate | 57.0 ±1.6 | 17.4 ±1.3 | -21.5 ±2.1 | -4.5 ±1.9 | 0.277 ±0.010 | 4.23 ±0.08 | 29.94 ±0.32 | 0.70 ±0.04 | -3.2 ±0.1 | 0.99 ±0.04 | 11.76 ±0.08 | 1.24 (opportunist) | 0.66 (detective) | 1.16 (casual) | 0 of 3000 |
| exact / human | 57.7 ±1.7 | 16.7 ±1.3 | -20.8 ±2.1 | -5.2 ±1.9 | 0.323 ±0.009 | 4.59 ±0.08 | 30.47 ±0.31 | 1.10 ±0.05 | -2.8 ±0.1 | 1.06 ±0.04 | 11.47 ±0.07 | 1.31 (opportunist) | 0.53 (detective) | 1.18 (casual) | 0 of 3000 |
| ranges 9/5/2 / bot-accurate | 64.0 ±1.6 | 18.6 ±1.3 | -14.5 ±2.0 | -3.4 ±1.9 | 0.321 ±0.009 | 4.86 ±0.08 | 31.33 ±0.32 | 1.43 ±0.06 | -2.4 ±0.1 | 1.22 ±0.04 | 11.36 ±0.07 | 1.46 (shark) | 0.57 (detective) | 1.15 (opportunist) | 0 of 3000 |
| ranges 9/5/2 / human | 67.8 ±1.5 | 18.4 ±1.3 | -10.7 ±2.0 | -3.6 ±1.9 | 0.386 ±0.008 | 5.21 ±0.08 | 32.14 ±0.32 | 2.38 ±0.08 | -1.5 ±0.1 | 1.34 ±0.04 | 11.13 ±0.07 | 1.35 (opportunist) | 0.57 (detective) | 1.18 (paranoid) | 0 of 3000 |

## What it shows

- Ranges 7/3/1 cut blind hits from 3.86 to 0.86 a game with bot-accurate players and to 2.00 with human memory, and bandits created from 5.92 to 4.82 and 5.25.
- The early leader takes a seat 8.5 and 8.2 points less often (78.5 to 70.0 and 70.3); the win drop is 3.6 ±1.9 bot-accurate but only 1.7 ±1.9 human, so not clearly different from zero.
- Exact numbers cut the leader's seat chance to 57.0 and 57.7 but win chance only to 17.4 and 16.7; it is the strongest effect, and it also leaves the fewest bandit comebacks (0.99 and 1.06 against 1.55).
- Hidden with human memory is no different from today (seat +2.0 ±1.7, win +1.2 ±1.8), so forgetful players alone change little; ranges 9/5/2 does less than 7/3/1 on blind hits (1.43 and 2.38).
- No personality dominates in any row (biggest win multiple 1.57, shark today, 1.46 or less with visibility), and every game balanced the books (0 unbooked in 24000).
