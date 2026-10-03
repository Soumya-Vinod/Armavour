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
