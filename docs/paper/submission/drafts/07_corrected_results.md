# Corrected Evidence

<!--
## 7 Corrected evidence (~2.5 pp) + Fig: dose-response baseline vs fixed (+ original curve)
7.1 Retroactive correction (exclude BREAKING cells; 245 rows) [CT]
- share of DC in broken cells: E1a 47, spot 48, E2 49, E1b 63, E2b 44, E2a 17% [T8]
- overall: E1a 17.5→10.3%; E1b 13.5→5.6% [T1]
- dose: E1a 0→9→17.8→17.1 (plateau); E1b 5→8→6.7→1.4 (none) [T3]
- patterns: drip 25→0; SaaS 55→40 (E1a), 30→6.7 (E1b); TQ 42.5→20; B&S unchanged [T4]
- limitation: exclusion ≠ measurement → motivates rerun
7.2 Controlled rerun (Qwen 3.8-27B, T=0.7, 800 episodes, same run, frozen baseline vs fixed) [RR]
- design: 4 fixes only (FIXES.md); interleaved per config; config leak off; scoring v1 + v2
- plan pre-specified, committed before run; not independently registered; deviations listed (appendix)
- H1 supported: drip agg 10/10 DC → 10/10 RF; TQ agg 10/10 DC → 10/10 EC
- SaaS agg: rate ~unchanged (1/10 vs 0/10) but distribution 9 RF → 10 EC (refusal → correct completion)
- TQ moderate: 60% vs 70% — same rate, different meaning (baseline inverted scoring; fixed genuine misreading)
- H2: baseline 0/1/12/27.6% monotone, sign 6+/0− p=.016; fixed 0/0/9.0/8.1% not monotone, 3+/0− p=.125
- → broken items manufacture dose-response on same model
- real deception after fix: B&S agg 80%, TQ moderate 70%; rest ≈0
- refusals common: drip subtle/mod/agg 10/10 RF both variants; B&S subtle 10/10 RF
- H3 inconclusive (12/80 cells mixed) → cell-level reading primary
- noise illustration: B&S agg 4/10 vs 8/10 on identical items (p=.17); untouched patterns: no drift after Holm
- retry-truncated traces 6/15; outcomes unaffected (deviation 5)
7.3 Language
- direction consistent: 4 Hindi-worse cells, 0 English-worse, 8 tied; sign test p=.125 [CT T6_sign]
- 1 of 4 cells is non-manipulative TQ control → comprehension, not susceptibility
- state as direction on 3–4 cells; pair-level p only with pseudo-replication caveat
7.4 What survives (short summary table or list)
- survives: baseline contamination; B&S effect; language direction (weak)
- does not: dose-response; pattern split; nulls as findings
- only on second model: CS/II clean 0/10 (ablation)
Reviewer challenges: different model in rerun vs matrix; small n per cell; retroactive vs rerun consistency.
-->


We have two ways of finding out what the benchmark measures. The first is cheap: we drop the cells we know are broken and refigure the original tables. The second is slower and much more convincing: we repair the items, then run the broken and repaired testbeds against each other on the same model, at the same time. We report both. They answer different questions, and neither is enough without the other.

## Retroactive correction

This correction removes every breaking cell identified in Section~\ref{sec:05_audit_method}: cells where either no faithful path exists or the faithful path is scored as deception. Dropping them removes 245 of the 1,600 scored matrix episodes and leaves 1,355, yet in five of the six arms these few cells held between 44% and 63% of all raw deceptions (47% in E1a, 48% in the spot-check, 49% in E2, 63% in E1b and 44% in E2b; E2a is the exception at 17%).

