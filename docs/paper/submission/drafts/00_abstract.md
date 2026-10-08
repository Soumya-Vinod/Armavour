<!--
## Abstract (~200 words, write last)
- agents act for consumers; interfaces contain dark patterns
- benchmark from India's CCPA guidelines: 12 patterns, 4 intensities, 3 languages, 2 architectures, 1,928 episodes
- original headline findings: dose-response, pattern split, language effect
- structured self-audit → most findings artefacts
- controlled rerun: dose-response present on broken testbed, absent after 4 item fixes (same model, same run)
- taxonomy (5 classes) + detection signatures; config-leak ablation; corrected results; released checks
- NOT in abstract: pair-level language p-value
-->

AI agents increasingly shop, subscribe and fill in forms on people's behalf, and the pages they use can contain dark patterns: designs that steer users against their own interests. Whether agents fall for them is a question the field answers with benchmarks. We built one from India's 2023 dark-pattern guidelines, covering twelve legally defined patterns at four intensities, in English, Hindi and Hinglish, with two agent architectures. Its first run, 1,928 episodes, gave three clean findings: deception rose with the intensity of the manipulation, some kinds of pattern worked while others did not, and agents were deceived more often on Hindi pages. We then audited the benchmark, and most of these findings turned out to be products of how it was built. Some items could not be completed without being scored as deceived, and one scored correct readings as deception. To test the audit, we repaired four items and ran the original and repaired testbeds side by side on the same model. The original reproduced a clean dose-response curve. The repaired one did not. We describe five classes of failure, from broken items to leaked test information, each with a check that would detect it. We also report which original findings survive, and release the testbed, the audit scripts and executable checks for every item. One finding survives in a new form, on a second model too: agents instructed in Hindi fail even on pages with no manipulation at all, because they misread them.
