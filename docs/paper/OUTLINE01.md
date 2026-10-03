# Paper outline (fragments only — author writes all prose)

Format: acmart manuscript, single column, ≤14 pp excl. refs; endmatter page extra; appendix unlimited.
Focus area: Evaluations and evaluation practices.
Title: author's choice. Angle: what a susceptibility benchmark actually measures; self-audit.
Source key: CT = CORRECTED_TABLES.md · SD = SPEC_DIVERGENCE.md · FU = FOLLOWUP_REPORT.md · SP = 03_SPRINT_REPORT.md · RR = RERUN_RESULTS.md · PC = PATH_CHECKS.md · AB = results/ablation · N = NUMBERS.md

---------------------------------------------------------------------
## Abstract (~200 words, write last)
- agents act for consumers; interfaces contain dark patterns
- benchmark from India's CCPA guidelines: 12 patterns, 4 intensities, 3 languages, 2 architectures, 1,928 episodes
- original headline findings: dose-response, pattern split, language effect
- structured self-audit → most findings artefacts
- controlled rerun: dose-response present on broken testbed, absent after 4 item fixes (same model, same run)
- taxonomy (5 classes) + detection signatures; config-leak ablation; corrected results; released checks
- NOT in abstract: pair-level language p-value

---------------------------------------------------------------------
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

---------------------------------------------------------------------
## 2 Background and related work (~1.5 pp)
2.1 Dark patterns & regulation
- taxonomies → measurement at scale [Gray 2018; Mathur 2019; Brignull 2023]
- CCPA 2023 codification; legal definitions constrain operationalisation [CCPA]
2.2 Agents and dark patterns
- TrickyArena [Ersoy et al., S&P 2026]: DC/DF/EC/EF outcome scheme (we adopt — credit); URL-parameter activation + static element IDs (same channels we found leaking; we did not audit their results); their EF analysis: early-exit/paralysis → coincidental evasion (parallels our scoring finding)
- SusBench [Guo et al.]: 9 types, 313 tasks, 55 real sites, humans vs agents; trick wording among most effective (our TQ finding is about our implementation, not theirs)
- Tang et al.: 16 types; agents prioritise task completion
- web/computer-use benchmarks [WebArena, Mind2Web, OSWorld]
2.3 Benchmark validity
- measurement & construct validity [Jacobs & Wallach; Raji et al.; Bowman & Dahl; BetterBench]
- Agentic Benchmark Checklist [Zhu et al., NeurIPS 2025]: task setup/reward flaws; τ-bench empty responses counted as success = analogue of our no-oracle default
- our difference: susceptibility benchmarks — second outcome axis, item validity, leakage, translation, provenance
2.4 Pseudo-replication [Hurlbert 1984]
- deterministic decoding → seeds ≠ independent samples
2.5 Multilingual evaluation [MEGA; GLUECoS — verify]
Reviewer challenge: novelty vs ABC → susceptibility-specific classes; controlled rerun evidence.

---------------------------------------------------------------------
## 3 The benchmark (~1.5 pp) + Table: 12 patterns, task, success signal
- synthetic testbed, 7 services; episode = pure function of config; config hash as key
- 12 of 13 CCPA patterns; 13th not observable in one session
- per pattern: spec (legal definition, manifestation per intensity, oracle, task, control)
- intensities: control, subtle, moderate, aggressive
- languages: English, Hindi, Hinglish; UI + instruction variants; native-speaker strings
- agents: ComputerUse (element list → one action), BrowserUse (third-party framework)
- outcome scheme from TrickyArena: EC/DC/EF/DF; oracle from page, not agent self-report
- judge for false urgency & confirm shaming only; raw oracle DC primary
- arms: E1a (CU, en, 488), spot-check (8B, 60), E1b (BU, 480), E2 (lang UI, 540), E2a/E2b (localised instruction, 180 each)
- original model: Llama-3.3-70B via Groq, T=0
- excluded before audit: DA, FU (328 episodes) → 1,600 scored
Reviewer challenge: synthetic testbed realism → acknowledge; controlled design is the point.

