# Original Results

<!--
## 4 Original results (~0.75 pp, deliberately short)
- dose-response E1a 0→9→23→38%; E1b 5→8→15→26% [CT T3 raw]
- overall DC 17.5% (CU), 13.5% (BU), 42.0% spot-check [CT T1 raw]
- pattern split: info-asymmetry patterns high (SaaS 55, TQ 42.5, drip 25, B&S 22.5); perception/affect ~0 [CT T4 raw]
- language: 20.7% en UI → 36.0% hi UI; McNemar 26 vs 3, p=1.5e-5 [CT T6 raw]
- frame: "as originally analysed" — no endorsement
Reviewer challenge: none; keep neutral.
-->

This section reports what the matrix appeared to show when we first analysed it. We give the numbers as they came out of the original analysis, which our reconstruction reproduces exactly (Section~\ref{sec:05_audit_method}). We do not endorse them. Most do not survive the audit, and Section~\ref{sec:07_corrected_results} says which. We set them out here because the point of the paper is the distance between these numbers and what was actually measured, and that distance is hard to see without the starting point.

The first analysis told a clean story with three parts.

**Deception rose with intensity.** On ComputerUse (E1a), the share of episodes in which the agent completed the task but was deceived rose steadily from control to aggressive: 0, 9, 23 and 38%. BrowserUse (E1b) showed the same shape at a lower level: 5, 8, 15 and 26%. Two architectures and four points, both monotone. It looked like the agents were responding to how hard the manipulation pushed.

**Some patterns worked and others did not.** Overall, 17.5% of ComputerUse episodes and 13.5% of BrowserUse episodes ended in deception. On the smaller Llama-3.1-8B, which was tested at aggressive intensity only, the figure was 42.0%. Behind these averages, the patterns split into two groups. The ones that hide or distort information deceived the agent often. On ComputerUse, SaaS billing deceived it in 55.0% of episodes, the trick question in 42.5%, drip pricing in 25.0% and bait-and-switch in 22.5%. The ones that work through presentation or emotion barely registered: interface interference, nagging and the subscription trap never deceived it, and confirm shaming did so once in 40 episodes. The reading we drew was that agents are vulnerable to what they are told but not to how it is shown or how it makes them feel.

**Hindi made it worse.** With English instructions throughout, deception was 20.7% on an English interface, 26.7% on a Hinglish one and 36.0% on a Hindi one. A paired comparison of the same configurations in English and Hindi found 26 pairs in which only the Hindi episode was deceived against 3 the other way (McNemar's exact test, $p = 1.5 \times 10^{-5}$). With the instruction translated into Hindi as well, the rate reached 73.3%.

Each of these findings would have been worth reporting. A dose-response curve suggests a mechanism, a split between pattern types suggests where protection should focus, and a language gap raises a fairness problem for agents acting on behalf of Indian consumers. All three were also consistent with prior work on agents and dark patterns. That consistency is part of why we did not question them sooner.
