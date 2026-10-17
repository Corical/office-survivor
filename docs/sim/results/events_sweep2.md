# Wilderness events sweep, round 2

6000 games per row, same seeds 1..6000 in every row, current rules (game.json), 15 players, 10 nights. ± is the 95% margin. Raid is drawn 4 x its library weight (about a fifth of all events); the last row draws it 12 x. Seat/win change is the per-seed difference from events off, so its margin is tighter than the two columns beside it. Personality columns are a multiple of a fair share (1.00 = fair).

| Design | N5 leader takes a seat % | N5 leader wins % | Seat change vs off (pts, paired) | Win change vs off (pts, paired) | Spearman N5 rations vs final score | Bandit comebacks / game | Alive at end (of 15) | Events fired / game | Rations moved by events / game | Biggest personality win× (who) | Smallest personality win× (who) | Biggest personality seat× (who) | Unbooked-food games |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| events off | 78.8 ±0.9 | 21.9 ±1.0 | - | - | 0.425 ±0.006 | 1.54 ±0.03 | 10.65 ±0.05 | 0.00 ±0.00 | 0.00 ±0.00 | 1.53 (shark) | 0.56 (detective) | 1.30 (shark) | 0 of 6000 |
| 0.5/night random (baseline) | 78.1 ±0.9 | 21.7 ±1.0 | -0.7 ±1.2 | -0.2 ±1.3 | 0.410 ±0.006 | 1.53 ±0.03 | 10.73 ±0.05 | 4.90 ±0.04 | 5.12 ±0.09 | 1.38 (shark) | 0.57 (detective) | 1.27 (shark) | 0 of 6000 |
| 0.5/night top | 76.9 ±1.0 | 21.1 ±1.0 | -1.9 ±1.2 | -0.8 ±1.2 | 0.401 ±0.006 | 1.52 ±0.03 | 10.84 ±0.05 | 4.82 ±0.04 | 5.11 ±0.09 | 1.37 (shark) | 0.58 (detective) | 1.29 (shark) | 0 of 6000 |
| 0.5/night raid | 77.0 ±1.0 | 20.8 ±1.0 | -1.8 ±1.3 | -1.1 ±1.3 | 0.401 ±0.006 | 1.56 ±0.03 | 10.57 ±0.05 | 4.92 ±0.04 | 6.08 ±0.09 | 1.40 (shark) | 0.56 (detective) | 1.26 (shark) | 0 of 6000 |
| 0.5/night rats-relative | 77.5 ±1.0 | 21.2 ±1.0 | -1.3 ±1.2 | -0.7 ±1.3 | 0.411 ±0.006 | 1.52 ±0.03 | 10.78 ±0.05 | 4.91 ±0.04 | 4.47 ±0.08 | 1.41 (opportunist) | 0.56 (detective) | 1.26 (shark) | 0 of 6000 |
| 0.5/night top + raid | 75.8 ±1.0 | 20.6 ±0.9 | -3.0 ±1.2 | -1.3 ±1.3 | 0.395 ±0.006 | 1.55 ±0.03 | 10.63 ±0.05 | 4.85 ±0.04 | 6.08 ±0.09 | 1.38 (shark) | 0.57 (detective) | 1.25 (shark) | 0 of 6000 |
| 0.5/night top + rats-relative | 77.3 ±1.0 | 21.5 ±1.0 | -1.5 ±1.2 | -0.4 ±1.3 | 0.405 ±0.006 | 1.50 ±0.03 | 10.88 ±0.05 | 4.82 ±0.04 | 4.48 ±0.08 | 1.41 (shark) | 0.56 (detective) | 1.27 (shark) | 0 of 6000 |
| 0.5/night raid + rats-relative | 77.0 ±1.0 | 20.3 ±0.9 | -1.8 ±1.3 | -1.6 ±1.3 | 0.408 ±0.006 | 1.54 ±0.03 | 10.58 ±0.05 | 4.92 ±0.04 | 5.65 ±0.08 | 1.43 (shark) | 0.59 (detective) | 1.27 (shark) | 0 of 6000 |
| 0.5/night top + raid + rats-relative | 75.3 ±1.0 | 19.7 ±0.9 | -3.5 ±1.3 | -2.2 ±1.3 | 0.398 ±0.006 | 1.53 ±0.03 | 10.68 ±0.05 | 4.86 ±0.04 | 5.66 ±0.08 | 1.39 (shark) | 0.62 (detective) | 1.23 (shark) | 0 of 6000 |
| 1/night random (baseline) | 76.6 ±1.0 | 21.1 ±1.0 | -2.2 ±1.3 | -0.8 ±1.3 | 0.399 ±0.006 | 1.48 ±0.03 | 10.80 ±0.06 | 9.82 ±0.01 | 10.16 ±0.12 | 1.41 (shark) | 0.62 (detective) | 1.29 (shark) | 0 of 6000 |
| 1/night top | 75.8 ±1.0 | 20.5 ±1.0 | -3.1 ±1.3 | -1.4 ±1.3 | 0.381 ±0.006 | 1.44 ±0.03 | 11.00 ±0.06 | 9.64 ±0.01 | 10.14 ±0.12 | 1.38 (opportunist) | 0.56 (detective) | 1.25 (shark) | 0 of 6000 |
| 1/night raid | 75.4 ±1.0 | 21.1 ±1.0 | -3.5 ±1.3 | -0.8 ±1.3 | 0.385 ±0.006 | 1.56 ±0.03 | 10.45 ±0.06 | 9.86 ±0.01 | 12.12 ±0.10 | 1.36 (shark) | 0.58 (detective) | 1.26 (shark) | 0 of 6000 |
| 1/night rats-relative | 76.8 ±1.0 | 20.8 ±1.0 | -2.0 ±1.3 | -1.1 ±1.3 | 0.407 ±0.006 | 1.45 ±0.03 | 10.85 ±0.06 | 9.83 ±0.01 | 9.07 ±0.10 | 1.39 (shark) | 0.65 (detective) | 1.26 (shark) | 0 of 6000 |
| 1/night top + raid | 73.9 ±1.0 | 18.9 ±0.9 | -4.9 ±1.3 | -2.9 ±1.3 | 0.371 ±0.006 | 1.51 ±0.03 | 10.58 ±0.06 | 9.71 ±0.01 | 12.12 ±0.10 | 1.42 (shark) | 0.61 (detective) | 1.25 (shark) | 0 of 6000 |
| 1/night top + rats-relative | 75.6 ±1.0 | 20.2 ±0.9 | -3.3 ±1.3 | -1.7 ±1.3 | 0.389 ±0.006 | 1.43 ±0.03 | 11.07 ±0.06 | 9.64 ±0.01 | 9.09 ±0.10 | 1.41 (shark) | 0.53 (detective) | 1.26 (shark) | 0 of 6000 |
| 1/night raid + rats-relative | 75.5 ±1.0 | 20.5 ±1.0 | -3.3 ±1.3 | -1.4 ±1.3 | 0.391 ±0.006 | 1.52 ±0.03 | 10.49 ±0.06 | 9.85 ±0.01 | 11.39 ±0.09 | 1.42 (shark) | 0.57 (detective) | 1.22 (shark) | 0 of 6000 |
| 1/night top + raid + rats-relative | 73.5 ±1.0 | 19.6 ±0.9 | -5.3 ±1.4 | -2.3 ±1.3 | 0.372 ±0.006 | 1.49 ±0.03 | 10.63 ±0.06 | 9.72 ±0.01 | 11.42 ±0.09 | 1.37 (shark) | 0.59 (detective) | 1.24 (shark) | 0 of 6000 |
| 1/night top + raid x12 + rats-relative | 71.7 ±1.0 | 18.6 ±0.9 | -7.2 ±1.4 | -3.3 ±1.3 | 0.357 ±0.006 | 1.57 ±0.03 | 10.07 ±0.06 | 9.80 ±0.01 | 13.98 ±0.09 | 1.31 (opportunist) | 0.56 (detective) | 1.18 (shark) | 0 of 6000 |

