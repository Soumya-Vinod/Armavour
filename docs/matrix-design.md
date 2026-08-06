# Full Matrix Design — E1 + E2

**Status:** agreed by both devs. Config generation proceeds against this
document. Amendments require a heads-up, not a silent edit.

---

## Design principles

1. **E1 and E2 answer different questions and are not unified into a
   single cross-product.** E1 asks *which patterns deceive agents, and
   how much does intensity matter*. E2 asks *does language change
   susceptibility*. A full cross-product would spend roughly half the
   budget on language arms for patterns where the manipulation is
   structural rather than linguistic.
2. **Language variation is only run where the manipulation is carried by
   language.** Running Hindi/Hinglish on drip_pricing or basket_sneaking
   would mostly measure translation noise.
3. **Seeds are held at 10 and spent surgically.** If specific cells come
   back ambiguous after E1, seeds are added to those cells rather than
   raised across the board.

---

## E1 — Susceptibility matrix (English only)

**Purpose:** establish the pattern-level DPSR ranking and the
intensity/disclosure-friction findings with enough power to report.

E1 runs as **two sequential batches**, not one interleaved run.
`browseruse` has had enough reliability issues that a mid-run failure
should not be able to touch `computeruse` data.

### E1a — computeruse

| Axis | Values | Count |
|---|---|---|
| Patterns | all 12 | 12 |
| Intensities | control, subtle, moderate, aggressive | 4 |
| Language | en | 1 |
| Agent | computeruse | 1 |
| Seeds | 10 | 10 |

**E1a total: 480 episodes**

### E1b — browseruse

Same matrix, run only after E1a completes and is verified.

**E1b total: 480 episodes**

### Notes

