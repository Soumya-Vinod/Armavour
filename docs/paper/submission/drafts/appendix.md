# Appendix

<!--
## Appendix (unlimited, reviewers not obliged)
- A: audit protocol step by step
- B: SPEC_DIVERGENCE summary grid (pattern × intensity verdicts)
- C: PATH_CHECKS summary
- D: scoring v2 rule table
- E: rerun plan + deviations; full pattern × intensity grid both variants
- F: corrected tables T1–T7 full
- G: ablation details
-->

## Episodes and configuration {#app:episodes}

The testbed page is driven entirely by URL parameters (pattern, intensity, interface language and seed), so an episode is a pure function of its configuration. A hash of the configuration, including the instruction language, is the episode's key, which lets an interrupted run resume without repeating or skipping anything.

## Audit protocol {#app:protocol}

This is the order in which we did the audit, with the script or record that each step produced. Every database query was run read-only.

1. **Trace audit.** We exported every stored trace and separated model-generated text from harness-supplied text. We searched the model text for five groups of terms: pattern names, configuration keys, intensity labels, words such as "dark pattern" or "benchmark", and spelled-out pattern names. Each hit was checked against a corpus of 3,678 strings the testbed and task prompts could render.
2. **Specification audit.** For each pattern and intensity, we compared the page as the extractor sees it with the specification. We listed every action path and its oracle outcome, and graded the cell OK, minor, major or breaking (Appendix~\ref{app:spec}).
3. **Provenance forensics.** We dated rows by content signatures and git ancestry, not by timestamps, and identified the judge from a typographic fingerprint in its outputs.
4. **Reconstruction.** `scripts/corrected_tables.py` rebuilds every published table with the original analysis functions and checks it cell by cell before applying any exclusion. All ten tables matched, and a deliberately changed outcome produced 19 mismatches.
5. **Executable path checks.** `tests/test_item_paths.py` drives every cell along a faithful and a deceived path with scripted browser sessions and no language model (Appendix~\ref{app:paths}).
6. **Leak ablation.** `scripts/run_leak_ablation.py` and `scripts/analyze_ablation.py` (Appendix~\ref{app:ablation}).
7. **Repairs and rerun.** Four items were repaired (Appendix~\ref{app:fixes}), and the rerun was run under a plan committed beforehand with `scripts/run_rerun.py`. It was scored with `scripts/score_v2.py` (Appendix~\ref{app:v2}) and analysed with `scripts/analyze_rerun.py`.
8. **Language replication.** `scripts/run_lang_control.py` and `scripts/analyze_lang_control.py`, under their own pre-specified plan (Appendix~\ref{app:langctl}).
9. **Post-hoc analyses.** Requested by a reviewer after the results were seen: `scripts/review_analyses.py`. Every output is labelled post hoc.

## Specification audit: verdict for every cell {#app:spec}

Table~\ref{tab:app-spec} gives the verdict for each pattern and intensity. *Breaking* means no path an agent could choose from the page leads to a correct completion, or the scoring contradicts the specification. *Major* means detectability or the avoidance path differs from the specification. *Minor* is a wording or cosmetic difference. The trick question's aggressive level is breaking in all three languages. The original audit had judged the Hinglish version consistent, and a native-speaker check showed it is not. For the subscription trap, the item itself is close to its specification, but the scoring rule (C1) made giving up count as avoidance. We list that separately.

\begin{table}[htbp]
\caption{Specification-audit verdicts by pattern and intensity. * excluded from scoring before the audit. C1: abandonment scored as avoidance. ID: element-id leak in the matrix.}
\label{tab:app-spec}
\centering
\small
\begin{tabular}{lllll}
\toprule
\textbf{Pattern} & \textbf{Control} & \textbf{Subtle} & \textbf{Moderate} & \textbf{Aggressive} \\
\midrule
Basket sneaking & Major & OK & Major & Major \\
Drip pricing & Minor & Major & Major & \textbf{Breaking} \\
Bait and switch & Minor & OK & Minor & OK \\
Disguised advertisement* & OK & OK & Major & \textbf{Breaking} \\
False urgency* & Minor & Major & Major & Major \\
Confirm shaming & Major & OK & Minor & OK (ID) \\
Interface interference & OK & Minor & Minor & Major (ID) \\
Forced action & OK & Major & OK & Major \\
Nagging & OK & Major & Major & Major \\
Subscription trap & OK & Minor + C1 & Major + C1 & Major + C1 \\
SaaS billing & OK & Minor & Major & \textbf{Breaking} \\
Trick question & OK & Minor & \textbf{Breaking} & \textbf{Breaking} \\
\bottomrule
\end{tabular}
\end{table}

## Executable path checks {#app:paths}

For each cell, the test checks two things. The *faithful* path, what a reader who follows the task literally would do using only what the page shows, must be scored as avoided. The *deceived* path, what the manipulation is designed to induce, must be scored as deceived. The four repaired patterns are checked in all three languages and the others in English, which gives 72 combinations for the ten scored patterns.

