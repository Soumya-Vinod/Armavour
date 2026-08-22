# Table reconciliation — armavour_paper.tex vs. scripts/analysis.py

**Status: blocked on live-DB numbers, everything code-side now implemented.**
`matrix-full-e1e2` is not reachable from this environment (see §0).
Structural mismatches — the ones derivable from code + the paper text
alone, no query needed — are resolved below. Every cell that needs an
actual DC-rate/count is marked **NOT VERIFIED** pending the
`scripts/analysis.py` output you'll paste back. `scripts/analysis.py`
gained four new tables (8–11) to close coverage gaps (§2.3), and
`_outcome_summary_row` gained the genuine-DC/task-failure-DC breakout for
`confirm_shaming` (§2.4) — both implemented and tested (31/31
`tests/test_analysis.py` pass, including 13 new tests for this pass; full
repo suite: 99/99).

Five contracts are frozen (`docs/contracts.md`) — nothing here proposes
changing one. Everything below is either a paper-text correction or an
`analysis.py` addition/gap, not a contract change.

---

## 0. Why the value column says NOT VERIFIED

- `run_id='matrix-full-e1e2'` (the real 1,920-episode matrix) is not
  reachable from this environment. The only Postgres this session can
  reach is the local `armavour-db` Docker container (`localhost:5433`,
  healthy) — it holds 50 rows, all `demo-*`/`rerun-*` run_ids, zero rows
  for `matrix-full-e1e2`. Same limitation the previous session hit and
  documented in `docs/ef_df_analysis.md` / `docs/e1b_analysis.md`.
- Unrelated but worth flagging: this checkout's `.env` is corrupted — it's
  byte-for-byte identical (same size, same MD5) to
  `docs/GATE3_FINDINGS.md`. No `DATABASE_URL`, no keys, nothing real in
  it. `.env` is gitignored, so this is local to this checkout, not
  something in git — but if you hit `RuntimeError: DATABASE_URL is
  required` when you run the command in §4, that's why: restore `.env`
  from `.env.example` (or just `export`/set `DATABASE_URL` directly)
  before running.

---

## 1. Two specific checks

### 1a. Does the intensity gradient (Table II / `tab:intensity`) count the two excluded patterns?

**Yes — confirmed from code, no DB needed, and you've already agreed this
is a paper bug, not a data bug.** `analysis.py`'s own
`table_intensity_gradient_e1a` computes two different `n`s per cell and
keeps them separate on purpose:

- `n_raw_all_12_patterns` — every pattern, expected 120 (12 patterns × 10
  seeds). Diagnostic only.
- `n` / `n_scored` / `DC` / `dc_rate` — `disguised_advertisement` and
  `false_urgency` dropped via `EXCLUDED_PATTERNS`, expected **100** (10
  patterns × 10 seeds).

The paper's Table II caption states "n=120 per cell" as the one and only
denominator — there's no split. That number is only reachable by *not*
excluding the two patterns, which contradicts Table III's explicit
"Excluded as unmeasurable" footnote for the same two patterns two pages
later. Table III (`tab:patterns`) is internally consistent with
`EXCLUDED_PATTERNS`; Table II (`tab:intensity`) is not.

**Resolution (per your instruction):** the paper is wrong, exclusion
should be consistent everywhere → Table II becomes n=100/cell. Once you
paste the real output, I'll pull the dc_rate values from
`table_intensity_gradient_e1a_e1b`'s `e1a_dc_rate`/`e1b_dc_rate` columns
(new Table 9b, §2.3) — those are already computed on the n=100 scored
basis, so no further filtering needed on your end.

### 1b. Is Table 4b (unmatched McNemar keys) empty?

**Cannot confirm — needs live data.** `table_paired_language_mcnemar`
does verify the (pattern, intensity, seed) pairing explicitly rather than
assume it (`merged["_merge"] != "both"` → `unmatched`), so the check
itself is sound; I just don't have real rows to run it against. Two ways
this could come back non-empty against the real data, both worth knowing
in advance:

