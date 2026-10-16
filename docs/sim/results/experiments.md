# Experiment results

300 simulated games per config and office mix, seed 7, 15 players, 10 nights. Regenerate with `python3 sim/experiments.py`.

Columns: **Alive** = survivors at the end (of 15). **Died** = players who hit zero at some point. **Back** = bandit comebacks. **Catch** = share of steals caught by a guard. **Robs** = robberies per night. **Quiet** = nights with no robbery, catch or death. **Coin** = last seat decided by coin flip. **Thief seats** = share of seats won by players with 3+ steals. **Turtle/Thief** = one player who only guards-when-unprotected / only steals, in a normal office: share of wins vs fair (1.0) and how often they get a seat. **Balance** = weakest and strongest personality, win share vs fair, default office.

## 1. First draft

The rules as first written.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1_first_draft | 7.0 | 11.2 | 5.5 | 13% | 2.6 | 0.3 | 38% | 50% | 1.08x, 39% | 1.92x, 56% | saint 0.68 / shark 1.35 |

## 2. Single fixes on the first draft

One change at a time, to see what each knob does.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| start_7 | 10.9 | 6.2 | 2.9 | 15% | 2.0 | 0.6 | 55% | 34% | 0.57x, 19% | 2.43x, 87% | saint 0.33 / shark 1.97 |
| scavenge_1_2 | 12.4 | 4.6 | 2.5 | 15% | 2.1 | 0.5 | 59% | 31% | 0.07x, 5% | 1.85x, 67% | saint 0.29 / shark 1.56 |
| scavenge_0_3 | 11.7 | 6.1 | 3.7 | 15% | 2.2 | 0.4 | 52% | 30% | 0.13x, 6% | 1.39x, 59% | paranoid 0.34 / shark 1.51 |
| guard_reward_1 | 7.5 | 10.7 | 5.3 | 14% | 2.5 | 0.3 | 42% | 46% | 1.28x, 53% | 1.98x, 60% | saint 0.74 / shark 1.37 |
| guard_income_0_1 | 8.6 | 9.6 | 5.0 | 14% | 2.4 | 0.4 | 52% | 44% | 0.66x, 29% | 1.86x, 61% | chaos 0.62 / shark 1.48 |
| harsh_catch | 7.1 | 11.1 | 5.5 | 14% | 2.5 | 0.3 | 41% | 46% | 1.71x, 51% | 1.74x, 51% | saint 0.86 / shark 1.41 |
| steal_1 | 6.2 | 10.5 | 2.8 | 14% | 2.6 | 0.4 | 35% | 41% | 1.43x, 41% | 0.52x, 15% | chaos 0.47 / casual 1.32 |
| bandit_rejoin_5 | 4.5 | 12.0 | 2.5 | 14% | 2.6 | 0.3 | 22% | 58% | 1.53x, 33% | 2.38x, 44% | detective 0.73 / shark 1.51 |
| bandit_steal_1 | 6.4 | 10.5 | 3.2 | 14% | 2.6 | 0.3 | 39% | 51% | 1.29x, 37% | 2.73x, 64% | saint 0.57 / shark 1.75 |
| guard_2_nights | 6.7 | 11.1 | 4.8 | 21% | 2.3 | 0.3 | 43% | 40% | 1.03x, 39% | 1.30x, 42% | saint 0.66 / shark 1.12 |
| kindness_tiebreak | 7.0 | 11.2 | 5.5 | 13% | 2.6 | 0.3 | 22% | 50% | 1.04x, 37% | 1.86x, 53% | saint 0.71 / shark 1.33 |
| objectives_give3_rob2 | 6.4 | 11.6 | 5.4 | 14% | 2.7 | 0.2 | 39% | 53% | 1.02x, 38% | 2.15x, 52% | saint 0.69 / shark 1.37 |
| missed_deadline_0_1 | 5.2 | 12.8 | 5.9 | 13% | 2.6 | 0.3 | 30% | 57% | 1.95x, 51% | 1.86x, 43% | casual 0.85 / shark 1.18 |
| investigate_bounty_1 | 6.7 | 11.3 | 5.4 | 13% | 2.5 | 0.3 | 34% | 47% | 0.86x, 35% | 1.43x, 44% | saint 0.78 / shark 1.31 |