On the frozen original testbed, the checks fail on exactly the 12 expected combinations and nowhere else:

- **Drip pricing and SaaS billing, aggressive, all three languages: no faithful path exists.** In drip pricing, the only control is Pay, and it adds the fee and fires the oracle in one click. In SaaS billing, the only control starts a trial with automatic renewal switched on.
- **Trick question, moderate and aggressive, all three languages: the faithful path is scored as deceived.**

On the repaired testbed, all 72 combinations pass. A separate test confirms that the six patterns we did not repair produce identical oracle results in both variants. Disguised advertisement at aggressive intensity fails in both variants. With no label on the ad, nothing on the page lets an agent tell it apart from the genuine items. The pattern was already excluded for this reason.

Three faithful paths are refusals rather than completions: declining or cancelling in drip pricing, "No thanks" in bait-and-switch, and "Leave" in forced action. The oracle scores them as avoided, and the revised scheme codes them as refusals (Appendix~\ref{app:v2}).

## Revised outcome codes {#app:v2}

The rerun is scored twice. The original codes (v1) are kept unchanged so that old and new data stay comparable. The revised codes (v2) are computed offline from the stored oracle result and the reason the episode ended. Unlike v1, v2 never treats missing ground truth as avoidance.

\begin{table}[htbp]
\caption{Revised (v2) outcome codes.}
\label{tab:app-v2}
\centering
\small
\begin{tabular}{p{0.07\linewidth}p{0.30\linewidth}p{0.53\linewidth}}
\toprule
\textbf{Code} & \textbf{Meaning} & \textbf{When} \\
\midrule
EC & Task completed, pattern avoided & Oracle fired; task completed; pattern avoided \\
DC & Task completed, deceived & Oracle fired; task completed; pattern not avoided \\
DF & Deceived, task not completed & The pattern won without the task being completed, e.g.\ the subscription is still active at the end \\
RF & Refused & Oracle fired through a decline, cancel or ``No thanks'' control, or the agent stopped explicitly without an oracle \\
NC & No completion signal & No oracle, and the episode ended by step cap, crash, silent stop or a failed click; excluded from denominators \\
\bottomrule
\end{tabular}
\end{table}

The primary rate is the deception rate, (DC + DF) / (EC + DC + DF + RF). NC episodes are reported per cell but excluded from the denominator. v1's EF splits under v2 into RF (an explicit refusal), DF (an abandoned cancellation) and NC (no signal). A rule table covering every combination of pattern, oracle state and ending is generated and tested by `scripts/score_v2.py`.

## Controlled rerun {#app:rerun}

### The four repairs {#app:fixes}

1. **Drip pricing, aggressive.** The fee now appears on a separate confirmation screen before the oracle fires, so an agent can see the higher total and decline.
2. **SaaS billing.** A genuine free plan exists at every intensity, and the disclosure of automatic renewal follows the specification at each level.
3. **Trick question.** The scoring now follows the label as rendered, in every language. The box's starting state was also changed so that doing nothing is never correct. At subtle intensity the box now starts ticked, as its label assumes, so the subtle cell also differs between variants.
4. **Nagging.** The prompt now interrupts the task. It reappears each time the agent tries to finish, up to six times at aggressive intensity.

Every other finding graded major was left in place on purpose and affects both variants equally.

### Plan {#app:plan}

The plan was committed before the run and was not changed afterwards. It specified the following:

- **Design.** Ten scored patterns at four intensities, seeds 0 to 9, on both variants: 800 episodes. The run used Qwen3.8-27B at temperature 0.7 with thinking suppressed, the ComputerUse adapter, English interface and instruction, 20 steps, no configuration leak and opaque identifiers. Each configuration ran on both variants back to back, alternating which went first.
- **Exclusions.** Crashed episodes were retried up to three times. NC episodes were excluded from v2 denominators only, and a cell with five or more NC would be flagged as uninformative. There were no other exclusions and no interim looks at outcomes.
- **H1.** Each formerly breaking cell has at least one EC or RF episode in the fixed variant.
- **H2.** A monotone dose-response holds in the fixed variant if a one-sided sign test over the per-pattern Cochran–Armitage statistics gives $p < .05$ and the pooled rate never decreases from one intensity to the next.
- **H3.** Within-cell variation is supported if at least 16 of the 80 cells are mixed, rejected if 8 or fewer are, and inconclusive in between.
- **Sanity check.** Fisher's exact test on each of the 24 cells of the untouched patterns, Holm-adjusted.

### Deviations from the plan {#app:deviations}

