# The Benchmark

<!--
## 3 The benchmark (~1.5 pp) + Table: 12 patterns, task, success signal
- synthetic testbed, 7 services; episode = pure function of config; config hash as key
- 12 of 13 CCPA patterns; 13th not observable in one session
- per pattern: spec (legal definition, manifestation per intensity, oracle, task, control)
- intensities: control, subtle, moderate, aggressive
- languages: English, Hindi, Hinglish; UI + instruction variants; native-speaker strings
- agents: ComputerUse (element list → one action), BrowserUse (third-party framework)
- outcome scheme from TrickyArena: EC/DC/EF/DF; oracle from page, not agent self-report
- judge for false urgency & confirm shaming only; raw oracle DC primary
- arms: E1a (CU, en, 488), spot-check (8B, 60), E1b (BU, 480), E2 (lang UI, 540), E2a/E2b (localised instruction, 180 each)
- original model: Llama-3.3-70B via Groq, T=0
- excluded before audit: DA, FU (328 episodes) → 1,600 scored
Reviewer challenge: synthetic testbed realism → acknowledge; controlled design is the point.
-->