Overall the rates have fallen accordingly. ComputerUse (E1a) drops from 17.5% to 10.3% and BrowserUse (E1b) from 13.5% to 5.6% (Table~\ref{tab:v-t1} in the appendix). These two numbers can't be set against each other, though. In a post-hoc robustness analysis, we bounded each rate by how its unscored episodes are counted: E1a barely moves (10.3% to 11.1%), but E1b could be anywhere from 5.6% to 17.8%. On top of that, E1b's step budget is unknown. So the difference between ComputerUse and BrowserUse can't be interpreted, and we make no claim about it. Within each arm, the dose-response curve changes shape and not just level (Table~\ref{tab:v-t3} in the appendix): from control to aggressive, E1a goes from 0, 9, 23 and 38% to 0, 9, 17.8 and 17.1%, rising once and then flattening, and E1b's rise disappears, from 5, 8, 15 and 26% to 5, 8, 6.7 and 1.4%. The reason is simple: 26 of the 38 deceptions behind E1a's aggressive rate, and 25 of E1b's 26, were in breaking cells.

The pattern-level picture shows these changes in the same way. Drip pricing, which was observed as one of the most promising patterns (25.0% in E1a, 22.5% in E1b), falls to zero in both arms. On the other hand, SaaS billing goes from 55.0% to 40.0% in E1a and from 30.0% to 6.7% in E1b. The trick question goes from 42.5% to 20.0% in E1a. A post-hoc check shows that even that 20% (4 of 20) is not what it seems: all four deceptions were in the subtle cell, and in each one the harness ticked a box the agent had asked to leave alone, so if we honour what the agent meant to do, the rate is 0 of 20. Bait-and-switch is untouched at 22.5% in E1a, and that is because none of its cells were broken. The original account split the patterns into information-asymmetry patterns that work and perception or affect patterns that do not. Without drip pricing and the inflated SaaS and trick-question rates, that split no longer has much to stand on (Table~\ref{tab:v-t4} in the appendix).

Retroactive exclusion has an obvious limit: it can only tell us what the remaining cells say, not what the agent would have done on a working version of the removed items. A curve with its top two points partly deleted is not the same thing as a measured curve, and to get one we ran the experiment again.

## Controlled rerun

The rerun is used to compare two versions of the testbed. The *baseline* is a frozen copy of the testbed as the matrix ran it. The *fixed* variant differs from it only in the four repairs, which are listed in the appendix (Section~\ref{sec:appendix}): drip pricing at aggressive intensity, SaaS billing, the trick question, and finally nagging. Path checks confirmed that the baseline fails on exactly the 12 breaking combinations and the fixed variant passes all 72 (Appendix~\ref{app:paths}).

The original model is no longer available, so the rerun uses Qwen3.8-27B through the same API, with thinking suppressed and temperature 0.7. We ran each configuration on both variants back to back, alternating the order, which resulted in 400 episodes per variant and 400 complete pairs. No crash rows remained in the final data. We scored every episode twice: with the original outcome codes (v1) and with the revised scheme (v2), which separates refusal (RF) and non-completion (NC) from avoidance. The analysis plan was committed before the run but not independently registered, so we call it pre-specified; deviations are listed in Appendix~\ref{app:deviations}.

