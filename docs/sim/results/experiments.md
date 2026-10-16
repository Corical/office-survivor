# Experiment results

300 simulated games per config and office mix, seed 7, 15 players, 10 nights. Regenerate with `python3 sim/experiments.py`.

Columns: **Alive** = survivors at the end (of 15). **Died** = players who hit zero at some point. **Back** = bandit comebacks. **Catch** = share of steals caught by a guard. **Robs** = robberies per night. **Quiet** = nights with no robbery, catch or death. **Coin** = last seat decided by coin flip. **Thief seats** = share of seats won by players with 3+ steals. **Turtle/Thief** = one player who only guards-when-unprotected / only steals, in a normal office: share of wins vs fair (1.0) and how often they get a seat. **Balance** = weakest and strongest personality, win share vs fair, default office.

## 1. First draft

The rules as first written.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1_first_draft | 7.1 | 11.2 | 5.6 | 13% | 2.6 | 0.3 | 39% | 49% | 0.88x, 37% | 1.92x, 54% | saint 0.73 / shark 1.38 |

## 2. Single fixes on the first draft

One change at a time, to see what each knob does.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| start_7 | 10.9 | 6.2 | 2.9 | 16% | 2.0 | 0.6 | 55% | 34% | 0.63x, 19% | 2.46x, 87% | saint 0.35 / shark 2.07 |
| scavenge_1_2 | 12.4 | 4.6 | 2.6 | 15% | 2.1 | 0.5 | 59% | 32% | 0.07x, 5% | 1.84x, 67% | saint 0.29 / shark 1.54 |
| scavenge_0_3 | 11.8 | 6.0 | 3.7 | 15% | 2.2 | 0.4 | 51% | 30% | 0.14x, 7% | 1.43x, 60% | paranoid 0.41 / shark 1.50 |
| guard_reward_1 | 7.9 | 10.6 | 5.4 | 14% | 2.5 | 0.3 | 47% | 45% | 1.24x, 58% | 2.04x, 58% | detective 0.77 / shark 1.40 |
| guard_income_0_1 | 8.7 | 9.5 | 5.0 | 14% | 2.4 | 0.4 | 53% | 45% | 0.54x, 26% | 1.88x, 62% | chaos 0.58 / shark 1.57 |
| harsh_catch | 7.3 | 11.1 | 5.6 | 14% | 2.5 | 0.3 | 36% | 46% | 1.34x, 58% | 1.74x, 52% | saint 0.69 / shark 1.46 |
| steal_1 | 6.2 | 10.5 | 2.8 | 13% | 2.6 | 0.4 | 35% | 42% | 1.53x, 41% | 0.51x, 16% | chaos 0.47 / casual 1.28 |
| bandit_rejoin_5 | 4.6 | 12.0 | 2.5 | 14% | 2.6 | 0.3 | 23% | 58% | 1.68x, 34% | 2.47x, 43% | chaos 0.83 / shark 1.46 |
| bandit_steal_1 | 6.4 | 10.5 | 3.2 | 14% | 2.6 | 0.3 | 41% | 52% | 1.26x, 38% | 2.66x, 63% | saint 0.44 / shark 1.86 |
| guard_2_nights | 6.8 | 11.0 | 4.8 | 21% | 2.3 | 0.3 | 41% | 42% | 1.05x, 41% | 1.43x, 41% | chaos 0.57 / shark 1.21 |
| kindness_tiebreak | 7.1 | 11.2 | 5.6 | 13% | 2.6 | 0.3 | 23% | 48% | 0.89x, 36% | 1.82x, 50% | saint 0.76 / shark 1.35 |
| objectives_give3_rob2 | 6.6 | 11.6 | 5.5 | 14% | 2.7 | 0.2 | 39% | 55% | 0.98x, 40% | 2.18x, 52% | chaos 0.68 / opportunist 1.39 |
| missed_deadline_0_1 | 5.3 | 12.8 | 6.0 | 13% | 2.6 | 0.3 | 32% | 56% | 1.54x, 52% | 2.00x, 44% | casual 0.82 / shark 1.23 |
| investigate_bounty_1 | 6.8 | 11.3 | 5.5 | 14% | 2.6 | 0.3 | 38% | 47% | 0.79x, 36% | 1.45x, 47% | saint 0.70 / shark 1.35 |

