# docs/audit — reading order

The audit trail for the pre-submission review of Armavour. Read the reports in this order. Each entry says what the report established and what, if anything, later replaces it.

**Old names.** Reports 01–03 were written at the repo root under other names, and older documents still cite them that way. The scripts, `FOLLOWUP_REPORT.md`, `SPEC_DIVERGENCE.md`, `CORRECTED_TABLES.md` and `docs/paper/NUMBERS.md` all do this. Those citations are left as written:

| cited as | file here |
|---|---|
| `ARMAVOUR_STATUS_REPORT.md` | `01_STATUS_REPORT.md` (restored from `156682a^`) |
| `AUDIT_F6_F8.md` | `02_AUDIT_F6_F8.md` |
| `SPRINT_REPORT.md` | `03_SPRINT_REPORT.md` (restored from `5266063^`) |

## Audit of the original matrix (`matrix-full-e1e2`)

| # | report | what it established | superseded by |
|---|---|---|---|
| 01 | [`01_STATUS_REPORT.md`](01_STATUS_REPORT.md) | First repo audit (2026-10-01). The paper's table numbers match the exported CSVs. It raised the open validity problems: the config leak (F6), judge provenance (F7) and code drift (F8). | 02 and 03 on F6–F8; `CORRECTED_TABLES.md` for the result numbers |
| 02 | [`02_AUDIT_F6_F8.md`](02_AUDIT_F6_F8.md) | Data audit of F6, F7 and F8 on the restored `armavour_audit` DB. It covers how the dump was repaired, a leak-term search of the traces, which judge actually scored the matrix, and a timeline of code drift inside the run. | Consolidated into 03, the same-day sprint |
| 03 | [`03_SPRINT_REPORT.md`](03_SPRINT_REPORT.md) | Deadline sprint. F6: no evidence the leak influenced matrix agents. F7: the judge was a gpt-oss-family model, not llama-3.1-8b. Harness leak fixes, leak-ablation and re-judge scripts, and a "survives / confounded / unknown" classification of paper results. | `FOLLOWUP_REPORT.md` on E1b EF; `CORRECTED_TABLES.md` for the numbers |
| — | [`FOLLOWUP_REPORT.md`](FOLLOWUP_REPORT.md) | The E1b EF rate is not completion-signal contamination; the E1b step budget was most likely 5. Abandoned subscription_trap episodes are scored as safe. Adds the two-arm leak-ablation runner and its analysis. | `SCORING_V2.md` replaces the no-oracle "avoided" rule for new data |
| — | [`SPEC_DIVERGENCE.md`](SPEC_DIVERGENCE.md) | Spec-vs-implementation audit of all 12 patterns, with cross-cutting scoring defects C1 (no oracle → avoided) and C2 (abandon → EC). Lists the BREAKING cells: no faithful path, or inverted scoring. | §12 Hinglish trick_question corrected in `CORRECTED_TABLES.md`; four patterns repaired in `FIXES.md` |
| — | [`CORRECTED_TABLES.md`](CORRECTED_TABLES.md) | Matrix tables recomputed with the BREAKING cells excluded. The drip "reversal" is an artefact, and monotone dose-response is not supported. Several headline rates shrink. | Not superseded. The rerun below is a separate experiment on a different model, not a replacement for these numbers. |

## Corrected rerun (baseline vs fixed testbed, qwen, T = 0.7)

| report | what it established | superseded by |
|---|---|---|
| [`FIXES.md`](FIXES.md) | The four testbed fixes (drip_pricing aggressive, saas_billing, trick_question, nagging), each tied to its SPEC_DIVERGENCE finding and spec lines | — |
| [`PATH_CHECKS.md`](PATH_CHECKS.md) | Scripted, no-LLM check. In the fixed variant every scored cell has a faithful path scored avoided and a deceived path scored deceived. In the baseline exactly the 12 BREAKING cells fail. | — |
| [`SCORING_V2.md`](SCORING_V2.md) | Outcome codes EC/DC/DF/RF/NC. Missing ground truth is never scored "avoided", abandon controls count as RF, and NC is excluded from denominators. | — |
| [`RERUN_PREREG.md`](RERUN_PREREG.md) | Pre-registration (H1–H3, the analysis, exclusions), frozen against code commit `43d5660`, with its deviations recorded | — |
| [`RERUN_RESULTS.md`](RERUN_RESULTS.md) | Results of the 800 episodes. H1 supported. H2 (monotone dose-response) not supported. H3 inconclusive. No untouched-pattern cell differs between variants. | — |

`RERUN_STATUS.md` is the phase-by-phase work log of the rerun and lists every file it created or changed. Read it only for provenance.

## Evidence

| file | what |
|---|---|
| [`evidence/analysis_output.txt`](evidence/analysis_output.txt) | UTF-16 stdout of the original `scripts/analysis.py` run on `matrix-full-e1e2`, cited by 01. Formerly `analysis_output.txt` at the repo root. |
| [`evidence/crashes_ablation-config-01.llama-retired.csv`](evidence/crashes_ablation-config-01.llama-retired.csv) | The 52 `model_not_found` crash rows from the retired llama-3.3-70b ablation attempt, the source of `RET-rows` in `docs/paper/NUMBERS.md`. A tracked copy of the gitignored `results/` file. |
