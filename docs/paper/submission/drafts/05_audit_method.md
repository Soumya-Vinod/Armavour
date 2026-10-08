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

**Trace audit.** We read what the agents actually wrote. For each episode we separated text the model generated (its reasoning, actions and final summary) from text the harness supplied, such as the start URL. We then searched the model's output for vocabulary that should not have been there: pattern names, configuration keys, intensity labels, and words like "dark pattern" or "benchmark". To tell leakage apart from ordinary reading, we checked every hit against a corpus of 3,678 strings the testbed and task prompts could render. A word the agent used but the page never showed had to come from somewhere else. This step found the configuration and identifier leaks (Section~\ref{sec:06_taxonomy}).

**Specification audit.** For each of the 12 patterns at each of the four intensities, we compared what the page actually renders, as the agent's text extractor sees it, with what the pattern's specification says it should render. We then listed every action an agent could take in that cell and the outcome the oracle assigns to each. The question for each cell was simple: can an agent that reads the page correctly and follows the task be scored as having avoided the pattern? We graded each cell on a four-point scale. *OK* means the cell matches its specification. *Minor* means a cosmetic or wording difference. *Major* means detectability or the avoidance path differs from the specification. *Breaking* means no path an agent could choose from the page leads to a correct completion, or the scoring contradicts the specification. Among the scored patterns, four cells were breaking in every language, twelve once language is counted: drip pricing and SaaS billing at aggressive intensity, and the trick question at moderate and aggressive intensity. These are the cells removed in the corrected analysis. The subscription trap's scoring rule was also graded breaking. We treat it separately, because the fault lies in the scoring rule and not in the item.

**Provenance forensics.** We tried to establish what code and which models produced each row. This was harder than it should have been. The episode store kept the first insertion time when a row was overwritten, so timestamps could not date a row's content. We relied instead on content signatures, such as prices or labels an agent quoted that only one version of the code could render, and on git ancestry, to work out which version of the testbed each machine could have served. The same approach identified the judge. Its outputs carried a typographic fingerprint that matched one model family and not the one recorded in the manifest.

**Controlled ablation.** Some problems could be shown to exist but not to matter. Every episode had the run configuration in its prompt, so the matrix contains no unexposed condition to compare against. Where exposure was universal, we ran a seed-paired ablation on a second model: the same 200 configurations with and without the leaked information, compared pair by pair.

**Reconstruction.** To correct the published results, we reused the original analysis code rather than writing new code. We first ran it on the full matrix and checked that it reproduced every published table cell for cell. All ten tables matched exactly, and changing a single outcome produced 19 mismatches, so the check could fail. Only then did we apply the corrections, so that any change in the numbers comes from the exclusions and not from new code.

**Executable path checks.** A specification audit is a reading of the code, and readings can be wrong. So we turned its central question into tests. Using scripted browser sessions with no language model, we drove each cell along two paths. The *faithful* path is what a reader who follows the task literally would do. The *deceived* path is what the manipulation is designed to induce. We checked that the oracle scores the first as avoided and the second as deceived. On a frozen copy of the original testbed, the checks fail on exactly the 12 breaking cells and nowhere else. On the repaired testbed, all 72 checked combinations of pattern, intensity and language pass.

**Controlled rerun.** Finally, we repaired four items and ran the original and repaired testbeds side by side on the same model, under an analysis plan written and committed before the run (Section~\ref{sec:07_corrected_results}).

Some further analyses were added later at a reviewer's request, after the results had been seen. We mark these as post hoc wherever they appear.

All database queries in the audit were read-only, and every finding is tied to a script or query that can be re-run. That matters because of the audit's main weakness: the auditors are the authors. We built the benchmark, found its problems, and decided what counted as broken. We cannot remove that conflict, but we have tried to make our judgements checkable. The path checks fail or pass without our interpretation, the rerun's analysis was fixed before its data existed, and we release the scripts so that others can run the same checks on our benchmark, or on their own.
