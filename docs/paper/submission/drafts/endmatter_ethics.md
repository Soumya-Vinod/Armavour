<!--
## Endmatter (extra page, not counted)
- Ethical considerations: synthetic testbed, no human subjects, no real platforms; dual-use of pattern implementations; notice to related benchmark authors if sent
- No acknowledgements/positionality at submission (anonymity)
-->
<!-- Points to cover (own words): synthetic testbed, no human subjects, no real platforms or payments; dual-use risk of releasing manipulative-pattern implementations and why release is justified; notice sent to authors of related benchmarks whose design choices are discussed (only if actually sent); Hindi-speaker comprehension disparity as a potential harm; results not for vendor ranking or relaxing consumer protection. Keep methodological limitations out of this section (they belong in Limitations). -->

This work involved no human participants. Every episode was run on a synthetic testbed that we built and hosted ourselves. No real platform was visited, no real account was created, and no payment was made. Anything an agent typed into a form stayed on our own machines. The traces we coded by hand were written by language models, not people. Items modelled on enforcement actions draw only on the regulator's public orders.

Releasing working implementations of dark patterns carries a dual-use risk: someone could copy them. We think the risk is small and the benefit larger. Every pattern we implement is already described, with examples, in the public guidelines it comes from, and our implementations are simple, synthetic pages, not tools for deploying manipulation at scale. What they add is a way to test whether agents can resist these patterns, which is the purpose of the release.

Our language finding points to a possible harm. Agents instructed in Hindi failed tasks on pages with no manipulation at all. People who rely on agents in languages other than English may be served worse even by honest sites. We report this to argue for evaluation in more languages, not to rank languages or the people who speak them.

Our results should not be used to rank agent vendors or to argue that consumer protection can be relaxed for agent-mediated shopping. They come from two models on a synthetic testbed, and leaked information in our original benchmark made agents look more resistant than they were, not less.

We discuss design choices in other dark-pattern benchmarks only to show where checks are worthwhile. We make no claim that their results are wrong.
<!-- TODO(authors): if you notify the authors of the benchmarks discussed in Sections 2 and 6, say so here; do not state it unless it was actually sent. -->