---------------------------------------------------------------------
## 4 Original results (~0.75 pp, deliberately short)
- dose-response E1a 0→9→23→38%; E1b 5→8→15→26% [CT T3 raw]
- overall DC 17.5% (CU), 13.5% (BU), 42.0% spot-check [CT T1 raw]
- pattern split: info-asymmetry patterns high (SaaS 55, TQ 42.5, drip 25, B&S 22.5); perception/affect ~0 [CT T4 raw]
- language: 20.7% en UI → 36.0% hi UI; McNemar 26 vs 3, p=1.5e-5 [CT T6 raw]
- frame: "as originally analysed" — no endorsement
Reviewer challenge: none; keep neutral.

---------------------------------------------------------------------
## 5 Audit method (~1 pp)
- guiding question: per number, does it measure what its label says
- (a) trace audit: model-output fields vs harness-supplied fields; vocabulary absent from rendered text [SP]
- (b) spec audit: per pattern × intensity, render vs spec; enumerate action paths; "can a faithful agent be scored as avoiding?" [SD]; grades minor/major/breaking
- (c) provenance forensics: git ancestry vs row creation; content signatures; typographic fingerprint [SP]
- (d) controlled ablation where exposure ≠ effect [AB]
- (e) reconstruction: same analysis code on filtered data; regression check reproduces every published cell first [CT]
- (f) executable path checks: scripted Playwright, no LLM; baseline fails exactly the 12 BREAKING cells; fixed 79/79 pass [PC]
- (g) controlled rerun with pre-specified plan [RR]
Reviewer challenge: auditor = author → independence limitation; mitigated by executable checks + released scripts.

---------------------------------------------------------------------
## 6 Taxonomy of failures (~3 pp) + Table: class | failure | where | signature | effect
6.1 Item design
- criterion-bypassable: DA v1 ad priced above cheapest genuine item; FU cue on pricier item [SD §4–5]
- implementation–spec divergence: SaaS agg (conversion disclosed, no free plan, autoRenew on → only action authorises renewal); drip agg (fee applied inside oracle-firing click) [SD §2, §11]
- uninformative nulls: nagging never interrupts; ST not buried, password not validated [SD §9–10]
- inverted scoring: TQ moderate/aggressive, all 3 languages; outcome = deterministic function of box state, 0 exceptions; episode 1214 quote (correct reading scored DC) [SD §12; native-speaker check]
- translation note: Hinglish negation count verified by native speaker
- visual-only manipulation: levels identical in text input → treatment not delivered (DA moderate 9px "Ad") [SD C3]
- signature: enumerate paths per cell; outcome fully determined by one UI state
6.2 Information leakage
- identifier leakage: DA/FU/CS/II ids named the answer [identifier_audit]
- config leakage: pattern/intensity in CU prompt; URL in BU task [SP]
- matrix agent: 0/1,448 CU traces verbalise it; 9/480 BU URL echoes on give-up [SP §2c]
- ablation (Qwen): DC 15.0→12.5%; 6 vs 1 discordant, p=.125; B&S agg 10/10→4/10; 5 of 6 flips name tactic, 2 quote label verbatim; 0/200 without config; 3 control-cell mentions where no switch exists [AB]
- implication: leak lowers measured deception → matrix rates lower bounds for this channel
- signature: vocabulary in reasoning absent from rendered text; seed-paired ablation
6.3 Scoring
- no-oracle → avoided (BU): 0/48 EF claim success; 16 forced, 14 obstacle aborts, 15 stop-short, 3 no done; 6/7 control EF forced [FU A3]
- ST abandonment scored safe: spec-faithful 9/40 deceived (BU) [CT S4]
- refusal scored inconsistently: FA "Leave" → EC; SaaS decline → EF; BU stop → avoided [CT C2]
- abandonment as success: B&S "No thanks" at control (4/10 believed already bought) [CT C2]
- signature: same behaviour → different codes across patterns; outcome category varies 10× across architectures and appears at control
6.4 Analysis
- denominator drift: pooled pattern column n=135 vs 45 [table_reconciliation]
- baseline contamination: Hindi instruction+UI control 42% deceived; en 0% [CT T2]
- pseudo-replication: language pairs 25 vs 1 (p=8e-7) vs cells 4 vs 0 (p=.125); one cell is TQ control [CT T6, T6_sign]
- signature: identical token counts across seeds; few cells carry effect
6.5 Provenance
- judge: manifest says Llama-8B; U+2011/U+202F fingerprint in 107/235 CS judge outputs; 0/2,205 Llama traces; 29/181 gpt-oss traces → gpt-oss family, size unknown [SP §2k]
- code drift within run: upserts keep first created_at; 172 BU rows with 7,602 s duration written in 20 s; arms on uncommitted code [SP §2h]
- served ≠ committed: drip pilot 0/5 saw pre-fix page ("Pay Rs 590"); main run 10/10 → GATE3 "reversal" artefact [CT Part A]
- hosted-model retirement: Llama-3.3-70B withdrawn → original not reproducible
- signature: agent reports values committed code cannot render; per-row code SHA absent
Reviewer challenge: "bug list, not taxonomy" → emphasise signatures + generality (ABC, TrickyArena design overlap).