## 3. Combined packages

Economy fix + slower bandits + 2-night guard + kindness tiebreak + easier objectives.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tuned_a_start7 | 10.3 | 5.9 | 1.6 | 26% | 2.0 | 0.4 | 21% | 32% | 0.51x, 29% | 2.55x, 66% | saint 0.33 / shark 1.85 |
| tuned_b_scavenge1_2 | 11.7 | 4.5 | 1.5 | 24% | 2.0 | 0.3 | 17% | 26% | 0.27x, 15% | 1.90x, 49% | chaos 0.12 / shark 1.47 |
| tuned_c_scavenge0_3 | 10.6 | 5.9 | 2.1 | 25% | 2.2 | 0.2 | 17% | 26% | 0.65x, 29% | 1.22x, 37% | chaos 0.16 / shark 1.52 |
| tuned_a+missed_0_1 | 9.1 | 7.2 | 1.7 | 25% | 2.1 | 0.3 | 24% | 37% | 0.93x, 41% | 2.82x, 75% | chaos 0.41 / shark 2.16 |
| tuned_a+bounty | 10.2 | 5.9 | 1.5 | 27% | 1.9 | 0.4 | 14% | 31% | 0.51x, 30% | 1.56x, 51% | saint 0.28 / shark 1.73 |
| tuned_c+missed_0_1 | 8.3 | 8.3 | 2.4 | 24% | 2.3 | 0.2 | 14% | 37% | 0.83x, 49% | 1.67x, 47% | chaos 0.44 / shark 1.82 |
| tuned_c+bounty | 10.6 | 5.8 | 1.8 | 25% | 2.1 | 0.2 | 14% | 26% | 0.46x, 26% | 1.30x, 32% | chaos 0.22 / casual 1.27 |

## 4. First recommendation (R1) and variants

R1 = start 7, bandits steal 1, 2-night guard, thief pays guard 2, kindness tiebreaks, easier objectives.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | 10.6 | 5.6 | 1.6 | 28% | 1.9 | 0.4 | 17% | 25% | 1.07x, 86% | 1.55x, 50% | detective 0.48 / shark 1.42 |
| R1_no_winner_tiebreak | 10.6 | 5.6 | 1.6 | 28% | 1.9 | 0.4 | 17% | 25% | 0.93x, 86% | 1.73x, 50% | saint 0.39 / shark 1.62 |
| R1_rations_win_ties | 10.6 | 5.6 | 1.6 | 28% | 1.9 | 0.4 | 17% | 25% | 1.92x, 86% | 2.58x, 50% | saint 0.06 / paranoid 1.86 |
| R1+steal_1 | 11.0 | 5.0 | 1.3 | 26% | 1.9 | 0.4 | 19% | 16% | 1.02x, 83% | 0.14x, 11% | detective 0.50 / paranoid 1.39 |
| R1+catch_3 | 10.6 | 5.8 | 1.8 | 26% | 1.9 | 0.3 | 13% | 24% | 1.55x, 94% | 1.04x, 34% | detective 0.39 / paranoid 1.72 |
| R1+gift_bonus | 11.4 | 5.1 | 1.9 | 28% | 1.8 | 0.4 | 12% | 24% | 1.08x, 84% | 1.51x, 55% | detective 0.56 / paranoid 1.42 |
| R1+bounty | 10.6 | 5.5 | 1.4 | 27% | 1.9 | 0.4 | 18% | 24% | 1.55x, 88% | 1.05x, 38% | saint 0.49 / shark 1.27 |

## 5. Fixing the turtle loophole in R1

