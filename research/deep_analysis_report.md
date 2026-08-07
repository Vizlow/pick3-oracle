# Deep pattern analysis — NY Numbers (Pick 3)

Generated 2026-08-07T05:17:36+00:00 · history through `2026-08-06-eve` · skill window: last 4000 draws · BH-FDR q < 0.1

## Honest framing

NY Numbers is drawn from audited physical machines. The prior is overwhelmingly that no exploitable signal exists; with ~80 battery p-values, ~4 raw p<0.05 are expected under the global null, which is why only FDR-surviving, era-stable, split-half-consistent findings count. Ball sets change over the years, so only the last-4000-draw era (2021→) is actionable; full-history findings are historical curiosities.

## A. Draw bias battery

0 of 81 tests significant after FDR.

No test survived FDR — the drawn numbers are statistically indistinguishable from uniform in every way tested.


<details><summary>All battery results</summary>

| test | n | stat | df | p | q |
|---|---|---|---|---|---|
| all:pos0_digit_uniform | 25647 | 9.518 | 9 | 0.3909 | 0.8601 |
| all:pos1_digit_uniform | 25647 | 10.77 | 9 | 0.292 | 0.8601 |
| all:pos2_digit_uniform | 25647 | 6.027 | 9 | 0.7372 | 0.9267 |
| all:pooled_digit_uniform | 25647 | 9.135 | 9 | 0.4249 | 0.8601 |
| all:sum_distribution | 25647 | 26.94 | 27 | 0.4672 | 0.8601 |
| all:structure_mix | 25647 | 8.551 | 2 | 0.01391 | 0.5632 |
| all:pos0_serial_dependence | 25647 | 86.08 | 81 | 0.3287 | 0.8601 |
| all:pos1_serial_dependence | 25647 | 69.65 | 81 | 0.8116 | 0.9267 |
| all:pos2_serial_dependence | 25647 | 98.16 | 81 | 0.09424 | 0.6539 |
| all:straight_repeat | 25647 | 29 | 0 | 0.5577 | 0.9219 |
| all:box_repeat | 25647 | -0.844 | 0 | 0.3986 | 0.8601 |
| all:carryover_count | 25647 | 2.121 | 3 | 0.5477 | 0.9219 |
| all:weekday_digit | 25647 | 42.46 | 54 | 0.872 | 0.9402 |
| all:dueness_positional_digits | 25647 | 1.107 | 4 | 0.8931 | 0.9402 |
| all:dueness_front_pairs | 25647 | 1.667 | 4 | 0.7968 | 0.9267 |
| all:dueness_back_pairs | 25647 | 8.068 | 4 | 0.08911 | 0.6539 |
| last4000:pos0_digit_uniform | 4000 | 22.98 | 9 | 0.006253 | 0.5065 |
| last4000:pos1_digit_uniform | 4000 | 9.1 | 9 | 0.4281 | 0.8601 |
| last4000:pos2_digit_uniform | 4000 | 7.16 | 9 | 0.6205 | 0.9267 |
| last4000:pooled_digit_uniform | 4000 | 8.217 | 9 | 0.5125 | 0.9024 |
| last4000:sum_distribution | 4000 | 25.35 | 25 | 0.4431 | 0.8601 |
| last4000:structure_mix | 4000 | 2.349 | 2 | 0.3089 | 0.8601 |
| last4000:pos0_serial_dependence | 4000 | 62.49 | 81 | 0.9368 | 0.9606 |
| last4000:pos1_serial_dependence | 4000 | 72.46 | 81 | 0.7401 | 0.9267 |
| last4000:pos2_serial_dependence | 4000 | 75.5 | 81 | 0.6517 | 0.9267 |
| last4000:straight_repeat | 4000 | 1 | 0 | 0.1831 | 0.7914 |
| last4000:box_repeat | 4000 | -1.868 | 0 | 0.0617 | 0.6539 |
| last4000:carryover_count | 4000 | 2.868 | 3 | 0.4124 | 0.8601 |
| last4000:weekday_digit | 4000 | 47.77 | 54 | 0.7122 | 0.9267 |
| last4000:mid_vs_eve_digit | 4000 | 12.97 | 9 | 0.1641 | 0.7914 |
| last4000:dueness_positional_digits | 4000 | 2.785 | 4 | 0.5944 | 0.9267 |
| last4000:dueness_front_pairs | 4000 | 5.123 | 4 | 0.2749 | 0.8601 |
| last4000:dueness_back_pairs | 4000 | 1.449 | 4 | 0.8356 | 0.9272 |
| last1000:pos0_digit_uniform | 1000 | 10.28 | 9 | 0.3283 | 0.8601 |
| last1000:pos1_digit_uniform | 1000 | 14.22 | 9 | 0.1147 | 0.6637 |
| last1000:pos2_digit_uniform | 1000 | 7.36 | 9 | 0.5997 | 0.9267 |
| last1000:pooled_digit_uniform | 1000 | 10.08 | 9 | 0.344 | 0.8601 |
| last1000:sum_distribution | 1000 | 22.51 | 23 | 0.4895 | 0.8811 |
| last1000:structure_mix | 1000 | 0.0204 | 2 | 0.9899 | 0.9899 |
| last1000:pos0_serial_dependence | 1000 | 71.13 | 81 | 0.7753 | 0.9267 |
| last1000:pos1_serial_dependence | 1000 | 86.03 | 81 | 0.3302 | 0.8601 |
| last1000:pos2_serial_dependence | 1000 | 96.65 | 81 | 0.1131 | 0.6637 |
| last1000:straight_repeat | 1000 | 0 | 0 | 0.7361 | 0.9267 |
| last1000:box_repeat | 1000 | -1.831 | 0 | 0.06708 | 0.6539 |
| last1000:carryover_count | 1000 | 0.6931 | 2 | 0.7071 | 0.9267 |
| last1000:weekday_digit | 1000 | 56.94 | 54 | 0.3664 | 0.8601 |
| last1000:dueness_positional_digits | 1000 | 4.538 | 4 | 0.3381 | 0.8601 |
| last1000:dueness_front_pairs | 1000 | 2.291 | 4 | 0.6823 | 0.9267 |
| last1000:dueness_back_pairs | 1000 | 1.012 | 4 | 0.908 | 0.9429 |
| mid2000:pos0_digit_uniform | 2000 | 14.79 | 9 | 0.09687 | 0.6539 |
| mid2000:pos1_digit_uniform | 2000 | 15.75 | 9 | 0.07229 | 0.6539 |
| mid2000:pos2_digit_uniform | 2000 | 5.05 | 9 | 0.8299 | 0.9272 |
| mid2000:pooled_digit_uniform | 2000 | 15.47 | 9 | 0.07873 | 0.6539 |
| mid2000:sum_distribution | 2000 | 25 | 25 | 0.4622 | 0.8601 |
| mid2000:structure_mix | 2000 | 2.03 | 2 | 0.3623 | 0.8601 |
| mid2000:pos0_serial_dependence | 2000 | 77.17 | 81 | 0.5999 | 0.9267 |
| mid2000:pos1_serial_dependence | 2000 | 70.91 | 81 | 0.7808 | 0.9267 |
| mid2000:pos2_serial_dependence | 2000 | 90.47 | 81 | 0.221 | 0.8523 |
| mid2000:straight_repeat | 2000 | 0 | 0 | 0.2707 | 0.8601 |
| mid2000:box_repeat | 2000 | -1.319 | 0 | 0.1872 | 0.7914 |
| mid2000:carryover_count | 2000 | 3.879 | 3 | 0.2748 | 0.8601 |
| mid2000:weekday_digit | 2000 | 48.99 | 54 | 0.6677 | 0.9267 |
| mid2000:dueness_positional_digits | 2000 | 1.831 | 4 | 0.7668 | 0.9267 |
| mid2000:dueness_front_pairs | 2000 | 1.103 | 4 | 0.8937 | 0.9402 |
| mid2000:dueness_back_pairs | 2000 | 0.5764 | 4 | 0.9656 | 0.9777 |
| eve2000:pos0_digit_uniform | 2000 | 13.24 | 9 | 0.152 | 0.7914 |
| eve2000:pos1_digit_uniform | 2000 | 8.71 | 9 | 0.4645 | 0.8601 |
| eve2000:pos2_digit_uniform | 2000 | 4.62 | 9 | 0.8661 | 0.9402 |
| eve2000:pooled_digit_uniform | 2000 | 5.81 | 9 | 0.7588 | 0.9267 |
| eve2000:sum_distribution | 2000 | 36.47 | 25 | 0.06481 | 0.6539 |
| eve2000:structure_mix | 2000 | 1.252 | 2 | 0.5346 | 0.9213 |
| eve2000:pos0_serial_dependence | 2000 | 72.99 | 81 | 0.7251 | 0.9267 |
| eve2000:pos1_serial_dependence | 2000 | 86.43 | 81 | 0.3193 | 0.8601 |
| eve2000:pos2_serial_dependence | 2000 | 75.24 | 81 | 0.6596 | 0.9267 |
| eve2000:straight_repeat | 2000 | 1 | 0 | 0.8123 | 0.9267 |
| eve2000:box_repeat | 2000 | -1.95 | 0 | 0.05124 | 0.6539 |
| eve2000:carryover_count | 2000 | 4.708 | 3 | 0.1945 | 0.7914 |
| eve2000:weekday_digit | 2000 | 62.69 | 54 | 0.1954 | 0.7914 |
| eve2000:dueness_positional_digits | 2000 | 4.061 | 4 | 0.3978 | 0.8601 |
| eve2000:dueness_front_pairs | 2000 | 2.054 | 4 | 0.7257 | 0.9267 |
| eve2000:dueness_back_pairs | 2000 | 10.13 | 4 | 0.03829 | 0.6539 |