- **Control is included.** The pilots ran 3 intensities; control is the
  baseline that makes DPSR interpretable ("deception above what the
  honest UI produces"). Omitting it weakens every claim.
- **`agente` is excluded.** Still a stub — no PyPI package exists
  (see `decisions.md`, 2026-07-16). Excluded until real.
- **`false_urgency` is included.** The extractor-blind-spot hypothesis
  was disproven by diagnostic: `context_text` is populated at every
  intensity, correctly attached to `buy-item-urgent`, and confirmed via
  `_elements_for_prompt()` to reach the model in the prompt JSON. The
  earlier llama-3.3-70b result is model behaviour, not a harness
  artifact. See "Model-dependence finding" below.

---

## E2 — Language arms (language-sensitive patterns only)

**Purpose:** test whether susceptibility differs across EN / HI /
Hinglish for the patterns where the manipulation is linguistic.

**Pattern subset (6):**

| Pattern | Why language-sensitive |
|---|---|
| `trick_question` | Spec calls HI/Hinglish double negatives "the core cross-lingual pattern" |
| `confirm_shaming` | Spec builder note: flat translation would lose the shaming force |
| `interface_interference` | Loaded labels (`ii.acceptRisk`, `ii.scare`) are language-carried |
| `forced_action` | Moderate/aggressive swing is driven by skip-label wording ("continue without" vs "Leave") |
| `false_urgency` | Scarcity/urgency copy is pure language |
| `saas_billing` | Highest DPSR in pilot; tests whether auto-renew fine print survives translation |

**Excluded from E2 (6):** basket_sneaking, drip_pricing,
bait_and_switch, disguised_advertisement, nagging, subscription_trap —
structural or numeric manipulations where language is incidental.

| Axis | Values | Count |
|---|---|---|
| Patterns | 6 language-sensitive | 6 |
| Intensities | control, moderate, aggressive | 3 |
| Languages | en, hi, hinglish | 3 |
| Agent | computeruse | 1 |
| Seeds | 10 | 10 |

**E2 total: 540 episodes**

### Notes

- **Subtle dropped for E2.** Three intensities is enough to establish a
  language × intensity interaction; subtle added least signal in the
  pilots.
- **EN included in E2** even though E1 covers English — E2's EN cells are
  the within-experiment baseline, so the language comparison is
  internally controlled rather than cross-referenced against a different
  seed configuration.
- **One agent for E2.** The language question is about the pattern, not
  the adapter.
- **i18n is E2-ready.** Localization gaps (`ii.acceptRisk` missing from
  the Hindi dict, missing `dp.decline`/`dp.declined` keys) are fixed and
  all language-sensitive strings are native-speaker reviewed. This
  mattered because `t()` falls back to English on a missing key —
  incomplete localization would have silently rendered English mid-run
  and confounded exactly the comparison E2 exists to make.

---

## Cross-model spot-check

One slice re-run on a second model to test whether the DPSR ranking is
model-specific or general: 12 patterns × aggressive × en × computeruse ×
5 seeds.

**Spot-check total: 60 episodes**

Runs **immediately after E1a**, not last — if the ranking turns out to be
strongly model-specific, that changes the interpretation of everything
downstream and is worth knowing before spending ~1,000 more episodes.

---

## Combined total

| Batch | Episodes |
|---|---|
| Smoke test (model pairing validation) | 5 |
| E1a — computeruse | 480 |
| Cross-model spot-check | 60 |
| E1b — browseruse | 480 |
| E2 | 540 |
| **Total** | **1,565** |

---

## Run order

1. Smoke-test the new model pairing (5 episodes) — includes
   `false_urgency` at moderate and aggressive explicitly
2. E1a — computeruse (480)
3. Cross-model spot-check (60)
4. E1b — browseruse (480)
5. E2 (540)

---

## Model selection

**Agent model: `openai/gpt-4o-mini`.**
Cost is negligible at this scale and it is cleaner for reviewer
credibility than a free-tier model. Moving off
`groq/llama-3.3-70b-versatile` also drops the TPM pacing tax
(`CHHAL_GROQ_DELAY_S=8`, and 25s for browseruse), which at 1,565
episodes is material wall-clock time.

**Judge model: `deepseek/deepseek-chat`.**
Satisfies Contract 5 (judge ≠ agent) unambiguously — different provider,
different family. Chosen after a judge-instability problem on
confirm_shaming that rubric tightening only partly resolved (5/15 fixed,
10/15 still misclassified, with near-identical traces returning opposite
verdicts).

**Pairing must be validated before the full run.** A 5-episode smoke
test on the gpt-4o-mini + deepseek-chat pairing runs first.

**Pilot model retained as a comparison arm.** llama-3.3-70b traces are
kept, not superseded — see below.

---

## Model-dependence finding (to capture during the smoke test)

The smoke test is not only a pass/fail gate. During it, capture *why*
the agent chose its action on `false_urgency`:

- If reasoning references the urgency copy ("Only 2 left", "Deal ends in
  05:00"), that is evidence the model attends to `context_text`.
- If it ignores those cues while they are demonstrably present in the
  prompt, that is equally meaningful.

llama-3.3-70b's traces said things like "all buttons have the same text
'Buy'" and "choice seems arbitrary" — which, given `context_text` *was*
in the prompt, indicates the model did not incorporate it, rather than
reading it and being unmoved. Both models' results are preserved.

If gpt-4o-mini attends and llama-3.3-70b does not, the finding is:
**susceptibility depends not only on the presence of the dark pattern
but on whether the underlying model incorporates non-interactive
contextual information during decision making.** That is a stronger
claim than either model's number alone.

---

## Known limitations, accepted deliberately

**The judge is trace-only; it never sees the screenshot.**
`_supports_vision()` returns `False` for all Groq models and otherwise
requires the literal string `"vision"` in the model name —
`deepseek-chat` and `gpt-4o-mini` both fail that check. Contract 5's
signature takes `final_screen`, but in practice the judge has been
trace-only throughout. Accepted for E1/E2 since the chosen judge model
does not support vision regardless. The `_supports_vision()` check is
being fixed separately as a drive-by, but is not blocking.

---

## Operational prerequisites

**Shared Postgres (Render), with `pg_dump` after each batch.**
A shared instance is load-bearing, not convenience: `soft_pilot.py`'s
`completed_config_hashes()` resume path skips already-completed configs
by querying the DB, and across 1,565 episodes with rate-limit
interruptions that path will be used. It only works if both devs point
`DATABASE_URL` at the same instance. Free-tier managed Postgres gets
reaped when idle, so a `pg_dump` after each batch (committed to repo or
Drive) is the durable backup.

**Pricing env vars must stay unset.**
`CHHAL_PRICE_IN` / `CHHAL_PRICE_OUT` short-circuit
`calculate_cost_usd()` before it asks LiteLLM for real per-model
pricing. They were set to Sonnet rates (3.00/15.00), so every pilot cost
figure was Groq usage priced as Sonnet. Both are now commented out in
`.env.example` and in both devs' local `.env` files. Leave them unset so
cost tracking reflects the model actually running.

**Soft-pattern DPSR convention.**
Per `decisions.md`: soft-pattern DPSR is the `judge_flag=True` rate, not
the raw DC rate. Analysis must report three numbers for soft patterns —
EC / genuine-DC (`judge_flag=True`) / task-failure-DC
(`judge_flag=False`).