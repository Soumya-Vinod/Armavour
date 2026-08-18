# Claude Code prompt — Armavour repo work

Paste everything below the line into Claude Code from the repo root
(`D:\BCA\MCA\RESEARCH\armavour`).

---

You are working on **Armavour**, a benchmark measuring whether LLM
computer-use agents fall for dark patterns codified by India's CCPA. Two
developers work on it: I own the testbed (`testbed/src/*.tsx`), pattern
specs (`docs/specs/`), judge rubrics (`docs/rubrics/`), and analysis. My
collaborator owns the harness (`harness/`), adapters, and run
orchestration (`scripts/run_matrix.py`).

**Ground rules**

- A full 1,920-episode matrix has already run. Postgres is the source of
  truth. Do not delete, mutate, or re-run episode data.
- The five interface contracts in `docs/contracts.md` are versioned and
  signed. Do not change them. If a task appears to require changing one,
  stop and tell me.
- Decisions already made are recorded in `docs/decisions.md` and
  `docs/judge_decision_note.md`. Read both before changing evaluation
  logic. Do not re-litigate them.
- `ruff check .` and `python -m pytest` must both pass before you
  consider any task done.
- Where a task is diagnostic, report findings and stop. Do not implement
  a fix for anything under "investigate" without telling me what you
  found first.

---

## Task 0 — Repair the git state (do this first)

The working tree has a merge problem. Diagnose before acting:

```
git status
git log --oneline --graph --all -20
git diff --name-only --diff-filter=U
```

Report what you find: unresolved conflict markers, a half-applied merge,
diverged branches, or something else. Then:

- If there are conflict markers, list every affected file and show me the
  conflicting hunks before resolving anything. Several files were edited
  by both of us recently — `scripts/run_matrix.py`, `harness/judge.py`,
  `harness/evaluator.py`, `harness/adapters/computeruse.py` — and a
  wrong resolution there silently corrupts the run.
- Verify no file contains `<<<<<<<`, `=======`, or `>>>>>>>` after
  resolution.
- Confirm `python -c "import ast,sys; [ast.parse(open(f,encoding='utf-8').read()) for f in sys.argv[1:]]" $(git ls-files '*.py')`
  parses cleanly — a previous truncation left a `for` loop with no body
  and broke the runner.

Do not force-push or rewrite published history.

---

## Task 1 — Wire two new judge rubrics into the judge

I have written `docs/rubrics/interface_interference.md` and
`docs/rubrics/trick_question.md`, replacing placeholder stubs. They
follow the same structure as the existing `false_urgency.md` and
`confirm_shaming.md`.

`harness/judge.py`'s `_template_values()` currently only populates
placeholders for `false_urgency` and `confirm_shaming`. The new rubrics
will therefore raise in `_assert_no_unformatted_placeholders`.

Add branches for both patterns. The placeholders they use:

- `interface_interference`: `{favoured_option_label}`,
  `{user_option_label}`, `{final_choice}` (plus the shared
  `{task_prompt}` and `{agent_trace}`)
- `trick_question`: `{trick_label}`, `{required_state}`,
  `{final_state}` (plus the shared two)

Populate them from `oracle_result` and `extracted_elements`, following
the existing `_confirm_shaming_label` / `_context_for_item` helpers as
the pattern. Read `docs/specs/interface_interference.md` §5 and
`docs/specs/trick_question.md` §5 for the exact oracle field names —
do not guess them.

Also note: `evaluator.py`'s `SOFT_PATTERNS` set currently contains only
`false_urgency` and `confirm_shaming`. Adding these two patterns to it
would change how ~270 already-scored episodes are evaluated. **Do not
add them.** Report what adding them would imply and let me decide.

Add tests to `tests/test_judge.py` (or create it) covering placeholder
population for both new patterns, including the case where an expected
oracle field is missing.

---

## Task 2 — Investigate the `avoided` default on the no-oracle path

**Investigate and report. Do not fix without telling me first.**

Analysis of the Postgres dump (2,208 rows) shows:

| placed | avoided | outcome | n |
|---|---|---|---|
| t | t | EC | 1584 |
| t | f | DC | 519 |
| f | t | EF | 68 |
| NULL | NULL | NULL | 36 |
| f | NULL | NULL | 1 |

`(placed=false, avoided=false)` never occurs, so `DF` is unreachable.

Read the current `harness/evaluator.py` and establish:

1. Exactly how `placed` and `avoided` are derived when
   `read_oracle_result` returns `None`. There was a change to this path
   (there is a `test-ef-fix` run_id in the data) and I have only read an
   older version of the file.
2. Whether `avoided=True` is assigned unconditionally on that path. If
   so, every early termination counts as having avoided the dark
   pattern — including five 8B `basket_sneaking` episodes that looped
   the same `uncheck` action for 20 steps until the step budget expired.
   Those did not avoid anything.
3. Whether `DF` is unreachable by construction or merely unobserved.
4. Whether `terminal_reason` (set by `computeruse.py`) is available at
   the point `avoided` is decided. If it is, a principled refusal
   (`action_none`, `explicit_done`) could be distinguished from a
   step-budget timeout (`normal_completion` at max steps) — but that is
   a scoring-semantics change and needs both devs to agree.

Write your findings to `docs/ef_df_analysis.md`. Include the code path,
the row counts above, and the specific line where `avoided` is set.

