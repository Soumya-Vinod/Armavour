# Audit Method

<!--
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
-->

We audited the benchmark the way we would want someone else to audit it. The question was the same for every number we had published: does it measure what its label says? A rate labelled "deceived by drip pricing at aggressive intensity" should go up when agents are deceived by drip pricing, and only then. We worked through that question in seven steps. The first five examine the data and code we already had. The last two produce new evidence.

**Trace audit.** We read what the agents actually wrote. For each episode we separated text the model generated (its reasoning, actions and final summary) from text the harness supplied, such as the start URL. We then searched the model's output for vocabulary that should not have been there: pattern names, configuration keys, intensity labels, and words like "dark pattern" or "benchmark". A word the agent used that the page never showed had to come from somewhere else (Appendix~\ref{app:protocol}). This step found the configuration and identifier leaks (Section~\ref{sec:06_taxonomy}).

**Specification audit.** For each of the 12 patterns at each of the four intensities, we compared what the page actually renders, as the agent's text extractor sees it, with what the pattern's specification says it should render. We then listed every action an agent could take in that cell and the outcome the oracle assigns to each. The question for each cell was simple: can an agent that reads the page correctly and follows the task be scored as having avoided the pattern? We call a cell *breaking* when no path an agent could choose from the page leads to a correct completion, or the scoring contradicts the specification (the full grading scale is in Appendix~\ref{app:spec}). Among the scored patterns, four cells were breaking in every language, twelve once language is counted: drip pricing and SaaS billing at aggressive intensity, and the trick question at moderate and aggressive intensity. These are the cells removed in the corrected analysis. The subscription trap's scoring rule was also graded breaking. We treat it separately, because the fault lies in the scoring rule and not in the item.

**Provenance forensics.** Because timestamps could not date a row's content, we dated rows by content signatures and git ancestry, and identified the judge from a typographic fingerprint in its outputs (Section~\ref{sec:06_taxonomy}).

**Controlled ablation.** Where exposure was universal, we ran a seed-paired ablation (Section~\ref{sec:leakage}).

**Reconstruction.** We corrected the published results with the original analysis code, after first checking that it reproduced every published table exactly (Appendix~\ref{app:protocol}).

**Executable path checks.** A specification audit is a reading of the code, and readings can be wrong. So we turned its central question into scripted browser tests with no language model: in each cell, the path a faithful reader would take must be scored as avoided, and the path the manipulation is built to induce must be scored as deceived. The original testbed fails on exactly the 12 breaking combinations; the repaired one passes all 72 (Appendix~\ref{app:paths}).

**Controlled rerun.** Finally, we repaired four items and ran the original and repaired testbeds side by side on the same model, under an analysis plan written and committed before the run (Section~\ref{sec:07_corrected_results}).

All database queries were read-only and every finding is tied to a script that can be re-run, which matters because we audited our own work (Section~\ref{sec:09_limitations}).