</details>

## B. Tactic skill (walk-forward, empirical per-draw nulls)

| tactic | kind | n | mean r | z | z h1 | z h2 | top50 z | p | q | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| carryover | tactic | 4000 | 0.4993 | -0.177 | 1.05 | -1.301 | -0 | 0.8599 | 0.956 | noise |
| datesum_key | tactic | 4000 | 0.4938 | -1.46 | -0.628 | -1.436 | -1.108 | 0.1444 | 0.5627 | noise |
| due_digits | tactic | 4000 | 0.5051 | 1.119 | 0.175 | 1.408 | 1.176 | 0.263 | 0.5627 | noise |
| follower_digit | tactic | 4000 | 0.4909 | -2 | -1.039 | -1.79 | -0.855 | 0.04548 | 0.5457 | noise |
| follower_pair | tactic | 4000 | 0.4979 | -0.704 | 0.015 | -1.011 | -0.811 | 0.4815 | 0.6798 | noise |
| hot_digits | tactic | 4000 | 0.4968 | -0.71 | 0.512 | -1.517 | -1.088 | 0.4775 | 0.6798 | noise |
| mirror_cloud | tactic | 4000 | 0.4982 | -1.249 | 0.346 | -2.116 | 0 | 0.2116 | 0.5627 | noise |
| pair_due | tactic | 4000 | 0.5051 | 1.107 | 1.451 | 0.114 | -0.215 | 0.2685 | 0.5627 | noise |
| pattern_balance | tactic | 4000 | 0.503 | 0.659 | -0.614 | 1.546 | 0.855 | 0.5101 | 0.6801 | noise |
| rundown_111 | tactic | 4000 | 0.4981 | -1.131 | -0.534 | -1.065 | -1.101 | 0.2583 | 0.5627 | noise |
| rundown_123_stack | tactic | 4000 | 0.5008 | 0.347 | 0.996 | -0.505 | 1.596 | 0.7289 | 0.8747 | noise |
| rundown_317 | tactic | 4000 | 0.4993 | -0.393 | -0.981 | 0.425 | 1.094 | 0.6946 | 0.8747 | noise |
| rundown_pi | tactic | 4000 | 0.5002 | 0.107 | 1.319 | -1.167 | 0.32 | 0.915 | 0.956 | noise |
| structure_due | tactic | 4000 | 0.4962 | -1.06 | -0.902 | -0.597 | -0.598 | 0.289 | 0.5627 | noise |
| sum_due | tactic | 4000 | 0.5043 | 0.939 | 0.187 | 1.14 | 0.312 | 0.3478 | 0.5963 | noise |
| ttt_mirror | tactic | 4000 | 0.4941 | -2.342 | -0.801 | -2.509 | -2.671 | 0.01918 | 0.4602 | noise |
| ttt_plus1 | tactic | 4000 | 0.4962 | -1.405 | -1.059 | -0.928 | -1.896 | 0.1601 | 0.5627 | noise |
| vtrac_due | tactic | 4000 | 0.5054 | 1.191 | -0.397 | 2.081 | 0.217 | 0.2337 | 0.5627 | noise |
| vtrac_return | tactic | 4000 | 0.4975 | -1.76 | 0.087 | -2.58 | 0 | 0.07837 | 0.5627 | noise |
| fused_equal | ensemble | 4000 | 0.4991 | -1.026 | -0.134 | -1.317 | None | 0.3048 | 0.5627 | noise |
| fused_learned | ensemble | 4000 | 0.499 | -1.036 | -0.305 | -1.149 | None | 0.3001 | 0.5627 | noise |
| top5_picks_box | picks | 4000 | 0.0297 | -0.034 | 0.568 | -0.615 | None | 0.9732 | 0.9732 | noise |
| pairs_front | pairs | 4000 | 0.0103 | 0.159 | None | None | None | 0.9162 | 0.956 | noise |
| pairs_back | pairs | 4000 | 0.0112 | 0.795 | None | None | None | 0.4666 | 0.6798 | noise |

