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

Four limits matter most.

**The original model is gone.** Llama-3.3-70B was withdrawn by its provider, so the matrix cannot be rerun, and all new evidence comes from Qwen3.8-27B with its thinking mode switched off. The rerun shows what broken items do to one model's measurements, not what Llama would have done on the repaired testbed.

**The new evidence is narrow.** The rerun covers English only, one architecture (ComputerUse) and four repairs; the other problems graded *major* were left in place in both variants. The Hindi and Hinglish strings written for the repairs have not yet been reviewed by a native speaker, though no reported result depends on them. The language replication used the original testbed at control intensity only. Retroactive exclusion cannot tell us what agents would have done on working versions of the removed cells, and E1b's unknown step budget rules out comparing the two architectures. The testbed is synthetic by design, which is what made the audit possible, but real sites are messier.

**Some noise is built in.** Provider sampling cannot be seeded, so the ten episodes of a rerun cell are replicates rather than reproducible draws, and sampling alone can move a cell by about four in ten. Rate-limit retries truncated the traces, though not the outcomes, of 21 episodes. The judge's model was misrecorded, its size is unknown and its validation set was small (Section~\ref{sec:03_benchmark}), which is one reason the page's own outcome is our primary measure.

**We audited our own work.** We built the benchmark, chose what to look for and decided what counted as broken. Path checks, read-only queries and released scripts make those judgements checkable, but not independent. The rerun's plan was committed before the run but not independently registered, and several analyses are post hoc. An outside audit using the checks we release would be the strongest test of what we report here.