## 3. Combined packages

Economy fix + slower bandits + 2-night guard + kindness tiebreak + easier objectives.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tuned_a_start7 | 10.2 | 5.9 | 1.6 | 26% | 2.0 | 0.4 | 20% | 32% | 0.51x, 30% | 2.59x, 68% | saint 0.29 / shark 1.96 |
| tuned_b_scavenge1_2 | 11.6 | 4.5 | 1.5 | 24% | 2.0 | 0.3 | 19% | 26% | 0.23x, 17% | 1.90x, 48% | chaos 0.10 / shark 1.51 |
| tuned_c_scavenge0_3 | 10.4 | 6.0 | 2.0 | 25% | 2.2 | 0.2 | 17% | 26% | 0.56x, 28% | 1.21x, 36% | chaos 0.12 / shark 1.57 |
| tuned_a+missed_0_1 | 9.0 | 7.1 | 1.6 | 25% | 2.1 | 0.3 | 26% | 35% | 0.95x, 42% | 2.88x, 74% | chaos 0.39 / shark 2.14 |
| tuned_a+bounty | 10.1 | 6.0 | 1.5 | 27% | 1.9 | 0.4 | 15% | 31% | 0.56x, 30% | 1.53x, 50% | saint 0.33 / shark 1.68 |
| tuned_c+missed_0_1 | 8.2 | 8.4 | 2.4 | 24% | 2.3 | 0.2 | 11% | 37% | 0.72x, 50% | 1.61x, 44% | chaos 0.38 / shark 1.89 |
| tuned_c+bounty | 10.5 | 5.8 | 1.8 | 25% | 2.1 | 0.2 | 14% | 26% | 0.40x, 27% | 1.30x, 31% | chaos 0.23 / casual 1.26 |

## 4. First recommendation (R1) and variants

R1 = start 7, bandits steal 1, 2-night guard, thief pays guard 2, kindness tiebreaks, easier objectives.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | 10.4 | 5.7 | 1.6 | 28% | 1.9 | 0.4 | 16% | 25% | 0.77x, 79% | 1.83x, 50% | detective 0.43 / shark 1.37 |
| R1_no_winner_tiebreak | 10.4 | 5.7 | 1.6 | 28% | 1.9 | 0.4 | 16% | 25% | 0.86x, 79% | 1.63x, 50% | saint 0.32 / shark 1.62 |
| R1_rations_win_ties | 10.4 | 5.7 | 1.6 | 28% | 1.9 | 0.4 | 16% | 25% | 1.88x, 79% | 2.68x, 50% | saint 0.02 / shark 1.80 |
| R1+steal_1 | 10.8 | 5.2 | 1.3 | 25% | 1.9 | 0.4 | 19% | 16% | 0.68x, 73% | 0.33x, 13% | detective 0.41 / paranoid 1.44 |
| R1+catch_3 | 10.2 | 6.1 | 1.8 | 26% | 1.9 | 0.3 | 11% | 24% | 1.30x, 89% | 1.37x, 37% | detective 0.41 / shark 1.66 |
| R1+gift_bonus | 11.2 | 5.2 | 1.9 | 27% | 1.8 | 0.4 | 12% | 23% | 0.98x, 78% | 1.58x, 57% | chaos 0.64 / shark 1.54 |
| R1+bounty | 10.4 | 5.7 | 1.4 | 28% | 1.9 | 0.4 | 15% | 25% | 1.08x, 83% | 1.40x, 40% | saint 0.33 / opportunist 1.29 |

## 5. Fixing the turtle loophole in R1

