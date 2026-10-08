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

A pre-ticked donation box at checkout, a fee that appears only on the last screen, a cancel button hidden four menus deep. Designs like these, usually called dark patterns, steer people toward choices that serve the platform rather than themselves~\cite{brignull2023deceptive,gray2018dark}, and they are common on shopping sites~\cite{mathur2019darkpatterns}. Regulators have started to treat them as law, not just bad design. In 2023 India's Central Consumer Protection Authority named thirteen of them as unfair trade practices~\cite{ccpa2023guidelines}.

Increasingly, though, the one clicking through checkout may not be a person. AI agents now shop, subscribe and fill in forms on people's behalf, and a dark pattern that once had to fool a human now only has to fool the agent. Whether it does has become an empirical question, and benchmarks are how the field answers it~\cite{ersoy2026trickyarena,guo2026susbench,tang2025darkgui}. That puts a lot of weight on the benchmarks. If a benchmark's numbers do not mean what their labels say, conclusions about agent safety, and possibly about enforcement, rest on nothing. Validity has to be shown, not assumed~\cite{jacobs2021measurement,raji2021benchmark}.

We built such a benchmark. Armavour implements twelve of the thirteen practices in India's guidelines, at four levels of intensity, in English, Hindi and Hinglish, and evaluates two agent architectures on them. The first full run, 1,928 episodes, gave us three clean findings. Deception rose steadily with the intensity of the manipulation. Patterns that hide information worked on agents, while patterns that rely on presentation or emotion did not. And agents were deceived far more often on Hindi pages than on English ones. These were tidy results that fit the literature.

Then we audited the benchmark, and most of those findings did not survive. The dose-response curve was largely produced by a few broken items. In two patterns at the top intensity, no correct path existed: the only way to finish the task was to be scored as deceived. In the trick question, the scoring was inverted. An agent that read the label correctly was recorded as deceived, and one that misread it was recorded as having resisted. In every trick-question episode on ComputerUse, the outcome followed from the final state of one checkbox, with no exceptions. When we repaired these items and ran the original and repaired testbeds side by side on the same model, the original reproduced a clean, monotone dose-response curve ($p = .016$), and the repaired one did not ($p = .125$). Broken items had manufactured the main finding.

Why publish a benchmark whose results failed? Because the ways it failed are not specific to us. Every one of them passed the checks we had: the pipeline ran, the oracle fired, and the numbers were stable and plausible. The failures were in what the numbers meant. Similar flaws in task design and scoring have been documented in capability benchmarks~\cite{zhu2025abc}, and some of the design choices that leaked information in ours are common in other dark-pattern benchmarks. We think a careful account of how a reasonable benchmark went wrong is more useful to the people building the next one than another set of clean-looking numbers.

This paper makes six contributions:

1. **A quantified audit.** In five of the six arms of the original run, between 44% and 63% of all recorded deceptions came from cells that could not measure what they claimed to (Section~\ref{sec:07_corrected_results}).
2. **A taxonomy of measurement-validity failures** in five classes (item design, information leakage, scoring, analysis and provenance), each with a signature that others can check for in their own benchmarks (Section~\ref{sec:06_taxonomy}).
3. **A controlled rerun** of 800 episodes, original against repaired testbed, under a pre-specified plan.
4. **An ablation of the configuration leak,** with trace evidence.
5. **Corrected results:** what survives, what does not, and what holds only as a direction.
6. **Released artefacts:** the testbed, audit scripts and executable path checks.
