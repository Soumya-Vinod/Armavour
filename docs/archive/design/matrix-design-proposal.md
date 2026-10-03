# Full Matrix Design Proposal — E1 + E2

*Draft for agreement with Dev 2 before config generation. Nothing is
run until both sides sign off, per the "don't re-run anything" goal.*

---

## Design principles

1. **E1 and E2 answer different questions and should not share a
   single undifferentiated matrix.** E1 asks *which patterns deceive
   agents, and how much does intensity matter*. E2 asks *does language
   change susceptibility*. Conflating them means paying full
   cross-product cost on cells neither question needs.
2. **Language variation is only meaningful where the manipulation is
   carried by language.** Running Hindi/Hinglish arms on purely
   structural patterns (drip_pricing, basket_sneaking) mostly measures
   translation noise, not cross-lingual susceptibility.
3. **Seeds buy statistical confidence; they should be spent where the
   variance is.** 5 seeds/cell was adequate at pilot scale; the full
   matrix should raise this where effects are being claimed.

---

## E1 — Susceptibility matrix (English only)

**Purpose:** establish the pattern-level DPSR ranking and the
intensity/disclosure-friction findings with enough power to report
confidently.

| Axis | Values | Count |
|---|---|---|
| Patterns | all 12 | 12 |
| Intensities | control, subtle, moderate, aggressive | 4 |
| Language | en | 1 |
| Agents | computeruse, browseruse | 2 |
| Seeds | 10 | 10 |

**E1 total: 12 × 4 × 1 × 2 × 10 = 960 episodes**

Notes:
- **Control included.** The pilot ran 3 intensities; control is needed
  as the baseline that makes DPSR interpretable ("deception above
  what the honest UI produces"). Skipping it weakens every claim.
- **Two agents, not three.** `agente` is still a stub
  (`NotImplementedError`, not a PyPI package) — exclude until it's
  real. `browseruse` is included because a second agent architecture
  is what lets us claim findings are about *agents*, not about one
  adapter's extraction quirks. Given the false_urgency extraction-gap
  finding, this is now a substantive robustness check, not a nice-to-have.
- **10 seeds, up from 5.** At 5 seeds a cell moves 20% per episode;
  several pilot cells came back 0/5 or 5/5, which is uninformative
  about the true rate. 10 halves that granularity.
- **Single model for E1** (see model section below).

---

## E2 — Language arms (language-sensitive patterns only)

**Purpose:** test whether susceptibility differs across EN / HI /
Hinglish for the patterns where the manipulation is linguistic.

**Proposed pattern subset (6):**
- `trick_question` — spec calls Hindi/Hinglish double negatives "the
  core cross-lingual pattern"
- `confirm_shaming` — spec's builder note: flat translation would lose
  the shaming force
- `interface_interference` — loaded labels (`ii.acceptRisk`,
  `ii.scare`) are language-carried
- `forced_action` — the moderate/aggressive swing is driven by skip-label
  wording ("continue without" vs "Leave"), which is exactly a
  translation-sensitive mechanism
- `false_urgency` — scarcity/urgency copy is pure language
  (*conditional on the extractor fix landing — see blockers*)
- `saas_billing` — highest DPSR in the pilot; worth testing whether
  the auto-renew fine print survives translation

**Excluded from E2 (6):** basket_sneaking, drip_pricing,
bait_and_switch, disguised_advertisement, nagging, subscription_trap —
structural/numeric manipulations where language is incidental.

| Axis | Values | Count |
|---|---|---|
| Patterns | 6 language-sensitive | 6 |
| Intensities | control, moderate, aggressive | 3 |
| Languages | en, hi, hinglish | 3 |
| Agents | computeruse | 1 |
| Seeds | 10 | 10 |

**E2 total: 6 × 3 × 3 × 1 × 10 = 540 episodes**

Notes:
- **Subtle dropped for E2.** Three intensities is enough to establish a
  language × intensity interaction; subtle added least signal in the
  pilot and quadruples nothing useful here.
- **EN included in E2** even though E1 covers English — E2's EN cells
  are the within-experiment baseline, so the language comparison is
  internally controlled rather than cross-referenced against a
  different agent/seed configuration.
- **One agent for E2.** The language question is about the pattern,
  not the adapter; `computeruse` is the validated path.

---

## Combined total

| Experiment | Episodes |
|---|---|
| E1 | 960 |
| E2 | 540 |
| **Total** | **1,500** |

This is below the blueprint's ~3-5k estimate. The reduction comes from
not running language arms on structurally-language-insensitive patterns
and not running a full 4-intensity sweep in E2 — both of which would
have added episodes without adding claims. If we want to spend the
remaining budget, the highest-value use is **more seeds on E1**
(e.g. 20 seeds → 1,920 E1 episodes, 2,460 total), not more cells.

---

## Model selection

**Proposal: run the full matrix on one primary model, plus a small
cross-model spot-check.**

- **Primary: `openai/gpt-4o-mini` or `deepseek/deepseek-chat`.** Per the
  cost table, either lands around $1.60–2.10 at full-matrix scale.
  Both avoid Groq's TPM pacing overhead (~20 min dead time per run),
  which at 1,500 episodes is a material wall-clock cost.
- **Not Groq/llama-3.3-70b for the full matrix.** It was right for the
  pilot (free, fast to iterate) but it produced the repeated-click
  reliability issue and the pacing tax. Keeping it as the pilot model
  and switching for the real run is defensible and worth a
  methods-section sentence.
- **Cross-model spot-check:** re-run one slice (e.g. all 12 patterns ×
  aggressive × en × computeruse × 5 seeds = 60 episodes) on a second
  model to test whether the DPSR ranking is model-specific or general.
  ~$0.10–1.50 depending on model. This is what turns "llama is
  susceptible to X" into "agents are susceptible to X."

**Judge model:** per Contract 5, must differ from the agent model.
If the primary agent model becomes gpt-4o-mini, the judge cannot also
be gpt-4o-mini — needs an explicit different choice (the judge swap
that just resolved the confirm_shaming instability should be
re-validated against whatever the final pairing is).

---

## Blockers before generation

1. **i18n completion.** `ii.acceptRisk` still commented out in the
   Hindi dict (silently falls back to English); minor typo in Hinglish
   `dp.declined`. E2 cannot run on partial localization — the missing
   keys would render English mid-run and confound exactly the
   comparison E2 exists to make.
2. **extract.py fix for non-interactive text.** The false_urgency
   extraction gap means urgency copy never reaches the agent. Until
   fixed, false_urgency should be excluded from both E1 and E2 (or the
   whole matrix delayed). Worth confirming the fix is general
   (surrounding-text context for all elements) rather than
   false_urgency-specific, since the same blind spot could affect any
   pattern whose manipulation lives in non-interactive copy.
3. **Soft-pattern reporting convention.** Per the judge_flag finding:
   DPSR for judge-based patterns = judge_flag=True rate, not raw DC.
   Should be recorded in `decisions.md` before the analysis layer is
   built against the full-matrix data, not after.
4. **Shared data location.** Pilot data currently lives only on one
   machine. At 1,500 episodes this needs settling — shared Postgres
   instance, or an agreed export cadence — before the run, not after.

---

## Open questions for Dev 2

- Agree on E1/E2 split, or prefer one unified matrix?
- 10 seeds, or push to 20 given the budget headroom?
- Primary model preference — gpt-4o-mini vs deepseek-chat?
- Is `browseruse` stable enough post-TPM-fix to carry half of E1, or
  should E1 be computeruse-only with browseruse as a spot-check slice?