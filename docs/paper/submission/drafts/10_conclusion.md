# Conclusion

<!--
## 10 Conclusion (~0.25 pp)
- benchmark, audit, rerun; what survived; failure classes general; checks released
-->

We set out to measure whether dark patterns fool AI agents, and ended up measuring our own benchmark: its first results were clean, plausible and mostly wrong. Broken items produced the dose-response curve, and when we repaired four of them and ran the benchmark again, the curve was gone.

Some findings held up. Bait-and-switch still deceives agents when it is pushed hard. And agents instructed in Hindi fail on pages with no manipulation at all, on two models, because they misunderstand the page. None of the problems we found are unusual, and we release our checks so that the next benchmark can be audited before its results are published, not after.
