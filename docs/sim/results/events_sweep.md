# Wilderness events sweep

3000 games per row, same seeds 1..3000 in every row, current rules (game.json), 15 players, 10 nights. ± is the 95% margin. Personality cells are win share / seat rate as a multiple of a fair share (1.00 = fair). Food and weather columns are per game.

| Events | N5 leader takes a seat % | N5 leader wins % | Bandit comebacks / game | Alive at end (of 15) | Events fired / game | Food found / game | Food lost / game | Feast saved / game | Storm cost / game | Unbooked-food games | casual win× / seat× | farmer win× / seat× | opportunist win× / seat× | shark win× / seat× | paranoid win× / seat× | saint win× / seat× | detective win× / seat× | chaos win× / seat× |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| events off | 78.5 ±1.3 | 22.0 ±1.4 | 1.55 | 10.64 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 of 3000 | 0.88 / 1.09 | 0.98 / 1.09 | 1.34 / 1.19 | 1.57 / 1.30 | 1.15 / 1.17 | 0.75 / 0.36 | 0.57 / 0.74 | 0.75 / 0.49 |
| 0.5/night random | 77.9 ±1.4 | 21.9 ±1.4 | 1.54 | 10.72 | 4.94 | 2.22 | 2.90 | 4.77 | 2.72 | 0 of 3000 | 0.91 / 1.08 | 1.01 / 1.08 | 1.33 / 1.17 | 1.40 / 1.27 | 1.08 / 1.16 | 0.74 / 0.39 | 0.54 / 0.78 | 0.90 / 0.55 |
| 0.5/night trailing | 77.3 ±1.4 | 22.0 ±1.4 | 1.51 | 10.76 | 4.93 | 2.22 | 2.90 | 4.77 | 2.77 | 0 of 3000 | 0.85 / 1.08 | 0.98 / 1.08 | 1.36 / 1.18 | 1.41 / 1.27 | 1.17 / 1.17 | 0.85 / 0.40 | 0.58 / 0.76 | 0.82 / 0.51 |
| 1/night random | 76.5 ±1.4 | 20.2 ±1.3 | 1.48 | 10.85 | 9.82 | 4.41 | 5.67 | 9.39 | 5.64 | 0 of 3000 | 0.92 / 1.08 | 0.85 / 1.05 | 1.28 / 1.17 | 1.44 / 1.32 | 1.21 / 1.16 | 0.83 / 0.39 | 0.65 / 0.81 | 0.97 / 0.54 |
| 1/night trailing | 77.6 ±1.4 | 20.7 ±1.4 | 1.48 | 10.87 | 9.82 | 4.41 | 5.68 | 9.39 | 5.65 | 0 of 3000 | 0.87 / 1.09 | 0.90 / 1.07 | 1.32 / 1.17 | 1.53 / 1.33 | 1.17 / 1.14 | 0.77 / 0.38 | 0.67 / 0.78 | 0.95 / 0.54 |
| 2/night random | 75.4 ±1.4 | 20.9 ±1.4 | 1.43 | 10.92 | 19.63 | 8.88 | 11.29 | 18.02 | 11.00 | 0 of 3000 | 0.84 / 1.06 | 0.90 / 1.05 | 1.34 / 1.19 | 1.45 / 1.27 | 1.15 / 1.17 | 0.79 / 0.39 | 0.63 / 0.80 | 1.14 / 0.60 |
| 2/night trailing | 75.6 ±1.4 | 20.4 ±1.3 | 1.38 | 11.09 | 19.65 | 8.87 | 11.29 | 17.82 | 10.77 | 0 of 3000 | 0.84 / 1.07 | 0.95 / 1.06 | 1.29 / 1.18 | 1.58 / 1.27 | 1.12 / 1.18 | 0.72 / 0.39 | 0.67 / 0.78 | 1.02 / 0.57 |

What it shows:
- Even at 2 events a night the night-5 leader still takes a seat 75.4-75.6% and wins 20.4-20.9%, against 78.5% and 22.0% with events off: about 3 points less on seats, 1 to 2 on wins.
- Trailing bias is no different from random at any rate (seat and win gaps between the two are 1.1 points or less, inside the margin), so steering luck to the players behind does not show up at these event sizes.
- Comebacks fall from 1.55 to 1.38 per game and 0.45 more players are alive at the end (10.64 to 11.09) at 2 a night with trailing bias; at that rate events add 8.9 rations found and feasts save 17.8 per game.
- Shark keeps 1.40-1.58 times a fair share of wins and saint 0.36-0.40 times a fair share of seats in every row; only chaos moves (win 0.75 times fair with events off, 1.14 and 1.02 at 2 a night).
- Books balance: 0 of 21,000 games had food created or lost without a ledger line.
