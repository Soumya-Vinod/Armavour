# Discussion

<!--
## 8 Discussion (~1.25 pp)
- everything "worked": no crashes, plausible stable aggregates; failures in meaning of numbers
- checklist, one check per class (list allowed): enumerate paths per cell; native-speaker verify scoring per language; grep reasoning for non-rendered vocabulary; separate codes for non-completion/refusal/abandon; never default missing ground truth to benign; test null condition along every axis; cell as unit under low-variance decoding; per-row code SHA + judge model; check served = committed; archive outputs
- consumer protection: regulators may rely on such benchmarks; overstatement misdirects enforcement; leakage understates → false assurance
- self-audit value; negative results publishable
- generality: same design choices in other agent dark-pattern benchmarks (URL activation, static IDs) — check, not accuse
Reviewer challenge: actionable? → checklist + released executable path checks.
-->

The uncomfortable lesson of this audit is that nothing went wrong in the way we were watching for. There were no crashes, the oracle fired, the aggregates were stable, and the findings fit the literature. Every check we had built was a check that the pipeline *ran*. None of them asked whether a number meant what its label said. The failures in Section~\ref{sec:06_taxonomy} all lived in that gap, and we suspect we are not the only ones with such a gap.

## A checklist

Most of what we found could have been caught before a single episode was run, or soon after. We offer the checks we wish we had run, one or two per failure class. None of them is sophisticated. Each would have caught at least one problem in Armavour that changed a published number.

- **Item design.** For every cell, list every action path and the outcome the scorer assigns to it. Turn the list into a scripted test with no model in the loop. A cell with no path scored as avoided, or with an outcome fixed by a single UI state, is not measuring susceptibility. For each language, have a native speaker check that the scoring rule matches what the label actually says.
- **Leakage.** Search the agent's reasoning for words the rendered page never contains: pattern names, configuration keys, fragments of element ids. If the agent could see something the consumer could not, run a paired ablation with and without it.
- **Scoring.** Give non-completion, refusal and abandonment their own codes. Never let missing ground truth default to the benign outcome. Check that the same behaviour gets the same code in every pattern.
- **Analysis.** Measure the null condition along every axis you plan to compare, including language. Before reporting a pooled effect, count how many cells carry it. Under low-variance decoding, treat the cell as the unit of analysis.
- **Provenance.** Record the code version and the judge model on every row. Check that the page actually served matches the committed code. Keep the full prompts and raw outputs, not just the parsed results. Our database did not store the prompts, so for some questions we could only infer what the agent had been shown.

We release the path-check tests and audit scripts so that these checks can be run on Armavour, or adapted for other benchmarks.

## Why this matters for consumer protection

Benchmarks like ours are starting to be read as evidence about whether AI agents can be trusted to act for consumers. Regulators, including the one whose guidelines we built on, may look to them when deciding where to focus. Measurement error in this setting has costs in both directions. Overstatement points attention in the wrong place: our original analysis singled out drip pricing as one of the most effective patterns, and that result came from an item no agent could pass. Understatement is worse, because it looks like reassurance. In our ablation on a second model, the configuration leak warned the agent about bait-and-switch and cut the deception rate in that cell from 10 in 10 to 4 in 10. A benchmark with leaks like this will tend to report that agents resist manipulation better than they do.

The language results raise a different concern. On pages with no manipulation at all, an agent instructed in Hindi failed tasks that the same agent completed in English. Counting those failures as deception overstates the agent's susceptibility. But the more important point for consumer protection is that a Hindi-speaking consumer who delegates to such an agent is let down even when the site is honest. English-only evaluation would never show this.
