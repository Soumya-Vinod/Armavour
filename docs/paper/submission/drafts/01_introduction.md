# Introduction

<!--
## 1 Introduction (~1.5 pp)
Purpose: problem → what we built → what audit found → contributions.
- dark patterns: designs steering users against own interest [Mathur, Gray, Brignull]
- regulators codifying: CCPA 2023, 13 patterns [CCPA]
- agents shopping/subscribing on users' behalf → manipulation target shifts
- benchmarks = instrument for "do dark patterns work on agents" [TrickyArena, SusBench, Tang]
- benchmark validity must be shown, not assumed [Jacobs & Wallach; Raji]
- we built one; first run gave clean findings (list three)
- audit result headline: dose-response carried by forced/inverted cells
- strongest single fact: TQ scored correct readings as deception (0 exceptions) [SD §12]
- rerun fact: broken testbed reproduces monotone trend (p=.016); fixed does not (p=.125) [RR]
- contributions (numbered list allowed):
  (1) quantified audit: 44–63% of deception in five of six arms in broken cells [CT T8]
  (2) taxonomy, 5 classes, detection signature each
  (3) controlled before/after rerun, pre-specified plan
  (4) config-leak ablation with trace evidence
  (5) corrected results: what survives / not / only as direction
  (6) released testbed, audit scripts, executable path checks
Reviewer challenge: "why publish a benchmark whose results failed?" → answer: the failure classes are general; ABC shows same in capability benchmarks.
-->
