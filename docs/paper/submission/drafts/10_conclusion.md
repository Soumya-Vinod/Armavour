# Conclusion

<!--
## 10 Conclusion (~0.25 pp)
- benchmark, audit, rerun; what survived; failure classes general; checks released
-->

We set out to measure whether dark patterns fool AI agents, and ended up measuring our own benchmark. Its first results were clean and plausible, and most of them were wrong. Broken items produced the dose-response curve, inverted scoring turned correct answers into deceptions, and the agent was told more than any consumer would be. When we repaired four items and ran the benchmark again, the curve was gone.

Some findings held up. Bait-and-switch still deceives agents when it is pushed hard. And agents instructed in Hindi fail on pages with no manipulation at all, on two models, because they misunderstand the page. For a Hindi-speaking consumer, that failure matters whether or not anyone is trying to trick them.

None of the problems we found are unusual, and none of them were caught by the checks benchmarks normally run. We release the scripts and executable item checks we used, in the hope that the next benchmark of this kind will be audited before its results are published, not after.