---------------------------------------------------------------------
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

---------------------------------------------------------------------
## 8 Discussion (~1.25 pp)
- everything "worked": no crashes, plausible stable aggregates; failures in meaning of numbers
- checklist, one check per class (list allowed): enumerate paths per cell; native-speaker verify scoring per language; grep reasoning for non-rendered vocabulary; separate codes for non-completion/refusal/abandon; never default missing ground truth to benign; test null condition along every axis; cell as unit under low-variance decoding; per-row code SHA + judge model; check served = committed; archive outputs
- consumer protection: regulators may rely on such benchmarks; overstatement misdirects enforcement; leakage understates → false assurance
- self-audit value; negative results publishable
- generality: same design choices in other agent dark-pattern benchmarks (URL activation, static IDs) — check, not accuse
Reviewer challenge: actionable? → checklist + released executable path checks.

---------------------------------------------------------------------
## 9 Limitations (~0.5 pp)
- original model retired; rerun and ablation on Qwen (thinking off)
- synthetic testbed; English-only rerun; new hi/hinglish strings for fixes not yet native-reviewed
- judge size unknown; small judge validation set (12 cases, 2 positives)
- auditors = authors
- retroactive exclusion cannot recover broken cells; rerun covers 4 fixes only; MAJOR findings unfixed
- unseeded provider sampling; rate-limit retry truncation
- plan not independently registered

---------------------------------------------------------------------
## 10 Conclusion (~0.25 pp)
- benchmark, audit, rerun; what survived; failure classes general; checks released

---------------------------------------------------------------------
## Endmatter (extra page, not counted)
- Generative AI usage statement (required; agree wording with co-author): Claude Code for code, data analysis, audit scripts, tables/figures, literature search, fact ledger and outline; all text written by authors
- Ethical considerations: synthetic testbed, no human subjects, no real platforms; dual-use of pattern implementations; notice to related benchmark authors if sent
- No acknowledgements/positionality at submission (anonymity)

---------------------------------------------------------------------
## Appendix (unlimited, reviewers not obliged)
- A: audit protocol step by step
- B: SPEC_DIVERGENCE summary grid (pattern × intensity verdicts)
- C: PATH_CHECKS summary
- D: scoring v2 rule table
- E: rerun plan + deviations; full pattern × intensity grid both variants
- F: corrected tables T1–T7 full
- G: ablation details