1. **Freeze and registration.** The plan was committed before the run started and did not change. The freeze fields were filled in after the run, because the run's safeguards forbid commits while it is running. The plan was not lodged with an independent registry, so we describe it as pre-specified, not pre-registered.
2. **Outcomes visible during the run.** The run console printed each episode's v1 outcome, and the author saw these while watching for crashes. One diagnostic query during the run also showed the outcomes of the ten baseline subscription-trap episodes at aggressive intensity, to investigate their step counts. The plan was not changed in response to either.
3. **Crashes from a failing API key.** A short series of crashes (confirm shaming, subtle) was caused by a failing key. Every crashed configuration was retried, and the final crash count is zero in both variants.
4. **Pause at the provider's daily limit.** At about 410 of 800 episodes, both API keys reached the provider's daily token limit and the run stopped itself. It resumed after the reset the next morning, with every setting unchanged.
5. **Truncated traces after rate-limit retries.** When a model call was retried after hitting the per-minute rate limit, the agent loop restarted with an empty trace and step counter, while the browser kept its state. The final oracle state is valid, so outcomes are unaffected. The stored traces and step counts are truncated, though, and the step budget was effectively reset. This affected 6 baseline and 15 fixed episodes. The fixed variant has more because its repaired items take more steps and so make more model calls. These episodes are flagged in any analysis of traces.
6. **Smoke-test run names.** The two-episode smoke test was stored under different run names from those in the plan, to avoid a clash between the two variants. Smoke-test episodes are not part of the data.

### Full results {#app:rerun-grid}

Table~\ref{tab:app-rerun-grid} gives deceived over scored episodes for every cell in both variants, with refusals in brackets.

\input{tables/A_rerun_grid}

## Corrected matrix tables {#app:corrected}

Tables~\ref{tab:corr-outcome} to~\ref{tab:corr-langpattern} give the original matrix tables before and after the breaking cells are excluded. Tables~\ref{tab:v-t1} to~\ref{tab:v-t5} add Wilson and cell-cluster bootstrap intervals to the corrected rates. The intervals are post hoc: they were computed after the results were seen, at a reviewer's request.

\input{../tables/T1_outcome}

\input{../tables/T2_control}

\input{../tables/T3_intensity}

\input{../tables/T4_patterns}

\input{../tables/T5_language}

\input{../tables/T6_mcnemar}

\input{../tables/T7_language_pattern}

\input{tables/V_T1}

\input{tables/V_T3}

\input{tables/V_T4}

\input{tables/V_T5}

## Configuration-leak ablation {#app:ablation}

**Design.** We ran 200 configurations twice each, once with the run configuration (pattern name and intensity) in the prompt and once without. They covered the ten scored patterns at control and aggressive intensity, seeds 0 to 9. The agent was Qwen3.8-27B with thinking disabled, on the ComputerUse adapter, with 20 steps. The testbed was the one in use before the four repairs. It differs from the matrix's in one respect: the element identifiers that had leaked answers were already opaque. Episodes were paired by configuration.

**Results.** Deception was 12.5% (25 of 200) with the configuration and 15.0% (30 of 200) without it. Six pairs were deceived only without the configuration and one only with it (McNemar's exact test, $p = .125$). No control episode was deceived in either arm. Only 2 of the 20 cells had any discordant pair. Bait-and-switch at aggressive intensity accounts for all six: 10 of 10 deceived without the configuration, 4 of 10 with it. The single reverse pair is in nagging at aggressive intensity. Drip pricing and the trick question at aggressive intensity were 10 of 10 in both arms, as their broken items require.

**Trace evidence.** In five of the six bait-and-switch episodes that changed outcome, the agent's reasoning with the configuration named the tactic, and two quoted the configuration label verbatim. None of the 200 episodes without the configuration mentioned it. In three control episodes of bait-and-switch, where no switch takes place, the agent with the configuration also mentioned the tactic. The cell-level breakdown was added post hoc.

## Language replication {#app:langctl}

**Design.** The replication covered control intensity only, on the original (unrepaired) testbed. It used the five scored patterns of the language arms (trick question, confirm shaming, interface interference, forced action and SaaS billing) under five instruction/interface combinations: English/English, English/Hindi, English/Hinglish, Hindi/Hindi and Hinglish/Hinglish. With seeds 0 to 9, that is 250 episodes. The agent was Qwen3.8-27B at temperature 0.7 with thinking suppressed, and the judge was used for confirm shaming only. The plan was written before the run, and the analysis was run once, after it finished.

**Tests.** The primary comparison (H1) was Hindi/Hindi against English/English. It used a one-sided exact stratified test with patterns as strata, at $\alpha = .05$. The secondary comparison (H2) was English/Hindi against English/English. The two Hinglish comparisons (H3) were exploratory. Every deceived episode was exported for hand coding as a comprehension failure, a breakdown in language generation, or other.

**Results.** H1 replicated: 6 of 50 against 0 of 50, $p = .008$. H2 did not (3 of 50, $p = .12$), and neither Hinglish comparison did (0 of 50 each). All nine deceived episodes were coded as comprehension failures. In one (episode 159), the context text the harness passes with each button ran straight into the neighbouring button's label, and the agent took the "Remove" at its end as the label of the "Keep donation" button. The judge flagged none of the confirm-shaming deceptions as genuine influence. Two deviations were recorded. In three SaaS-billing control episodes, the provider rejected the agent's output and the error message, which contained the agent's reasoning, was printed to the console. One episode crashed once and completed on retry, leaving a final crash count of zero.
