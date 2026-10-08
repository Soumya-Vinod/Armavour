# Limitations

<!--
## 9 Limitations (~0.5 pp)
- original model retired; rerun and ablation on Qwen (thinking off)
- synthetic testbed; English-only rerun; new hi/hinglish strings for fixes not yet native-reviewed
- judge size unknown; small judge validation set (12 cases, 2 positives)
- auditors = authors
- retroactive exclusion cannot recover broken cells; rerun covers 4 fixes only; MAJOR findings unfixed
- unseeded provider sampling; rate-limit retry truncation
- plan not independently registered
-->

The biggest limitation is one we could not avoid: the model the benchmark was built around no longer exists. Llama-3.3-70B was withdrawn by its provider, so the original matrix cannot be rerun, and every new piece of evidence in this paper comes from a different model, Qwen3.8-27B, run with its thinking mode switched off. The rerun shows what broken items do to the measurements of one model. It does not tell us what Llama would have done on the repaired testbed.

The rerun is also narrow. It covers English only, one agent architecture (ComputerUse) and four repairs. The other problems the specification audit graded *major* were left in place on purpose, so that the comparison isolates the four repairs, and they remain in both variants. The Hindi and Hinglish strings we wrote for the repairs have not yet been reviewed by a native speaker. No reported result depends on them, since the rerun was in English, but they would need checking before anyone used the repaired items in other languages. The language replication ran on the original testbed, at control intensity only. For the matrix itself, removing broken cells after the fact tells us what the remaining cells say, but nothing about what agents would have done on working versions of the removed ones. We could not recover E1b's step budget, which is one reason we make no comparison between the two architectures.

The testbed is synthetic. We think that is the right choice for a controlled study, and it is what made the audit possible, but real sites are messier and an agent's behaviour on them may differ.

Some of the noise in our results is built in. The provider does not let us seed its sampling, so the ten episodes of a cell in the rerun are replicates rather than reproducible draws. With ten episodes per cell, sampling alone can move a cell by about four in ten. Rate-limit retries cut short the traces of 21 rerun episodes. Their outcomes are unaffected, but any analysis of their reasoning is not.

We know less about the judge than we should. The manifest recorded the wrong model. The typographic evidence points to the gpt-oss family, but not to a size. And the judge was validated on only twelve cases, two of them positive. This affects the two judge-scored patterns, and it is one reason we report the page's own outcome as the primary measure.

Finally, we audited our own work. We built the benchmark, chose what to look for and decided what counted as broken. The executable path checks, the read-only queries and the released scripts are meant to make those judgements checkable, but they do not make them independent. The rerun's analysis plan was written down and committed before the run, but not lodged with an independent registry. Several robustness analyses were added after the results were seen, at a reviewer's request, and we have marked them as post hoc. An outside audit of this benchmark, using the checks we release, would be the strongest test of what we report here.