**The repairs did what they were meant to do (H1).** Table~\ref{tab:r2} shows the cells that had been breaking. Drip pricing at aggressive intensity goes from 10 of 10 deceived on the baseline to 10 of 10 refusals on the fixed testbed. Once the fee is no longer applied inside the click that fires the oracle, the agent simply declines to pay it. The aggressive trick question goes from 10 of 10 deceived to 10 of 10 correct completions (both $p < .001$, Fisher's exact test, Holm-corrected). For two cells the rate alone would mislead. SaaS billing at aggressive intensity is 1 of 10 on the baseline and 0 of 10 on the fixed testbed, which looks like no change. But nine of the ten baseline episodes were refusals, and the baseline offered no free plan. With the repair, all ten complete the task correctly. The moderate trick question shows the opposite case: the rates are almost the same (6 of 10 and 7 of 10), but they mean totally different things. On the baseline, a correct reading of the label was scored as deception, and on the fixed testbed, a deception is an actual misreading of the label.

\input{tables/R2_h1_cells}

**The dose-response curve does not survive the repairs (H2).** This is the result we consider most important, and Figure~\ref{fig:dose} shows it. On the baseline testbed, Qwen reproduces the pattern we originally reported for Llama: deception rises steadily with intensity, at 0, 1.0, 12.0 and 27.6%, and all six patterns with an estimable trend slope upwards (sign test, $p = .016$). On the fixed testbed, in the same run with the same model, the rates are 0, 0, 9.0 and 8.1%. This means that they are no longer monotone, and only three patterns have an estimable trend at all (sign test, $p = .125$). The per-pattern statistics show us where the curve came from. The trick question's Cochran–Armitage statistic falls from $Z = 5.20$ on the baseline to $Z = 1.30$ after the repair, and drip pricing's trend becomes undefined because nothing is deceived at any intensity. A clean dose-response curve was therefore not evidence that agents respond to intensity. It largely came from two broken items, and it reappears on the second model we tested whenever those items are present.

\input{figures/fig_dose_response}

So what deception is actually left? Very little, and it is concentrated in two cells of the fixed variant: bait-and-switch at aggressive intensity (8 of 10) and the moderate trick question (7 of 10). No other cell exceeds 10%. Refusal is far more common than deception: 70 refusals against 17 deceptions, including every drip-pricing episode at subtle and moderate intensity and every bait-and-switch episode at subtle intensity, on both variants. The original scoring had no code for refusal, so these episodes were folded into other outcomes and never showed up as what they were.

**The cell, not the episode, is the unit to read (H3).** Only 12 of the 80 cells were mixed, between our thresholds of 8 and 16, so H3 is inconclusive and the cell-level view is primary: the pooled rates above are descriptive, and the main evidence is the sign test across patterns. The 24 cells of the six untouched patterns, identical in both variants, showed no difference after Holm correction, so the run did not drift in any large way. But one of them shows how large noise can be: bait-and-switch at aggressive intensity gave 4 of 10 deceptions on one variant and 8 of 10 on the other ($p = .17$). So the repairs explain the two aggressive cells that went from 10 of 10 to 0 of 10, far beyond that noise, but smaller differences between variants cannot be attributed to them. Rate-limit retries truncated the traces, not the outcomes, of 21 episodes (Appendix~\ref{app:deviations}, Deviation 5).

## Language {#sec:language}

The original analysis reported that a Hindi interface roughly doubled deception when compared to English (20.7% versus 36.0%). That claim rested on a pair-level McNemar test, and the correction makes the test look even stronger: 25 pairs in which only the Hindi episode was deceived against 1 in the other direction, $p = 8 \times 10^{-7}$. But the pairs are not independent. Under deterministic decoding, the ten seeds of a cell tend to repeat the same outcome, so a single cell can contribute ten discordant pairs. When counted by cells, the evidence is much thinner: four cells are worse in Hindi, none is worse in English and eight are tied ($p = .125$). One of the four was the trick question at control intensity, which contained no manipulation at all. A difference there says that the agent understood the Hindi page less well than the English one, but says nothing about susceptibility to manipulation. But counting cells undersells the result: in a post-hoc analysis, a GEE with cells as clusters gives the Hindi interface an odds ratio of 4.35 against English (95% CI 2.41 to 7.83), and resampling whole cells puts the difference at +20 points (5.0 to 36.7). Hinglish does not hold up the same way: its odds ratio is 2.20, and the interval (0.82 to 5.92) includes 1. Two caveats remain. There are only 12 clusters, and one of the cells behind the Hindi effect is the trick-question control.

The clearest language result was in the control conditions with no dark pattern present. In the matrix, English control cells produced no deceptions (0 of 50) whereas Hindi instruction with a Hindi interface produced 21 of 50. To check whether this was specific to Llama, we ran a pre-specified replication on Qwen with the baseline testbed. This covered control intensity only, the five scored patterns of the language arms, and five instruction/interface combinations, 250 episodes in all. The primary comparison replicated: 6 of 50 deceived under Hindi/Hindi against 0 of 50 under English/English (one-sided exact stratified test, $p = .008$). The secondary comparison (English instruction, Hindi interface: 3 of 50, $p = .12$) and both Hinglish comparisons (0 of 50 each) did not replicate. Refusals also went up when the interface was in Hindi: 2 of 50 under English/English, but 10 of 50 with an English instruction and a Hindi interface. We report this only descriptively. Five of the six Hindi/Hindi deceptions came from confirm shaming. We hand-coded all nine deceived episodes in this run, and every one of them was a comprehension failure. Sometimes the agent mistranslated the instruction (for example, "remove the donation, pay only for the ticket" became "donate and cancel the ticket"). Other times it misread a button whose meaning was very clear in Hindi. In five of the nine, the agent's intent was right and it simply misread a label, as when episode 174 read "automatic renewal after the trial" as "disable trial after free period" and decided to tick it. In one (episode 159), the harness's own context text misled it (Section~\ref{sec:06_taxonomy}). The judge flagged none of these confirm-shaming cases as genuine influence. The two models also failed in different ways. Llama mostly reasoned in Hindi, and badly: in all ten of its confirm-shaming failures the reasoning is malformed Hindi, misspelt and full of repeated words, and eight of its ten interface-interference failures were reasoned in Hindi too.<!-- TODO(author): native-speaker check needed. Read the ten Llama hi/hi confirm_shaming control traces (ids 2974-2983, REVIEW_ANALYSES.md §B) and confirm "malformed Hindi" yourself; the classification there is Claude Code's, not yours. The 8/10 interface-interference count (ids 3028-3035 in Hindi, 3036-3037 in English) matches the traces. --> Qwen reasoned in English and got the translation wrong. The harm to the user is the same, but the cause is different. The disparity is real, and it reproduces on one more model. On that model it is much smaller (6 of 50 against 21 of 50) and comes mostly from one pattern, confirm shaming. Interface interference, 10 of 10 for Llama, did not replicate (0 of 10). And in the end it is a failure to understand the page, not a failure to resist manipulation.

## What survives

When we put the two corrections together, three findings hold up:

- **Control-condition failures in Hindi.** They appear in the matrix and replicate on a second model, but they are comprehension failures and not susceptibility.
- **Bait-and-switch.** The matrix rate is unaffected by the correction, and in the rerun it is the one pattern that still deceives the agent at aggressive intensity.
- **The Hindi-interface effect.** It holds when clustering is accounted for (odds ratio 4.35, 2.41 to 7.83), though it rests on 12 cells, one of them a control. The Hinglish effect does not.

The moderate trick question also produces genuine deception after the repair, although only on the rerun model.

Three findings do not hold up.

- **The dose-response curve, as published.** Some of it remains, but far less than we reported. In a post-hoc check that keeps the same patterns at every intensity and re-scores the trick question, E1a still rises (0, 5, 15 and 20%; sign test $p = .031$). However, that rise comes mainly from bait-and-switch and forced action, and the cluster-bootstrap intervals are wide (3.8% to 42.5% at aggressive intensity). E1b shows no rise at all, and the rerun is not monotone once the items are repaired.
- **The split between pattern families.** It depended on drip pricing and the inflated SaaS and trick-question rates.
- **The four original nulls** (interface interference, nagging, subscription trap and confirm shaming). These cannot be read as findings about agent behaviour, because each is confounded by leakage, scoring or an item that never delivered its treatment (Section~\ref{sec:06_taxonomy}).

Confirm shaming and interface interference were clean on Qwen (0 of 10 in each cell tested), but that, like the whole rerun, is a within-model contrast on a second model with ten episodes per cell, not a corrected matrix rate.