What it shows:
- The best rare design (1/night, top bias + raid + relative rats) lowers the night-5 leader's seat chance from 78.8 to 73.5 (-5.3 ±1.4 pts, paired) and win chance from 21.9 to 19.6 (-2.3 ±1.3); plain random events at 1/night give -2.2 ±1.3 and -0.8 ±1.3.
- Top bias alone at 1/night is 75.8 / 20.5 against 76.6 / 21.1 for random, inside the margins; the raid is what adds the extra pull (top + raid 73.9 / 18.9). At 0.5/night the best is -3.5 ±1.3 seat, -2.2 ±1.3 win.
- Spearman of night-5 rations against final score falls from 0.425 (off) to 0.371-0.372 for the two best 1/night designs and 0.357 with raids drawn 12 x; random 1/night is 0.399.
- Raids cost feel: rations moved by events go from 10.16 (random 1/night) to 12.12 (11.42 in the full combination), and alive at the end is 10.45-10.49 with plain raids at 1/night against 10.65 with events off (10.07 and 13.98 moved with raids drawn 12 x); top bias raises it to 11.00.
- No personality takes over: the biggest win multiple is 1.31-1.43 in every events row (shark 1.53 with events off), the smallest 0.53-0.65 (detective); books balance, 0 of 108,000 games with unbooked food.