R1's 2-night guard let players guard, scavenge, repeat. Candidate fixes.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1+guard_1_night | 10.8 | 5.6 | 1.7 | 18% | 2.2 | 0.4 | 15% | 31% | 0.67x, 50% | 2.48x, 70% | detective 0.47 / shark 1.84 |
| R1+guard_1_night+income | 11.7 | 4.5 | 1.6 | 17% | 2.1 | 0.5 | 16% | 31% | 1.15x, 83% | 2.99x, 76% | detective 0.43 / shark 1.86 |
| R1+guard_limit_3 | 10.9 | 5.4 | 1.7 | 25% | 1.9 | 0.4 | 15% | 27% | 0.32x, 36% | 1.85x, 54% | detective 0.60 / shark 1.49 |
| R1+guard_limit_4 | 10.7 | 5.6 | 1.6 | 27% | 1.9 | 0.4 | 16% | 26% | 1.02x, 56% | 1.53x, 51% | detective 0.54 / shark 1.42 |
| R1+cooldown_1 | 10.7 | 5.6 | 1.7 | 24% | 2.0 | 0.3 | 16% | 29% | 1.18x, 66% | 1.06x, 60% | detective 0.23 / shark 1.66 |
| R1+cooldown_2 | 11.0 | 5.3 | 1.8 | 20% | 2.1 | 0.3 | 16% | 33% | 0.72x, 59% | 2.22x, 68% | saint 0.49 / shark 2.00 |
| R1+guard_1_night+limit_3 | 11.1 | 5.3 | 1.8 | 14% | 2.3 | 0.4 | 25% | 35% | 0.30x, 24% | 2.60x, 77% | detective 0.49 / shark 1.88 |
| R1+guard_1_night+limit_4 | 10.8 | 5.6 | 1.8 | 16% | 2.2 | 0.4 | 15% | 34% | 0.05x, 19% | 2.62x, 75% | paranoid 0.49 / shark 1.88 |
| R1+limit_3+catch_3 | 10.8 | 5.8 | 1.9 | 24% | 2.0 | 0.3 | 16% | 25% | 0.93x, 47% | 1.38x, 44% | detective 0.41 / shark 1.94 |
| R1+limit_4+catch_3 | 10.6 | 5.9 | 1.9 | 26% | 1.9 | 0.3 | 14% | 24% | 1.10x, 69% | 1.15x, 35% | detective 0.41 / paranoid 1.59 |
| R1+limit_3+steal_1 | 11.1 | 5.0 | 1.4 | 24% | 2.0 | 0.4 | 19% | 17% | 0.65x, 57% | 0.21x, 12% | detective 0.37 / farmer 1.40 |
| R1+limit_3+bounty = v2 | 10.9 | 5.3 | 1.5 | 24% | 2.0 | 0.4 | 18% | 26% | 0.33x, 36% | 1.04x, 41% | saint 0.57 / shark 1.43 |

## 6. Current rules

v2 as written in game.json, and the open steal-size dial.

| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2_current | 10.9 | 5.3 | 1.5 | 24% | 2.0 | 0.4 | 18% | 26% | 0.33x, 36% | 1.04x, 41% | saint 0.57 / shark 1.43 |
| v2+steal_1 | 11.4 | 4.7 | 1.4 | 23% | 2.0 | 0.4 | 17% | 16% | 0.54x, 54% | 0.12x, 7% | detective 0.49 / paranoid 1.33 |

## Secret objective completion (default office)

| Config | Beat @player | Robbed + extract | Steal 3 clean | Give away | Grudge |
| --- | --- | --- | --- | --- | --- |
| v1_first_draft | 40% | 17% | 35% | 0% | 69% |
| objectives_give3_rob2 | 41% | 18% | 35% | 6% | 9% |
| R1 | 47% | 27% | 14% | 37% | 40% |
| v2_current | 48% | 29% | 17% | 35% | 40% |

## Balance across office mixes (weakest / strongest personality, win share vs fair)

| Config | Default office | Honest office | Cutthroat office |
| --- | --- | --- | --- |
| v1_first_draft | saint 0.73 / shark 1.38 | saint 0.57 / shark 1.53 | saint 0.84 / casual 1.15 |
| tuned_a_start7 | saint 0.33 / shark 1.85 | saint 0.46 / opportunist 1.72 | saint 0.32 / shark 1.59 |
| R1 | detective 0.48 / shark 1.42 | chaos 0.43 / opportunist 1.59 | detective 0.41 / paranoid 1.78 |
| R1+guard_limit_3 | detective 0.60 / shark 1.49 | chaos 0.38 / opportunist 1.84 | detective 0.33 / paranoid 1.55 |
| R1+limit_3+bounty = v2 | saint 0.57 / shark 1.43 | detective 0.56 / opportunist 1.82 | detective 0.36 / paranoid 1.70 |
| v2+steal_1 | detective 0.49 / paranoid 1.33 | chaos 0.22 / casual 1.21 | shark 0.38 / paranoid 1.78 |
