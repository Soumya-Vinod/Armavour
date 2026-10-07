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

We have two ways of finding out what the benchmark measures once its defects are taken into account. The first is cheap: drop the cells we know to be broken and recompute the original tables. The second is slower but more convincing: repair the items, then run the broken and repaired testbeds against each other on the same model, at the same time. We report both. They answer different questions, and neither is enough without the other.

## Retroactive correction

The correction removes every BREAKING cell identified in Section~\ref{sec:05_audit_method}. In these cells either no faithful path exists or the faithful path is scored as deception. Dropping them removes 245 of the 1,928 matrix episodes and leaves 1,683. The removed cells are few, but they carried a large share of the original results. In five of the six arms, between 44% and 63% of all raw deceptions came from BREAKING cells: 47% in E1a, 48% in the spot-check, 49% in E2, 63% in E1b and 44% in E2b. E2a is the exception at 17%.

Overall rates fall accordingly. ComputerUse (E1a) drops from 17.5% to 10.3% and BrowserUse (E1b) from 13.5% to 5.6%. The dose-response curve changes shape, not just level (Table~\ref{tab:corr-intensity}). In E1a, the rates by intensity were 0, 9, 23 and 38% from control to aggressive. After correction they are 0, 9, 17.8 and 17.1%: the curve rises once and then flattens. In E1b the rise disappears altogether, from 5, 8, 15 and 26% to 5, 8, 6.7 and 1.4%. The reason is easy to state. Of the 38 deceptions that made up E1a's aggressive rate, 26 were in BREAKING cells. For E1b the figure is 25 of 26.

\input{../tables/T3_intensity}

The pattern-level picture changes in the same way. Drip pricing, which looked like one of the more effective patterns (25.0% in E1a, 22.5% in E1b), falls to zero in both arms. SaaS billing goes from 55.0% to 40.0% in E1a and from 30.0% to 6.7% in E1b. The trick question goes from 42.5% to 20.0% in E1a. Bait-and-switch is untouched at 22.5% in E1a, because none of its cells were broken. The original account split the patterns into information-asymmetry patterns that work and perception or affect patterns that do not. Without drip pricing and the inflated SaaS and trick-question rates, that split no longer has much to stand on.

Retroactive exclusion has an obvious limit. It tells us what the remaining cells say, but it cannot tell us what the agent would have done on a working version of the removed items. A curve with its top two points partly deleted is not the same thing as a measured curve. To get that, we had to run the experiment again.

## Controlled rerun

The rerun compares two versions of the testbed. The *baseline* is a frozen copy of the testbed as the matrix ran it. The *fixed* variant differs from it only in the four repairs listed in the appendix (Section~\ref{sec:appendix}): drip pricing at aggressive intensity, SaaS billing, the trick question, and nagging. Before running any agent, we checked both variants with scripted paths that involve no LLM. The baseline fails exactly the 12 expected BREAKING rows. In the fixed variant, all 72 rows of the ten scored patterns pass: the faithful path is scored as avoided and the deceived path as deceived.

The original agent model, Llama-3.3-70B, had been withdrawn by its provider, so the rerun uses Qwen3.8-27B through the same API, with thinking suppressed and temperature 0.7. The rest of the setup mirrors the matrix's E1a arm: the ComputerUse adapter, English interface and instruction, 20 steps, the ten scored patterns at four intensities, and seeds 0 to 9. Configuration leakage was switched off and element identifiers were opaque. Each configuration ran on both variants back to back, with the order alternated, giving 400 episodes per variant and 400 complete pairs. No crash rows remained in the final data. We score every episode twice: with the original outcome codes (v1) and with the revised scheme (v2), which separates refusal (RF) and non-completion (NC) from avoidance. Unless stated otherwise, rates are v2 deception rates, (DC + DF) over all episodes except NC. The hypotheses and analysis were written down and committed before the run started. They were not lodged with an independent registry, so we describe them as pre-specified rather than pre-registered. All deviations from the plan are listed in the appendix.