---

## Task 3 — Distinguish TPD from TPM in rate-limit handling

Groq returns two different rate limits. Tokens-per-minute recovers in
seconds; tokens-per-day does not. The current retry logic in
`harness/runner.py` (`_is_rate_limit_error`, `_rate_limit_backoff_s`) and
`harness/providers/key_pool.py` treats them identically, so a TPD
exhaustion burns three retries at 30/60/120s against a limit whose own
error text says "try again in 16m25s", then converts the episode to a
crash row.

Add TPD detection. The error body contains
`"on tokens per day (TPD)"` and a `Please try again in Xm Ys` hint.
Behaviour on TPD:

- Do not retry with second-scale backoff.
- If a key pool is in use and other keys remain, rotate immediately.
- If all keys are exhausted on TPD, halt the batch cleanly with the
  existing interrupted-run summary and resume instructions, rather than
  converting every remaining episode into a crash row.

Add tests to `tests/test_key_pool.py` covering TPD vs TPM
classification and the halt-on-exhaustion path.

---

## Task 4 — Analysis script for the results tables

Create `scripts/analysis.py`. It reads from Postgres via
`harness/logger.py`'s `engine_from_env()` and prints (and writes CSV to
`results/analysis/`) the following. It must not mutate the database.

Each table needs explicit `n` per cell and must not pool across
experiment arms — arms differ in intensity coverage, language, and
model, so pooled tables confound the variables.

1. **Intensity gradient, E1a only** (computeruse, English,
   llama-3.3-70b, `matrix-full-e1e2`): DC rate by intensity, `n` per
   cell. Expect n=120 each.
2. **Pattern table, E1a only**, equal n per pattern. Expect n=40. Flag
   any pattern whose n differs.
3. **Language table.** Report the five conditions separately, do not
   collapse them:
   - en instruction + en UI
   - en instruction + hinglish UI
   - en instruction + hi UI
   - hinglish instruction + hinglish UI
   - hi instruction + hi UI
4. **Paired language comparison.** For the seed-matched triplets
   (E2, English instruction, varying UI), compute McNemar's test for
   en-vs-hi and en-vs-hinglish, reporting discordant pair counts and
   the p-value. Verify the pairing actually matches on
   (pattern, intensity, seed) before computing — do not assume.
5. **Control-condition deceptions.** List every DC in a `control`
   intensity with arm, pattern, agent, and language. Control is the
   honest interface, so any DC there is a comprehension or execution
   failure, not deception.
6. **EF breakdown** by arm, agent, pattern, `steps`, and
   `terminal_reason` extracted from the trace JSON.
7. **Excluded patterns.** `disguised_advertisement` and `false_urgency`
   are structurally unmeasurable under spec v1 — see
   `docs/specs/disguised_advertisement.md` §10. Exclude them from every
   aggregate and print them in a separate clearly-labelled section.
   Read `disguised_advertisement` v2 results from run_id
   `rerun-disguised-ad-v2` only.

---

## Task 5 — Investigate two E1b anomalies

**Investigate and report only.**

E1b (browseruse, 480 episodes) shows two things E1a does not:

1. **EF rate is 10.0% (48/480) against E1a's 0.6% (3/487)** — a 16×
   difference. Pull the traces and establish whether these are genuine
   voluntary early termination by the agent, or a structural property of
   the browseruse adapter (e.g. `agent.run()` returning before the
   oracle is set, the keep_alive/oracle-copy path in
   `harness/adapters/browseruse.py` failing silently, or a max-steps
   difference).
2. **Control intensity produced 5 DC** (3 `trick_question`,
   2 `saas_billing`) where E1a control produced 0/120. Control renders
   the honest interface, so there is nothing to fall for. Determine
   whether the control variant renders differently under browseruse, or
   whether the oracle result is being read or copied incorrectly through
   that adapter.

This matters because E1b exists to establish that findings are about
agents rather than about one adapter's extraction layer. If E1b's
outcomes are partly adapter artefacts, that claim does not hold.

Write findings to `docs/e1b_analysis.md`.

---

## Task 6 — Small cleanups

- `.env.example` still recommends `groq/llama-3.1-8b-instant` as the
  judge model in its comments. The judge is standardised on
  `groq/openai/gpt-oss-120b` (see `docs/decisions.md`, 2026-08-06);
  8b-instant is retained only as a historical baseline. Update the
  comments and the default.
- Confirm `CHHAL_PRICE_IN` / `CHHAL_PRICE_OUT` remain commented out in
  `.env.example`. They short-circuit `calculate_cost_usd()` before
  LiteLLM's per-model lookup, and were previously set to Sonnet rates,
  which mispriced every Groq episode.
- `results/` and `.checkpoints/` are gitignored, but `results/` holds
  the run manifests and environment fingerprints that are the
  reproducibility record. Report whether those artefacts are being
  preserved anywhere, and propose an approach — do not change
  `.gitignore` unilaterally.

---

## Order and reporting

Do Task 0 first and stop for my confirmation before continuing. After
that, Tasks 1, 3, 4, 6 are implementation; Tasks 2 and 5 are diagnostic
and end in a written report, not a code change.

For each task, tell me what you changed, what you ran to verify it, and
anything you found that contradicts what I've told you above. I would
rather hear that my description of the code is out of date than have you
work around it — that has already happened once in this project.
#extra line