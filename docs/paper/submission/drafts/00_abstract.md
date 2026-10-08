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

AI agents increasingly shop and sign up for services on people's behalf, and the pages they use can contain dark patterns: designs that steer users against their own interests. We built a benchmark from India's 2023 dark-pattern guidelines, with twelve legally defined patterns at four intensities, in English, Hindi and Hinglish. Its first run of 1,928 episodes suggested that deception rose with intensity, that some kinds of pattern worked and others did not, and that agents were deceived more often on Hindi pages. An audit showed that most of this came from how the benchmark was built: some items could not be passed without being scored as deceived, and one scored correct readings as deception. When we repaired four items and ran the original and repaired testbeds side by side on the same model, the original reproduced a clean dose-response curve and the repaired one did not. We describe five classes of failure, each with a check that would detect it, and release the testbed, audit scripts and executable item checks. One finding survives in a new form, on two models: agents instructed in Hindi fail even on pages with no manipulation, because they misread them.