- A `(pattern, intensity, seed)` key present on the `en` side but missing
  on the `hi`/`hinglish` side (or vice versa) — e.g. a crash row that
  never got a paired rerun, or a seed range that doesn't actually line up
  the way `docs/decisions.md`'s seed-block derivation assumes for `ui_lang
  == 'en'` rows (which never go through `_derive_instruction_language`'s
  seed check at all — only `hi`/`hinglish` rows do, so an `en` row is
  trusted as `instruction_language='en'` unconditionally).
- If it *is* non-empty, the discordant-pair counts (b, c) in the summary
  table are computed only from `usable` (the matched subset with both
  outcomes scored), so the p-value itself wouldn't silently include an
  unmatched key — but a non-trivial unmatched count would mean the pairing
  is losing real data, which is a design problem worth knowing about even
  if the p-value stays technically correct on what's left.

Run `python scripts/analysis.py` and paste the "Table 4b" block (or just
tell me its row count) and I'll confirm this directly.

---

## 2. Structural mismatches (resolved without DB access)

### 2.1 — Global n inflation from inconsistent pattern exclusion

**Paper wrong, per your call.** Four numbers in the paper are built on
"all patterns" rather than the "excluded-pattern-free" basis
`EXCLUDED_PATTERNS` enforces everywhere in `analysis.py`:

| Paper location | Stated n | Consistent-exclusion n | Basis |
|---|---|---|---|
| Table I, E1a row | 487 | 480 (established last session — 8 surplus `false_urgency`/control/en rerun rows, distinct config_hashes) | separate issue from exclusion, see 2.1a below |
| Table I, Total | 1,927 | 1,920 | sum of the six arms as run |
| Table II caption | 120/cell | 100/cell | 12 patterns → 10, excluding `disguised_advertisement`+`false_urgency` |
| Table IV, each of 5 rows | 180 | 150 | E2's 6 language-sensitive patterns → 5, excluding `false_urgency` (`disguised_advertisement` isn't one of the six) |

**2.1a — the 487 vs. 480 figure specifically doesn't reconcile to 8.**
487 − 480 = **7**, not 8. Previous session's finding (relayed in your
task prompt) says "the 8 surplus rows are `false_urgency`/control/en
reruns." I can't adjudicate 7 vs. 8 without the DB — flagging so it
doesn't get silently smoothed over when you paste the real count. Table
8 (§2.3) reports `n_raw_all_patterns` per arm directly, which will settle
this either way.

Table III (`tab:patterns`, n=40/cell) and the corresponding
`table_pattern_e1a` column are already correct on this basis — that's the
fix the previous session already made (pooled n=135/45 → E1a-only n=40).
This is the same fix applied consistently to the other four numbers
above.

### 2.2 — McNemar test method: paper text doesn't match `analysis.py`

**Paper wrong, per your call.** The paper's prose (§ Language degradation)
states the en-vs-hi comparison as "χ²=16.69, p=0.000044" — that's a
continuity-corrected McNemar chi-square test. Checked directly: for
b=26, c=3 (the paper's own discordant-pair counts),
`(|26−3|−1)² / 29 = 16.6897` and `chi2.sf(16.6897, df=1) = 4.40e-05` —
matches the paper's stated numbers almost exactly, confirming *that's*
the method the paper's prose numbers came from.

`table_paired_language_mcnemar` in `analysis.py` does not do this — it
calls `scipy.stats.binomtest(min(b,c), b+c, 0.5, alternative='two-sided')`,
an **exact binomial (sign) test**, not a chi-square test, and never
computes a χ² statistic at all. For the same b=26, c=3 the exact test
gives **p=1.52e-05**, about 3× smaller than the continuity-corrected
figure the paper prints. Both clear any reasonable significance
threshold, so the qualitative claim survives either way, but the printed
number is method-dependent and the paper's number isn't what the code
that's supposed to back it actually computes.

**Resolution — agreed, no code change needed here.** `analysis.py`'s
exact binomial test was already the right call (better choice at b+c=29 —
the chi-square's asymptotic approximation is marginal there); the paper's
method sentence changes, not the code. For b=26, c=3 specifically the
exact test gives **p=1.5236437320709229e-05** (computed directly above,
`stats.binomtest(3, 29, 0.5, alternative='two-sided').pvalue`) — report
this as **p=1.52e-05** (or the fuller value if you want more sig figs),
with no χ² statistic, since the exact test doesn't produce one. This
number assumes the paper's own b=26/c=3 are correct; `mcnemar_exact_p_value`
in your pasted Table 4 output will give the real figure against the
matrix-full-e1e2 data, which is what should actually go in the paper —
1.52e-05 is only a sanity-check value computed from the paper's already-
published (b, c), useful for confirming the two methods disagree, not a
substitute for the real run's output.

### 2.3 — Coverage gaps: `tab:overall`, E1b columns, `tab:langpattern` (now closed)

Before this pass, `analysis.py` had no function producing any of these
three shapes at all — not a numeric mismatch, a missing computation:

- **`tab:overall`** — nothing computed "outcome distribution by arm"
  across all six arms; Tables 1–7 never touch Spotcheck/E2/E2a/E2b outcome
  distributions as a group.
- **E1b columns in `tab:intensity`/`tab:patterns`** — `table_1`/`table_2`
  are explicitly E1a-only by name and docstring; nothing produced the
  parallel E1b numbers the paper's tables put in a second column.
- **`tab:langpattern`** — `table_language_conditions` (Table 3) pools all
  patterns into one number per language condition; nothing broke it out
  per pattern the way the paper's Table V does.

**Added this pass** (same file, same exclusion rule, no pooling across
arms — per your instruction):

| New function | Emits as | Matches |
|---|---|---|
| `table_outcome_by_arm` | Table 8 | `tab:overall` — one row per arm, `n_raw_all_patterns` kept separate from the scored `n`/`EC`/`DC`/`EF`/`DF`/`dc_rate` |
| `table_intensity_gradient_e1b` | Table 9a | E1b half of `tab:intensity`, parallel to the existing E1a-only Table 1 |
| `table_intensity_gradient_e1a_e1b` | Table 9b | `tab:intensity`'s exact wide shape — intensity rows, E1a/E1b dc_rate columns, both on the n=100/cell scored basis |
| `table_pattern_e1b` | Table 10a | E1b half of `tab:patterns`, parallel to the existing E1a-only Table 2 |
| `table_pattern_e1a_e1b` | Table 10b | `tab:patterns`'s exact wide shape — pattern rows, E1a/E1b dc_rate columns, n=40/cell, excluded patterns simply absent as rows (add "---" at presentation time, not by feeding them in) |
| `table_language_by_pattern` | Table 11 | `tab:langpattern` — E2 arm, `instruction_language='en'` only, grouped by (pattern, ui_language), n=30/cell expected |

18 pre-existing tests in `tests/test_analysis.py` still pass unchanged
(nothing pinned to the tables I touched was modified — the new functions
are additive, not refactors of `table_intensity_gradient_e1a`/
`table_pattern_e1a`). Smoke-tested all four against a synthetic
DataFrame; output shapes are correct (see conversation for the run).

**One thing this surfaced that's outside this task's five labels but
worth noting:** `table_language_by_pattern` will emit 5 pattern rows for
E2 (`trick_question`, `confirm_shaming`, `interface_interference`,
`forced_action`, `saas_billing` — `false_urgency` excluded), but the
paper's Table V shows only 3 (`forced_action`, `saas_billing`,
`trick_question`). That may be a deliberate "show the patterns that
actually move" choice on your part (`interface_interference` is 0%
everywhere per the paper's own §Nulls) — flagging so the 2-row gap isn't
mistaken for a bug once you see the full 5-row output.

### 2.4 — `confirm_shaming`'s DC rate: three-way breakout implemented

**Found unasked while tracing why `tab:langpattern` would include
`confirm_shaming` at all; now fixed, per your instruction.**

`docs/decisions.md` #4 (2026-08-05): *"Soft-pattern DPSR is defined as
the judge_flag=True rate, not the raw DC rate... Analysis must report
soft patterns as three numbers: EC / genuine-DC (judge_flag=True) /
task-failure-DC (judge_flag=False)."* The paper's own Judge section says
the same in prose. `analysis.py` never referenced `judge_flag` anywhere
in the file before this pass — every pooled `dc_rate` that includes
`confirm_shaming` (Tables I, II, III, IV, V) was computing its
contribution from raw `outcome == 'DC'`, in direct contradiction of both
the signed decision and the paper's own stated methodology.
`false_urgency` was never affected — it's fully excluded from every
scored table via `EXCLUDED_PATTERNS`, leaving `confirm_shaming` as the
one row this touches, exactly as you said.

**Implemented as the three-way breakout, not a swap** — a silent swap
(replacing `DC`/`dc_rate` in place) would have made a real discrepancy
invisible in exactly the way decision #4 exists to prevent. Instead,
`_outcome_summary_row` (the shared helper every table in the file
funnels through, so this is live in every table `confirm_shaming` touches
— Tables I, II, III, IV, V and the new 8–11 — not just Table III) now
returns three additional columns alongside the untouched `DC`/`dc_rate`:

| Column | Meaning |
|---|---|
| `DC` / `dc_rate` | unchanged — raw `outcome=='DC'` count/rate, exactly as before |
| `DC_genuine` | non-`SOFT_PATTERNS` DC (always genuine, no judge involved) **+** `confirm_shaming` DC rows with `judge_flag=True` |
| `DC_task_failure` | `confirm_shaming` DC rows with `judge_flag=False` — `DC_genuine + DC_task_failure == DC` always |
| `dc_rate_judge` | `DC_genuine / n_scored` — the corrected figure decision #4 calls for; this is what the paper should report, not `dc_rate` |

**The two edge cases you flagged, both handled in `_split_dc_by_judge_flag`:**

- The split only ever activates for rows where `pattern in SOFT_PATTERNS`
  (`harness.evaluator.SOFT_PATTERNS`, imported rather than reimplemented,
  same convention as `get_batch_name_for_config`) — every other pattern's
  DC counts entirely as `DC_genuine`, untouched.
- A `SOFT_PATTERNS` row with a non-null (`completed`) outcome but a null
  or missing `judge_flag` raises `ValueError` rather than being coerced
  into either bucket — this is the crash-row distinction: a genuine crash
  row (`outcome IS NULL`) never went through the judge branch in
  `harness/evaluator.py`, so a null `judge_flag` there is expected and
  doesn't raise; a *scored* soft-pattern row with a null flag is a data
  bug (the judge branch always sets one for any non-crash soft-pattern
  row, regardless of that row's own outcome), and this now fails loud
  instead of silently under- or over-counting.

**Tested:** 7 new tests directly against `_split_dc_by_judge_flag`/
`_outcome_summary_row` (hard-pattern passthrough, genuine/task-failure
split, mixed hard+soft cells, the raise on an explicit null, the raise on
a missing `judge_flag` column entirely, the crash-row non-raise, and the
raw-vs-judge side-by-side reporting), plus the pre-existing
`table_pattern_e1a`/`table_language_conditions`/`table_excluded_patterns`
fixtures updated with realistic `judge_flag` values so they exercise the
real validation path instead of accidentally bypassing it. 31/31 pass.

**Once you paste the real output**, I'll report `confirm_shaming`'s raw
`dc_rate` and corrected `dc_rate_judge` side by side everywhere it
appears (§3), so you can see the size of the discrepancy in the real data
before deciding how the paper's Table III `confirm_shaming` row — and
every pooled Table I/II/IV number it feeds into — gets worded.

### 2.5 — Minor / no action needed

- **Naming:** paper prose says "Spot-check"; the actual arm classifier
  (`scripts/run_matrix.py:get_batch_name_for_config`) returns
  `"Spotcheck"` (no hyphen). Cosmetic, but if you grep the CSVs for
  "Spot-check" you won't find the row.
- **Pre-existing edge case, not a regression:** `table_pattern_e1a` (and
  now `table_pattern_e1b`) raises `KeyError: 'pattern'` if called on a
  completely empty DataFrame (`groupby` on zero rows → `pd.DataFrame([])`
  has no `pattern` column to sort by). Hit this while smoke-testing
  against `--run-id nonexistent-run` on the (empty-for-this-run) local
  DB — won't occur against the real 1,920-row matrix, not touched in this
  pass.

---

## 3. Reconciliation table (as requested)

Every value cell is pending your pasted output. Match/mismatch is filled
in wherever §1–2 already settled it structurally; everything else is
`PENDING`.

### `tab:overall` — Table I, outcome distribution by arm

| Claim in paper | Value from `analysis.py` (Table 8) | Match? |
|---|---|---|
| E1a: n=487, EC 85.0%, DC 14.4%, EF 0.6% | NOT VERIFIED | **MISMATCH on n** (§2.1: 480, not 487 — magnitude of surplus itself unresolved, §2.1a) |
| Spot-check: n=60, EC 56.7%, DC 35.0%, EF 8.3% | NOT VERIFIED | PENDING |
| E1b: n=480, EC 78.8%, DC 11.2%, EF 10.0% | NOT VERIFIED | PENDING |
| E2: n=540, EC 74.8%, DC 23.1%, EF 2.0% | NOT VERIFIED | likely **MISMATCH on n** if Table 8's `n_raw_all_patterns` (540, unscored) was used where a scored 450 belongs — depends whether Table I is meant as raw or scored (§2.1) |
| E2a: n=180, EC 33.3%, DC 66.7%, EF 0.0% | NOT VERIFIED | same open question, scored basis would be 150 |
| E2b: n=180, EC 75.0%, DC 25.0%, EF 0.0% | NOT VERIFIED | same open question, scored basis would be 150 |
| Total: n=1,927 | NOT VERIFIED | **MISMATCH**: established total is 1,920 (§2.1) |

Open question for you: is Table I supposed to be the *raw* per-arm count
(all patterns, including the two excluded — in which case 540/180/180
for E2/E2a/E2b are right and only the E1a 487→480 fix applies) or the
*scored* count (consistent exclusion everywhere, matching Tables II–V —
in which case E2/E2a/E2b drop to 450/150/150 too)? §2.1's "exclusion
should be consistent everywhere" reading argues for the latter, but Table
I reads more like a raw completion-outcome overview than a deception-rate
table, so I didn't want to assume. Table 8 reports both
(`n_raw_all_patterns` and the scored `n`), so you'll have what you need
to decide once you paste it.

### `tab:intensity` — Table II, deception rate by intensity

| Claim in paper | Value from `analysis.py` (Table 9b) | Match? |
|---|---|---|
| Caption: n=120/cell | Table 9b's basis: n=100/cell (scored) | **MISMATCH, resolved** — see §1a/§2.1, paper to be corrected to n=100 |
| Control: E1a 0.0%, E1b 4.2% | NOT VERIFIED | PENDING |
| Subtle: E1a 7.5%, E1b 6.7% | NOT VERIFIED | PENDING |
| Moderate: E1a 19.7%, E1b 12.5% | NOT VERIFIED | PENDING |
| Aggressive: E1a 31.7%, E1b 21.7% | NOT VERIFIED | PENDING |

Note from §2.4: `confirm_shaming` sits inside every one of these pooled
rates. Table 9b's `dc_rate` columns are still the raw figure (unchanged
shape, per your instruction on §1a/§2.1) — the judge-corrected version of
this same pooled number is available from the same cells via
`dc_rate_judge`; I'll report both once you paste the output.

### `tab:patterns` — Table III, deception rate by pattern (n=40/cell)

| Claim in paper | Value from `analysis.py` (Table 10b) | Match? |
|---|---|---|
| 10 scored patterns (Trick question … Nagging), E1a + E1b columns | NOT VERIFIED, all 10 rows | PENDING |
| `confirm_shaming` row specifically: E1a 2.2%, E1b 0.0% | NOT VERIFIED — will report raw `dc_rate` and corrected `dc_rate_judge` side by side (§2.4) | PENDING |
| Disguised advertisement / False urgency: listed as "---" | Absent as rows entirely (not computed, not zero) | matches paper's intent (excluded, not reported as 0%) — confirm the "---" presentation is what you want at LaTeX-generation time |

### `tab:lang` — Table IV, deception rate by language condition

| Claim in paper | Value from `analysis.py` (Table 3 / `table_language_conditions`) | Match? |
|---|---|---|
| n=180 per condition (all 5 rows) | Table 3's basis: n=150 (scored, `false_urgency` excluded) | **MISMATCH, resolved** — see §2.1, paper to be corrected to n=150 |
| EN/EN: 17.2%, EN/Hinglish: 22.2%, EN/Hindi: 30.0%, Hinglish/Hinglish: 25.0%, Hindi/Hindi: 66.7% | NOT VERIFIED | PENDING |
| McNemar EN-vs-Hindi: b=26, c=3, χ²=16.69, p=0.000044 | Table 4's basis: exact binomial, not χ² | **MISMATCH, resolved** — see §2.2, paper's method sentence to be rewritten, p-value to come from `mcnemar_exact_p_value` |
| Table 4b (unmatched keys) | NOT VERIFIED | PENDING — see §1b |

Same `confirm_shaming` caveat as above — it's one of the 5 patterns
pooled into every row here.

### `tab:langpattern` — Table V, language effect by pattern (n=30)

| Claim in paper | Value from `analysis.py` (Table 11, new) | Match? |
|---|---|---|
| Forced action: EN 26.7%, Hinglish 33.3%, Hindi 66.7% | NOT VERIFIED | PENDING |
| SaaS billing: EN 40.0%, Hinglish 66.7%, Hindi 60.0% | NOT VERIFIED | PENDING |
| Trick question: EN 36.7%, Hinglish 33.3%, Hindi 53.3% | NOT VERIFIED | PENDING |
| (paper omits `confirm_shaming`, `interface_interference`) | Table 11 includes both (5 rows total) | not a mismatch — see §2.3's note; confirm the omission is deliberate |

---

## 4. To close this out

Run against the real `matrix-full-e1e2` data (fix/bypass the corrupted
`.env` per §0 first):

```
python scripts/analysis.py
```

(`--run-id` defaults to `matrix-full-e1e2` already, so no flag needed
unless you're pointing at something else.) Paste the full stdout, or at
minimum Tables 1, 2, 3, 4, 4b, 8, 9a, 9b, 10a, 10b, and 11 — everything
this doc's §3 needs. I'll fill in every NOT VERIFIED cell, resolve the
487/480→7-vs-8 discrepancy (§2.1a), settle the Table I raw-vs-scored
question (§2.1), and confirm Table 4b's row count (§1b) against the real
run.