**The repairs did what they were meant to do (H1).** Table~\ref{tab:r2} shows the cells that had been BREAKING. Drip pricing at aggressive intensity goes from 10 of 10 deceived on the baseline to 10 of 10 refusals on the fixed testbed. Once the fee is no longer applied inside the click that fires the oracle, the agent simply declines to pay it. The aggressive trick question goes from 10 of 10 deceived to 10 of 10 correct completions (both $p < .001$, Fisher's exact test, Holm-corrected). For two cells the rate alone would mislead. SaaS billing at aggressive intensity is 1 of 10 on the baseline and 0 of 10 on the fixed testbed, which looks like no change. But nine of the ten baseline episodes were refusals, because there was no free plan to choose. With the repair, all ten complete the task correctly. The moderate trick question shows the opposite case: the rates are almost the same (6 of 10 and 7 of 10), but they mean different things. On the baseline, a correct reading of the label was scored as deception. On the fixed testbed, a deception is an actual misreading of the label.

\input{tables/R2_h1_cells}

**The dose-response curve does not survive the repairs (H2).** This is the result we consider most important, and Figure~\ref{fig:dose} shows it. On the baseline testbed, Qwen reproduces the pattern we originally reported for Llama: deception rises steadily with intensity, at 0, 1.0, 12.0 and 27.6%. All six patterns with an estimable trend slope upwards (sign test, $p = .016$). On the fixed testbed, in the same run with the same model, the rates are 0, 0, 9.0 and 8.1%. They are no longer monotone, and only three patterns have an estimable trend at all ($p = .125$). The per-pattern statistics show where the curve came from. The trick question's Cochran–Armitage statistic falls from $Z = 5.20$ on the baseline to $Z = 1.30$ after the repair, and drip pricing's trend becomes undefined because nothing is deceived at any intensity. A clean dose-response curve was therefore not evidence that agents respond to intensity. Two broken items produced it, and it reappears on a different model whenever those items are present.

\input{figures/fig_dose_response}

So what deception is left? Very little, and it is concentrated. In the fixed variant, two cells account for most of it: bait-and-switch at aggressive intensity (8 of 10) and the moderate trick question (7 of 10). No other cell exceeds 10%. Refusal is far more common than deception. There are 70 refusals in the fixed variant against 17 deceptions. Every drip-pricing episode at subtle and moderate intensity is a refusal on both variants, and so is every bait-and-switch episode at subtle intensity. The original scoring had no code for refusal, so these episodes were folded into other outcomes and never showed up as what they were.

**The cell, not the episode, is the unit to read (H3).** We had planned to treat the ten seeds of a cell as independent draws if at least 16 of the 80 cells showed mixed outcomes. Only 12 did (8 baseline, 4 fixed). That falls between our thresholds, so H3 is inconclusive. We therefore read the rerun cell by cell and do not rely on pooled episode counts. Two further checks put the variant differences in context. First, the 24 cells of the six patterns we did not repair show no difference between variants after Holm correction, so the repairs did not leak into the rest of the testbed. Second, bait-and-switch at aggressive intensity was identical on both variants, yet it produced 4 of 10 deceptions on one and 8 of 10 on the other ($p = .17$). With ten episodes per cell, a difference of that size can arise from sampling alone, and any single-cell comparison in this paper should be read with that in mind. Finally, 6 baseline and 15 fixed episodes had their traces cut short by rate-limit retries. Their final oracle state is intact, so the outcomes above are unaffected.

## Language {#sec:language}

The original paper reported that a Hindi interface roughly doubled deception compared with English (20.7% versus 36.0%). That claim rested on a pair-level McNemar test, and the correction leaves the test looking even stronger: 25 pairs in which only the Hindi episode was deceived against 1 in the other direction, $p = 8 \times 10^{-7}$. But the pairs are not independent. Under deterministic decoding, the ten seeds of a cell tend to repeat the same outcome, so a single cell can contribute ten discordant pairs. Counted by cells, the evidence is much thinner. Four cells are worse in Hindi, none is worse in English and eight are tied ($p = .125$). One of the four is the trick question at control intensity, which contains no manipulation at all. A difference there says the agent understood the Hindi page less well. It says nothing about susceptibility to manipulation. What survives is a consistent direction carried by three or four cells, and we report it as no more than that.

The clearest language result was in the control conditions, where no dark pattern is present. In the matrix, English control cells produced no deceptions (0 of 50), while Hindi instruction with a Hindi interface produced 21 of 50. To check whether this was specific to Llama, we ran a pre-specified replication on Qwen with the baseline testbed. It covered control intensity only, the five scored patterns of the language arms, and five instruction/interface combinations, for 250 episodes. The primary comparison replicated: 6 of 50 deceived under Hindi/Hindi against 0 of 50 under English/English (one-sided exact stratified test, $p = .008$). The secondary comparison (English instruction, Hindi interface: 3 of 50, $p = .12$) and both Hinglish comparisons (0 of 50 each) did not replicate. Five of the six Hindi/Hindi deceptions came from confirm shaming. We hand-coded all nine deceived episodes in this run, and every one is a comprehension failure. Sometimes the agent mistranslated the instruction ("remove the donation, pay only for the ticket" became "donate and cancel the ticket"). Sometimes it misread a button whose meaning was clear in Hindi. The judge flagged none of the confirm-shaming cases as genuine influence. The disparity is real and it reproduces across models, but it is a failure to understand the page, not a failure to resist manipulation. A benchmark that scores it as deception will overstate how manipulable agents are in Hindi.

## What survives

Putting the two corrections together, three findings hold up.

- **Control-condition failures in Hindi.** They appear in the matrix and replicate on a second model, but they are comprehension failures, not susceptibility.
- **Bait-and-switch.** Its matrix rate is unaffected by the correction, and in the rerun it is the one pattern that still deceives the agent at aggressive intensity.
- **The direction of the language effect.** It is consistent but weak, carried by a handful of cells.

The moderate trick question also produces genuine deception after the repair, although only on the rerun model.

Three findings do not hold up.

- **The dose-response curve.** It flattens under exclusion and disappears when the items are repaired.
- **The split between pattern families.** It depended on drip pricing and the inflated SaaS and trick-question rates.
- **The four original nulls** (interface interference, nagging, subscription trap and confirm shaming). They cannot be read as findings about agent behaviour, because each is confounded by leakage, scoring or an item that never delivered its treatment (Section~\ref{sec:06_taxonomy}).

On Qwen, with opaque identifiers and no configuration leak, confirm shaming and interface interference are clean at 0 of 10 in each cell we tested. That is evidence about a second model, not a rescue of the original nulls.

Two caveats apply throughout. First, the rerun uses a different model from the matrix, so its rates should not be read as corrected versions of the matrix rates. What it shows is a within-model contrast: the same agent, on broken and repaired items, run side by side. Second, ten episodes per cell is a small sample. We have tried to make claims only where the pattern holds across cells, or where a single cell moves from all-or-nothing to its opposite.