## Headlines

- Draw bias battery: 0 of 81 tests significant after FDR — draws look uniform
- Tactic skill: 0 of 19 tactics beat their empirical null — all noise, as honest math predicts
- Ensemble: learned-weights z=-1.036, equal-weights z=-1.026 — weight learning adds nothing measurable
- Top-5 picks hit boxes at 3.0% per draw vs 3.0% coverage ceiling (z=-0.034)

## Method notes

- Skill metric: tactic's Borda points for the actual combo vs the mean/variance of its own full 1000-combo Borda vector that draw (tie-correct: pool tactics' per-draw sigma is ~0.07, not the tie-free 0.289 — assuming Var=1/12 would mis-scale their z by ~4x).
- No look-ahead: skill rides the backtest walk-forward loop (sentinel-tested); dueness walkers update last-seen strictly after scoring.
- Verdict rule was fixed in code before the numbers were run: signal iff q<0.10 AND same-sign z in both halves of the window.


## C. Parameter tuning protocol (engine/tuner.py)

Pre-registered before the holdout was touched: train = draws -6000..-2001, holdout =
last 2000 draws, run exactly once. Grid: alpha=0.02, tau in {0,6,12,24} x floor in
{0.1,0.3,0.6}.

Result: all 10 grid points landed within 1 SE of each other on train (any-box rate
3.10%-3.33%) — in an all-noise world the parameters don't matter, exactly as family B
predicts. The stability-first candidate (tau=0, frozen equal weights) then failed the
holdout P&L gate by $80 (-2840 vs -2760 net; box rate 2.65% vs 2.80%, both within
noise of the 3.0% ceiling). Verdict per the pre-stated acceptance rule: KEEP INCUMBENT
(alpha=0.02, tau=12, floor=0.3). No constants were changed.

Full numbers: research/tuning_results.json

## Actions taken from this analysis

1. select_picks max_per_box 2 -> 1 (committed 58e32d8, before this analysis): the one
   real defect found — ~80% of live draws wasted a slot on a permutation of an
   already-picked box. Walk-forward confirms picks now sit at the 3.0% coverage
   ceiling (top5_picks_box mean 2.97%, z=-0.03).
2. Weight-learning constants kept as-is per the tuning protocol above.
3. Tactic verdicts + battery summary surfaced on the dashboard (Pattern lab panel,
   site/data/analysis.json) so the honest-tracking story includes its own autopsy.