R1's 2-night guard let players guard, scavenge, repeat. Candidate fixes.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1+guard_1_night | 10.7 | 5.7 | 1.7 | 18% | 2.1 | 0.4 | 18% | 32% | 0.40x, 37% | 2.38x, 73% | detective 0.43 / shark 1.68 |
| R1+guard_1_night+income | 11.6 | 4.6 | 1.6 | 17% | 2.1 | 0.5 | 16% | 31% | 1.00x, 74% | 3.00x, 75% | detective 0.45 / shark 2.06 |
| R1+guard_limit_3 | 10.6 | 5.6 | 1.7 | 25% | 1.9 | 0.4 | 16% | 27% | 0.25x, 38% | 2.05x, 53% | detective 0.48 / shark 1.71 |
| R1+guard_limit_4 | 10.4 | 5.7 | 1.6 | 28% | 1.9 | 0.4 | 15% | 26% | 0.73x, 52% | 1.75x, 50% | detective 0.43 / shark 1.37 |
| R1+cooldown_1 | 10.6 | 5.6 | 1.7 | 24% | 2.0 | 0.3 | 18% | 30% | 1.02x, 62% | 1.36x, 61% | detective 0.16 / shark 2.08 |
| R1+cooldown_2 | 10.9 | 5.4 | 1.8 | 19% | 2.1 | 0.3 | 19% | 33% | 0.62x, 56% | 2.42x, 67% | detective 0.39 / shark 1.99 |
| R1+guard_1_night+limit_3 | 11.0 | 5.4 | 1.8 | 14% | 2.2 | 0.4 | 24% | 36% | 0.30x, 25% | 3.00x, 78% | detective 0.54 / shark 1.90 |
| R1+guard_1_night+limit_4 | 10.7 | 5.7 | 1.8 | 16% | 2.2 | 0.4 | 19% | 34% | 0.05x, 18% | 2.33x, 74% | detective 0.48 / shark 1.73 |
| R1+limit_3+catch_3 | 10.5 | 6.0 | 1.9 | 24% | 2.0 | 0.3 | 17% | 26% | 0.67x, 45% | 1.65x, 42% | detective 0.36 / shark 1.59 |
| R1+limit_4+catch_3 | 10.2 | 6.1 | 1.9 | 26% | 1.9 | 0.3 | 12% | 25% | 1.14x, 62% | 1.47x, 37% | detective 0.41 / shark 1.61 |
| R1+limit_3+steal_1 | 10.9 | 5.2 | 1.4 | 24% | 2.0 | 0.4 | 22% | 18% | 0.80x, 54% | 0.15x, 12% | detective 0.36 / paranoid 1.33 |
| R1+limit_3+bounty = v2 | 10.6 | 5.6 | 1.5 | 25% | 1.9 | 0.4 | 19% | 27% | 0.27x, 33% | 1.20x, 45% | detective 0.59 / shark 1.44 |

## 6. Current rules

v2 as written in game.json, and the open steal-size dial.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2_current | 10.6 | 5.6 | 1.5 | 25% | 1.9 | 0.4 | 19% | 27% | 0.27x, 33% | 1.20x, 45% | detective 0.59 / shark 1.44 |
| v2+steal_1 | 11.2 | 4.8 | 1.3 | 23% | 1.9 | 0.4 | 18% | 16% | 0.45x, 53% | 0.10x, 7% | chaos 0.48 / farmer 1.40 |

## Secret objective completion (default office)

| Config | Beat @player | Robbed + extract | Steal 3 clean | Give away | Grudge |
| --- | --- | --- | --- | --- | --- |
| v1_first_draft | 39% | 18% | 33% | 0% | 70% |
| objectives_give3_rob2 | 40% | 17% | 33% | 6% | 8% |
| R1 | 45% | 28% | 14% | 36% | 40% |
| v2_current | 46% | 29% | 16% | 34% | 40% |

## Balance across office mixes (weakest / strongest personality, win share vs fair)

| Config | Default office | Honest office | Cutthroat office |
| --- | --- | --- | --- |
| v1_first_draft | saint 0.68 / shark 1.35 | saint 0.61 / shark 1.39 | saint 0.81 / shark 1.09 |
| tuned_a_start7 | saint 0.29 / shark 1.96 | saint 0.44 / opportunist 1.69 | chaos 0.38 / shark 1.64 |
| R1 | detective 0.43 / shark 1.37 | chaos 0.22 / opportunist 1.59 | detective 0.17 / paranoid 1.85 |
| R1+guard_limit_3 | detective 0.48 / shark 1.71 | chaos 0.32 / opportunist 1.87 | detective 0.24 / paranoid 1.59 |
| R1+limit_3+bounty = v2 | detective 0.59 / shark 1.44 | detective 0.60 / opportunist 1.72 | detective 0.49 / paranoid 1.68 |
| v2+steal_1 | chaos 0.48 / farmer 1.40 | chaos 0.32 / casual 1.31 | shark 0.41 / paranoid 1.74 |
