# Armavour: repository cleanup plan

Read-only analysis, 2026-10-02. Repo `D:\BCA\MCA\RESEARCH\Armavour`, branch `main` (in sync with `origin/main`), HEAD `559cc9b`. No files were moved, deleted or edited. Only this file and `cleanup_repo.ps1` were created.

## 0. Read this first

1. **The corrected rerun is running in another session right now.** `docs/audit/RERUN_STATUS.md` shows Phase 1 done and Phases 2–7 pending. The rerun has uncommitted edits in `harness/` (3 files) and `testbed/src/` (9 files). While I was working, two new files appeared (`tests/conftest.py`, `tests/test_item_paths.py`). The plan does not touch anything the rerun owns: `harness/`, `testbed/`, `tests/`, `infra/migrations/`, `scripts/`, `docs/specs/`, the existing `docs/audit/*` reports, or any rerun path named in the brief. Even so, run `cleanup_repo.ps1 -DryRun:$false` **only after the rerun is finished and committed.** That way the index stays clean for the rerun's commit.
2. **Some of the brief's assumptions differ from the repo:**
   - `docs/paper/submission/` does not exist yet, so there is nothing in it to flag. §4 says what should go into it.
   - There are no audit reports at the repo root any more. `AUDIT_F6_F8.md` was already moved by hand to `docs/audit/02_AUDIT_F6_F8.md`; the root copy is deleted (unstaged) and the new copy is untracked. The two files are byte-identical (checked with `diff` against `HEAD:AUDIT_F6_F8.md`).
   - `ARMAVOUR_STATUS_REPORT.md` and `SPRINT_REPORT.md` were deleted in commits `156682a` and `5266063`. They exist **only in git history**, but scripts, audits and `NUMBERS.md` still cite them (see ASK-1).
   - `docs/paper/armavour_facct.tex` → `docs/paper/reference_generated_draft.tex` is a staged rename that is already in the index. The plan leaves it alone.
3. **`.env`:** confirmed gitignored (`.gitignore:1`) and never committed (`git log --all -- .env` is empty). I did not open it on purpose. One repo-wide grep did print two comment lines from it (about the default judge model). No values were shown, and every later scan excluded it.
4. **Incident during the dry-run test (09:51).** I ran `cleanup_repo.ps1` once in its default dry-run mode. It printed sections [1]–[4] up to `docs/texput.log` and then failed: `git` was no longer found. Within that same minute, three files disappeared:
   - `C:\Program Files\Git\cmd\git.exe`
   - `C:\Program Files\Git\mingw64\bin\git.exe`
   - `cleanup_repo.ps1` itself

   **What I checked:**
   - Dry-run mode makes no git writes and calls no `Remove-Item`.
   - All repo files are unchanged.
   - A non-admin process cannot delete files in Program Files.

   So this looks like antivirus remediation (probably Windows Defender behaviour monitoring), not the script. I could not confirm that, because reading the Defender history needs admin rights.

   I re-created the script and did not run it again. Before using it:
   - check Windows Security → Protection history, and restore or reinstall Git;
   - expect that running the script may trigger the same reaction.

---

## 1. Inventory

The full per-file inventory is in **Appendix A** at the end of this file: tracked, untracked and ignored, each with size, last-modified time and purpose. Summary:

| group | count / size | notes |
|---|---|---|
| tracked | 195 paths in the index (194 present; `AUDIT_F6_F8.md` deleted in worktree) | code, docs, 11 LaTeX build artefacts, 2 stray Vite cache files |
| untracked | 6 files + 2 empty dirs | 5 owned by the rerun, plus `docs/audit/02_AUDIT_F6_F8.md`; `analysis/` and `papers/` are empty |
| ignored | `.venv/` 588 MB · `testbed/node_modules/` 115 MB · `results/` 846 KB · `logs/` 92 KB · `__pycache__` ×9 ≈ 1.2 MB · `.pytest_cache` 17 KB · `.ruff_cache` 28 KB · `.checkpoints/` 1 KB · `.env` · `.claude/` | `.git/` is 37 MB |

---

## 2. Action table

Legend: **KEEP** (in place) · **MOVE** · **ARCHIVE** (→ `docs/archive/<sub>/`) · **DELETE** · **ASK** (see §5).
A reference marked *frozen* sits inside a dated audit or status record. Leave it as it is, because those records describe the repo as it was when they were written; it is listed only so you know about it. All other references in the last column should be updated by hand after the script runs. The script prints the same list.

### 2a. MOVE / ARCHIVE (implemented in `cleanup_repo.ps1`)

| # | item | action | destination | reason | references to update (file:line) |
|---|---|---|---|---|---|
| M1 | `AUDIT_F6_F8.md` (deleted) + `docs/audit/02_AUDIT_F6_F8.md` (untracked) | MOVE (finish the manual move) | `docs/audit/02_AUDIT_F6_F8.md` | The move was already done by hand. The script stages it (`git rm --cached` old path + `git add` new path), which is what `git mv` would have done. | none to update. `docs/paper/NUMBERS.md:12` already uses the new path. *Frozen:* `SPRINT_REPORT.md` §header (git history only) |
| M2 | `analysis_output.txt` (tracked, UTF-16) | MOVE | `docs/audit/evidence/analysis_output.txt` | Raw stdout of the original `scripts/analysis.py` run. It is evidence for the audits, not a root-level file. Keep the encoding unchanged. | none in the worktree. *Frozen:* `ARMAVOUR_STATUS_REPORT.md:5,125,224` (git history only; matters only if ASK-1 restores it) |
| A1 | `docs/paper/armavour_paper.tex` | ARCHIVE | `docs/archive/paper_ieee/armavour_paper.tex` | Superseded IEEE draft. It holds the original claims that the audits check against. It has no `\input`, so moving it breaks nothing. | `docs/paper/NUMBERS.md:15`; optional, name only: `docs/paper/REVIEW_NOTES.md:125`, `:126`, `docs/paper/DRAFT_STATUS.md:21`, `docs/table_reconciliation.md:1`. *Frozen:* `docs/audit/FOLLOWUP_REPORT.md:128`, `docs/audit/CORRECTED_TABLES.md:489` |
| A2 | `docs/paper/discussion-forced-action-interface-interference.md` | ARCHIVE | `docs/archive/paper_notes/` | Aug-04 pilot discussion draft, superseded by the audits | none |
| A3 | `docs/paper/results-deterministic.md` | ARCHIVE | `docs/archive/paper_notes/` | Aug-04 pilot results draft, superseded | none |
| A4 | `docs/context.md` | ARCHIVE | `docs/archive/phase0/context.md` | Phase-0 "start here" doc and almost entirely stale (§6). README stays as the single entry point. | none |
| A5 | `docs/ChhalBench_TestSpec.xlsx` | ARCHIVE | `docs/archive/phase0/` | Phase-0 CCPA-13 test spec under the old project name, superseded by `docs/specs/*.md`. Archived because specs are never deleted. | `docs/context.md:55`, name only; it moves together with this file |
| A6 | `docs/claude_code_prompt.md` | ARCHIVE | `docs/archive/prompts/` | Aug task prompt for Claude Code, now historical | `docs/e1b_analysis.md:3`, `docs/ef_df_analysis.md:4` (both archived in A8/A9): `docs/claude_code_prompt.md` → `docs/archive/prompts/claude_code_prompt.md` |
| A7 | `docs/matrix-design-proposal.md` | ARCHIVE | `docs/archive/design/` | Draft superseded by the frozen `docs/matrix-design.md` | none |
| A8 | `docs/e1b_analysis.md` | ARCHIVE | `docs/archive/diagnostics_2026-08/` | Aug diagnostic report, superseded by the Oct audits | `docs/table_reconciliation.md:28`. `docs/claude_code_prompt.md:227` is a historical instruction; leave it |
| A9 | `docs/ef_df_analysis.md` | ARCHIVE | `docs/archive/diagnostics_2026-08/` | Same as A8 | `docs/table_reconciliation.md:28`; `docs/e1b_analysis.md:6`, `:64` → `docs/archive/diagnostics_2026-08/ef_df_analysis.md`. `docs/claude_code_prompt.md:131` is a historical instruction; leave it |

### 2b. DELETE (implemented in `cleanup_repo.ps1`)

| # | item | state | method | reason | references |
|---|---|---|---|---|---|
| D1 | `all_context.txt` | tracked | `git rm` | Aug-08 paste-dump of `run_matrix.py`, `key_pool.py`, `test_key_pool.py`, `.gitignore`. A stale duplicate of code. | none |
| D2 | `demo_run.log` | tracked | `git rm` | Jul-19 demo log (5 episodes, LiteLLM errors). Not cited anywhere. Contains local user paths. | none |
| D3 | `docs/texput.log` | tracked | `git rm` | Empty pdflatex "Emergency stop" log | none |
| D4 | `docs/paper/armavour_facct.{aux,bbl,blg,fdb_latexmk,fls,log,out,pdf}` (8 files) | tracked | `git rm` | Build output of the old `armavour_facct.tex`, which is now the reference draft. The source has been renamed, so these files match nothing. They also embed `C:/Users/SOUMYA/...` paths. | only each other |
| D5 | `docs/paper/armavour_paper.{aux,log,pdf}` (3 files) | tracked | `git rm` | IEEE draft build output from Aug 22. The PDF is older than the `.tex` (edited Oct 1), so it is stale. Rebuild from the archived `.tex` if needed. | none |
| D6 | `testbed-app/.vite/deps/{_metadata.json,package.json}` | tracked | `git rm` | Stray Vite dep-cache from a Jul-4 scaffold in the wrong folder. The string `testbed-app` in `testbed/package.json`, `package-lock.json` and `index.html` is the npm package name and has nothing to do with this folder. | none |
| D7 | `analysis/`, `papers/` | untracked, empty | `Remove-Item` | Empty placeholder dirs | `README.md:38`, `README.md:41` (layout table rows; remove them) |
| D8 | `.pytest_cache/`, `.ruff_cache/` | untracked caches (see note) | `Remove-Item` | Caches | none |
| D9 | `__pycache__/` ×9 (auditor, harness, harness/adapters, harness/providers, infra/migrations, infra/migrations/versions, scripts, tests) | ignored | `Remove-Item` | Bytecode caches | none |
| D10 | `logs/matrix_ablation-config-01.llama-retired.log`, `logs/matrix_ablation-noconfig-01.llama-retired.log` | ignored | `Remove-Item` | Logs of the abandoned Llama-3.3-70b ablation attempt. Nothing cites them. Delete them as the brief asks, or back them up first (§4). | none |

Note on D8: `.pytest_cache` and `.ruff_cache` are not matched by `.gitignore`. Each carries its own internal `.gitignore` with `*`, which is why git reports them as ignored.

### 2c. KEEP (grouped)

| item(s) | reason |
|---|---|
| `harness/`, `auditor/`, `infra/`, `alembic.ini`, `docker-compose.yml`, `pytest.ini`, `.github/workflows/ci.yml`, `.env.example`, `.gitignore`, `data/` | Live code and config. The rerun is editing `harness/`. |
| `scripts/*` (all 25) | Code. Five are imported by tests (`run_matrix`, `run_leak_ablation`, `analyze_ablation`, `analysis`, `corrected_tables`). The one-off scripts are covered by ASK-4. |
| `tests/*` (incl. untracked rerun tests) | Tests are never moved or deleted |
| `testbed/` (incl. `spike/checkout.html`) | Used by `harness/verify_page.py:6`, `tests/test_evaluator.py:128,135` and CI. The rerun is editing `testbed/src`. `testbed/README.md` is unmodified Vite boilerplate; replacing it is optional. |
| `infra/migrations/versions/0007_oracle_result_variant.py` | Rerun |
| `docs/audit/02_AUDIT_F6_F8.md`, `CORRECTED_TABLES.md`, `FOLLOWUP_REPORT.md`, `SPEC_DIVERGENCE.md`, `RERUN_STATUS.md` | Audit reports, kept under their current names. Renumbering is ASK-2. |
| `docs/contracts.md`, `docs/decisions.md`, `docs/element_ids.md`, `docs/oracle_fields.md`, `docs/rubrics.md`, `docs/rubrics/*`, `docs/specs/*`, `docs/judge_decision_note.md`, `docs/matrix-design.md` | Contracts, decision log and specs |
| `docs/identifier_audit.md` | Cited by code comments: `harness/judge.py:285,309`; `testbed/src/{ConfirmShaming:12, DisguisedAd:7, FalseUrgency:8, InterfaceInterference:12, lib/ids.ts:4}`; `tests/test_identifier_audit.py:9,22,86` |
| `docs/table_reconciliation.md` | Cited by `scripts/analysis.py:27,32,332,662` |
| `docs/GATE3_FINDINGS.md` | Superseded in part (CORRECTED_TABLES Part A shows the drip "reversal" is an artefact), but it is source G3 in `NUMBERS.md:16,244` and cited by `identifier_audit.md:141`, `table_reconciliation.md:31`, `CORRECTED_TABLES.md:36,46`. See ASK-6. |
| `docs/taxonomy_crosswalk.md`, `docs/tier1_extraction_sheets.md` | Phase-0, but still the related-work material for the paper. Stale: the "ChhalBench" name in the title. |
| `docs/legal/*` | Legal sources plus 3 arXiv related-work PDFs, which are the sources for `tier1_extraction_sheets.md` |
| `docs/paper/reference_generated_draft.tex`, `refs.bib`, `tables/*.tex`, `NUMBERS.md`, `DRAFT_STATUS.md`, `REVIEW_NOTES.md` | See §4 and ASK-5 |
| `README.md` | KEEP and update (§6) |
| `results/` (all non-Llama files), `logs/*.log` (non-Llama), `.checkpoints/`, `.env`, `.claude/`, `.venv/`, `testbed/node_modules/` | Ignored runtime and data files. Back them up (§4). |

---

## 3. Audit reports: target names and reading order

| order | target path under `docs/audit/` | today | depends on / cites |
|---|---|---|---|
| 01 | `01_STATUS_REPORT.md` | git history only: `git show 156682a^:ARMAVOUR_STATUS_REPORT.md` | `analysis_output.txt`, `results/analysis/*.csv`, `docs/context.md` |
| 02 | `02_AUDIT_F6_F8.md` | **already in place** (untracked) | `ARMAVOUR_STATUS_REPORT.md` (line 3) |
| 03 | `03_SPRINT_REPORT.md` | git history only: `git show 5266063^:SPRINT_REPORT.md` | `ARMAVOUR_STATUS_REPORT.md`, `AUDIT_F6_F8.md` |
| 04 | `04_FOLLOWUP_REPORT.md` | `FOLLOWUP_REPORT.md` | `SPRINT_REPORT.md` (lines 3,49,60,160,245,270), `docs/paper/armavour_paper.tex:461-475` (line 128) |
| 05 | `05_SPEC_DIVERGENCE.md` | `SPEC_DIVERGENCE.md` | `SPRINT_REPORT.md` (line 5), `FOLLOWUP_REPORT.md` (lines 308,317) |
| 06 | `06_CORRECTED_TABLES.md` | `CORRECTED_TABLES.md` | `SPEC_DIVERGENCE.md`, `FOLLOWUP_REPORT.md`, `SPRINT_REPORT.md` (line 3; also 69,75,489), `GATE3_FINDINGS.md` (36,46) |
| 07+ | `FIXES.md`, `PATH_CHECKS.md`, `SCORING_V2.md`, `RERUN_PREREG.md`, `RERUN_STATUS.md`, `RERUN_RESULTS.md` | rerun (some still to be written) | **Do not rename.** The rerun creates and cites these exact paths. List them unnumbered in the index, after 06. |
| evidence | `evidence/analysis_output.txt` | root (M2) | — |

**Cross-references that would break if 04–06 were renamed** (this is why the renames are ASK-2 and not in the script):
- `docs/audit/CORRECTED_TABLES.md:3` → SPEC_DIVERGENCE, FOLLOWUP_REPORT
- `docs/audit/CORRECTED_TABLES.md:69` → SPEC_DIVERGENCE
- `docs/audit/CORRECTED_TABLES.md:489` → SPEC_DIVERGENCE
- `docs/audit/SPEC_DIVERGENCE.md:308`, `:317` → FOLLOWUP_REPORT
- `docs/audit/FOLLOWUP_REPORT.md:255` and `docs/audit/CORRECTED_TABLES.md:485` (self-paths in each "files written" table)
- `docs/paper/NUMBERS.md:9`, `:10`, `:11` (live ledger; would need updating)
- `scripts/corrected_tables.py:4`, `:53` (code comments)
- whatever the rerun docs (FIXES, SCORING_V2 …) cite once they are written

**Cross-references that are already broken** because the reports were removed from the root:
- `SPRINT_REPORT.md` is cited by:
  - `scripts/analyze_ablation.py:12`
  - `scripts/rejudge.py:22`
  - `scripts/run_leak_ablation.py:112`
  - `docs/audit/FOLLOWUP_REPORT.md:3,49,60,160,245,270`
  - `docs/audit/SPEC_DIVERGENCE.md:5`
  - `docs/audit/CORRECTED_TABLES.md:3`
- `ARMAVOUR_STATUS_REPORT.md` is cited by `docs/audit/02_AUDIT_F6_F8.md:3`.
- `NUMBERS.md:13–14` already explains how to read both reports from git history.

---

## 4. `docs/paper/`, `analysis_output.txt`, `results/`

**`docs/paper/` after cleanup:**
| file | role |
|---|---|
| `submission/` (to be created by you) | Hand-written single-column acmart paper. It should contain its own `main.tex`, its own `refs.bib` (the current one is 14 unverified `% VERIFY` candidates) and its own `tables/`, or `\input{../tables/...}`. |
| `reference_generated_draft.tex` | Reference only. It must **not** be copied into or `\input` by `submission/`. It `\input`s `tables/T1,T2,T3,T4,T6` and uses `refs.bib`, so those stay next to it. |
| `refs.bib` | Bibliography of the reference draft |
| `tables/T1–T7*.tex` | Generated by `scripts/corrected_tables.py` (`TEX_DIR`, `scripts/corrected_tables.py:51`) from **pre-rerun** data. Rerunning that script overwrites them. Rerun tables (from `scripts/analyze_rerun.py`) should go to a different folder, such as `submission/tables/`, so they do not clobber these. |
| `NUMBERS.md` | Numbers ledger. It is keyed to the reference draft, but its sources are still valid. Pre-rerun numbers; rebuild or extend after the rerun. |
| `DRAFT_STATUS.md`, `REVIEW_NOTES.md` | Companions of the reference draft (ASK-5) |
| build artefacts | All deleted (D4, D5). Add LaTeX ignores to `.gitignore` by hand (§7). |

**`analysis_output.txt`:** move it to `docs/audit/evidence/` (M2), keeping UTF-16. No reference in the worktree points to the root path. The only citation is in `ARMAVOUR_STATUS_REPORT.md`, which is in git history only.

**`results/` (gitignored, 846 KB), reproducible vs stored-only:**
| path | produced by | reproducible? |
|---|---|---|
| `results/analysis/*.csv` (14) | `scripts/analysis.py` | Yes, but only from a DB holding `matrix-full-e1e2` (the `armavour_audit` restore). `corrected_tables.py` checks against these files. |
| `results/analysis_corrected/*` (29) | `scripts/corrected_tables.py` | Yes, from `armavour_audit` |
| `results/ablation/*.csv` (3) | `scripts/analyze_ablation.py` | Yes, from `armavour_ablation` + `armavour_audit` |
| `configs_*.json`, `manifest_*.json`, `manifest_final_*.json`, `environment_*.json`, `matrix_summary_*.{csv,json}` | `scripts/run_matrix.py` at run time | **No.** Provenance snapshots taken at run time. |
| `crashes_ablation-config-01.llama-retired.csv` | `run_matrix.py` | **No.** Cited by `NUMBERS.md:254` (ASK-3). |
| `logs/*.log` | `run_matrix.py` | **No** |

**Back up outside the repo**, for example to `D:\BCA\MCA\RESEARCH\armavour_data\backup_2026-10-02\` plus one off-machine copy:
- all of `results/` and `logs/`, **before** D10;
- the Postgres databases, which are the real source of truth: `pg_dump` of `armavour_audit`, `armavour_ablation`, and later `armavour_rerun`;
- the original dump files that `02_AUDIT_F6_F8.md:9` says are in `C:\Users\SOUMYA\Downloads`;
- `armavour_data\testbed_baseline\`, which is already outside the repo but is still a single copy.

---

## 5. ASK ME (not in the script)

| # | question | my recommendation |
|---|---|---|
| ASK-1 | Restore `ARMAVOUR_STATUS_REPORT.md` and `SPRINT_REPORT.md` from git history as `docs/audit/01_STATUS_REPORT.md` and `03_SPRINT_REPORT.md`? Three scripts, four audits and `NUMBERS.md` cite them, and today those citations only resolve through `git show`. Restoring re-creates content that was deliberately deleted. | **Yes, after the rerun:**<br>`git show 156682a^:ARMAVOUR_STATUS_REPORT.md > docs/audit/01_STATUS_REPORT.md`<br>`git show 5266063^:SPRINT_REPORT.md > docs/audit/03_SPRINT_REPORT.md`<br>In PowerShell, add `\| Set-Content -Encoding utf8`. |
| ASK-2 | Rename `FOLLOWUP_REPORT.md`, `SPEC_DIVERGENCE.md` and `CORRECTED_TABLES.md` to `04_`/`05_`/`06_`? Renaming breaks about a dozen references (§3), and frozen reports would have to be edited to fix them. | **No.** Keep the names and add a `docs/audit/README.md` index with the §3 reading order. That breaks nothing. If you prefer the numbers, rename only after the rerun docs are final. |
| ASK-3 | `results/crashes_ablation-config-01.llama-retired.csv`: the brief lists `*.llama-retired` CSVs as DELETE, but `NUMBERS.md:254` cites this file as the source of a paper number (RET-rows = 52). | Do not delete it. Back it up, or copy it into `docs/audit/evidence/`, which makes it tracked. |
| ASK-4 | One-off scripts: `check_episode_data`, `check_models`, `check_rerun_failure`, `check_traces`, `debug_detector`, `diagnose_context_text`, `trace`, `rerun_disguised_ad`, `rerun_drip_aggressive`, `run_10_e1b`, `verify_judge_parse_error`, `scripts/test_localization.py`. Archive them to `scripts/archive/`? Seven of them use `sys.path.insert(0, ".")` and work only when run from the repo root. | Keep them until after submission. |
| ASK-5 | `docs/paper/DRAFT_STATUS.md` and `REVIEW_NOTES.md` describe the LLM draft. Should they stay next to `reference_generated_draft.tex`, or go to `docs/archive/paper_generated/`? | Keep them. They document the reference draft (compile notes, TODO citations). Optionally retitle them by hand. |
| ASK-6 | `docs/GATE3_FINDINGS.md`: superseded in part, but cited by the live ledger and by two docs. Archive it or keep it? | Keep it. Archiving means editing `NUMBERS.md:16`, `identifier_audit.md:141` and `table_reconciliation.md:31`. |
| ASK-7 | Should `.gitignore` get LaTeX artefacts, `testbed-app/`, `.pytest_cache/` and `.ruff_cache/`? The script does not edit files. | Yes, by hand (§7). |

---

## 6. Stale docs

**`README.md`: KEEP and update.** Stale items:
- line 7: "Private until the arXiv preprint (planned Phase 4)". The repo has a public-style GitHub remote, and the target is now FAccT, deadline 2026-10-27.
- line 22: "Phase 0 — foundation … in progress". The experiments are finished.
- line 26: `docs/armavour_architecture.svg` does not exist.
- lines 38, 41: `analysis/` and `papers/` are empty (D7). Analysis lives in `scripts/` and `results/`.
- line 40 and line 88: `docs/` described as "Blueprint, execution guide". Neither exists.
- missing from the layout table: `scripts/`, `tests/`, `results/`, `logs/`, `docs/audit/`, `docs/paper/`, `docs/archive/`.
- lines 59–66: `agent_spike.py`, `harness/spike_results.csv` and `CHHAL_MODEL` do not exist.
- line 84: the Roadmap is Phase-0 era.
- line 92: `LICENSE` does not exist.
- line 96: `CITATION.cff` does not exist.
- "Team & workflow" names Dev 1 / Dev 2. That is fine for anonymity, but check it.

**`docs/context.md`: ARCHIVE (A4).** Stale items:
- line 7: "private until the arXiv preprint";
- line 24: `docs/armavour_build_spec_detailed.md` and the "division-of-labour doc" do not exist;
- lines 34–37: "Phase 0 … Testbed/harness/auditor not built yet";
- lines 54–55: blueprint, execution guide, `ChhalBench_TestSpec.xlsx`.
- The parts still valid (episode model, five contracts) already appear in `README.md` and `docs/contracts.md`.

**Other Phase-0 material:**
- `ChhalBench_TestSpec.xlsx`: ARCHIVE (A5).
- `taxonomy_crosswalk.md` and `tier1_extraction_sheets.md`: KEEP; only the "ChhalBench" name is stale.
- `testbed/spike/`: KEEP (used by CI and tests).

---

## 7. Manual follow-ups (no file content is edited by the script)

- **Reference updates:** the "references to update" column in §2a. The script prints it as well.
- **`README.md`:** apply §6 and drop the rows at lines 38 and 41.
- **`.gitignore` additions (ASK-7):**
  ```
  .pytest_cache/
  .ruff_cache/
  testbed-app/
  docs/**/*.aux
  docs/**/*.bbl
  docs/**/*.blg
  docs/**/*.fdb_latexmk
  docs/**/*.fls
  docs/**/*.log
  docs/**/*.out
  docs/**/*.synctex.gz
  docs/**/*.pdf
  !docs/legal/*.pdf
  ```
- **After the rerun:** add `docs/audit/README.md` (ASK-2) with the §3 order.

---

## 8. Proposed final tree (top levels; rerun paths shown with ✚)

```
Armavour/
├── .github/workflows/ci.yml
├── .env.example  .gitignore  alembic.ini  docker-compose.yml  pytest.ini  README.md
├── auditor/
├── data/                     (.gitkeep, judge_validation_samples.json)
├── harness/                  (adapters/, providers/, runner.py …)
├── infra/migrations/versions/0001…0006, 0007_oracle_result_variant.py
├── scripts/                  (existing 25)  ✚ run_rerun.py ✚ score_v2.py ✚ analyze_rerun.py
├── testbed/                  (src/, spike/, public/ …)
├── tests/                    (existing + conftest.py, test_item_paths.py, test_rerun_persistence.py)
├── docs/
│   ├── contracts.md  decisions.md  element_ids.md  oracle_fields.md  rubrics.md
│   ├── judge_decision_note.md  matrix-design.md  identifier_audit.md  table_reconciliation.md
│   ├── GATE3_FINDINGS.md  taxonomy_crosswalk.md  tier1_extraction_sheets.md
│   ├── REPO_CLEANUP_PLAN.md
│   ├── rubrics/  specs/  legal/
│   ├── audit/
│   │   ├── (01_STATUS_REPORT.md — ASK-1)  02_AUDIT_F6_F8.md  (03_SPRINT_REPORT.md — ASK-1)
│   │   ├── FOLLOWUP_REPORT.md  SPEC_DIVERGENCE.md  CORRECTED_TABLES.md   (04–06 per ASK-2)
│   │   ├── RERUN_STATUS.md ✚ FIXES.md ✚ PATH_CHECKS.md ✚ SCORING_V2.md ✚ RERUN_PREREG.md ✚ RERUN_RESULTS.md
│   │   └── evidence/analysis_output.txt
│   ├── paper/
│   │   ├── submission/        (hand-written acmart paper — you create)
│   │   ├── reference_generated_draft.tex  refs.bib  tables/T1…T7.tex
│   │   └── NUMBERS.md  DRAFT_STATUS.md  REVIEW_NOTES.md
│   └── archive/
│       ├── paper_ieee/armavour_paper.tex
│       ├── paper_notes/discussion-forced-action-interface-interference.md  results-deterministic.md
│       ├── phase0/context.md  ChhalBench_TestSpec.xlsx
│       ├── prompts/claude_code_prompt.md
│       ├── design/matrix-design-proposal.md
│       └── diagnostics_2026-08/e1b_analysis.md  ef_df_analysis.md
└── (ignored) .venv/ testbed/node_modules/ results/ logs/ .checkpoints/ .env .claude/
```
Removed: `all_context.txt`, `demo_run.log`, `analysis/`, `papers/`, `testbed-app/`, `docs/texput.log`, all LaTeX build artefacts, caches, and the two `*.llama-retired.log`.

---

## 9. Anonymity list (do not change; deal with these before sharing for review)

| file:line | what |
|---|---|
| `docs/paper/armavour_paper.tex:20–31` | author names and institution (IEEE author block) |
| `docs/paper/armavour_paper.tex:981` | GitHub repo URL (owner name) |
| `auditor/audit_runner.py:38` | GitHub repo URL in the auditor User-Agent |
| `docs/audit/02_AUDIT_F6_F8.md:9` | local Windows user path (user name) |
| `docs/audit/02_AUDIT_F6_F8.md:263,332,427` | developer first names |
| `docs/audit/CORRECTED_TABLES.md:36,46` | developer first names |
| `docs/audit/CORRECTED_TABLES.md:483–487` | local absolute paths `D:\BCA\MCA\…` |
| `docs/audit/FOLLOWUP_REPORT.md:255–261` | local absolute paths |
| `docs/audit/RERUN_STATUS.md:24–26,29,35` | local absolute paths |
| `docs/paper/DRAFT_STATUS.md:15–19` | local absolute paths |
| `docs/claude_code_prompt.md:4` | local absolute path (archived by A6) |
| `docs/e1b_analysis.md:16,243` | developer first name (archived by A8) |
| `docs/ef_df_analysis.md:4,8` | developer first names (archived by A9) |
| `docs/GATE3_FINDINGS.md:6` | "college report" (institution hint) |
| `docs/GATE3_FINDINGS.md:128,166,180,184` | developer first name |
| `docs/paper/armavour_facct.{log,fls,fdb_latexmk}`, `docs/paper/armavour_paper.log` | `C:/Users/<name>/…` paths (removed by D4/D5) |
| `demo_run.log` | local paths (removed by D2) |
| `.claude/settings.local.json` (ignored) | local user paths |
| **git metadata** | Commit authors (2 people, with personal emails) and `origin` → a GitHub URL with the owner's name. Never share `.git`. For review, share a fresh export: `git archive`, or anonymous.4open.science. |
| `README.md:7`, "Team & workflow" | no names, but describes a two-developer team |

`docs/paper/reference_generated_draft.tex` and `docs/paper/NUMBERS.md` had no hits.

## 10. Possible secrets (paths only, contents not reproduced)

| path | tracked? | type |
|---|---|---|
| `.env` | ignored, never committed | local secrets (not opened) |
| `.claude/settings.local.json` | ignored | DB connection string with embedded credential |
| `.checkpoints/provider_state.json` | ignored | provider key-pool state (only the top-level key was inspected) |
| `.env.example` | tracked | DB connection string with embedded credential |
| `docker-compose.yml` | tracked | Postgres password |
| `scripts/analyze_ablation.py:54` | tracked | DB URL with embedded credential (default) |
| `docs/audit/FOLLOWUP_REPORT.md` | tracked | DB connection string with embedded credential (2 lines) |

No API-key-shaped strings (`sk-`, `gsk_`, `AIza`, `sk-ant-`, `ghp_`, private keys) were found in any file outside `.env`, `.git`, `.venv` and `node_modules`. If any of the DB credentials above is more than a local dev default, rotate it before the repo is shared.

---

## Appendix A. Full inventory

### A. Tracked (195 paths)

| path | state | size | last modified | purpose |
|---|---|---|---|---|
| `.env.example` | tracked | 1.9 KB | 2026-08-22 20:06 | Template for local .env (DB URL, provider keys, judge model). |
| `.github/workflows/ci.yml` | tracked | 740 B | 2026-07-07 19:26 | CI: ruff, spike oracle check, pytest. |
| `.gitignore` | tracked | 147 B | 2026-08-22 20:09 | Root ignore rules. |
| `AUDIT_F6_F8.md` | tracked, deleted in worktree | - | - | F6/F8 data audit; DELETED in worktree, identical copy now at docs/audit/02_AUDIT_F6_F8.md. |
| `README.md` | tracked | 4.9 KB | 2026-07-04 11:19 | Project README (Phase-0 era, stale). |
| `alembic.ini` | tracked | 680 B | 2026-07-04 19:49 | Alembic config (script_location infra/migrations). |
| `all_context.txt` | tracked | 51.4 KB | 2026-08-08 17:54 | Aug-08 concatenated dump of run_matrix.py, key_pool.py, tests, .gitignore (LLM paste context; duplicate of code). |
| `analysis_output.txt` | tracked | 115.3 KB | 2026-08-22 20:06 | UTF-16 stdout of scripts/analysis.py on matrix-full-e1e2 (Aug 20); evidence cited by ARMAVOUR_STATUS_REPORT. |
| `auditor/__init__.py` | tracked | 115 B | 2026-08-16 11:19 | Armavour Auditor Package — inverted harness for detecting CCPA-13 dark patterns. |
| `auditor/audit_runner.py` | tracked | 23.3 KB | 2026-10-01 15:23 | Auditor: step-capturing audit runner with payment guard. |
| `auditor/detector.py` | tracked | 42.6 KB | 2026-10-01 15:23 | Auditor: CCPA-13 detectors (deterministic + judge paths). |
| `auditor/field.py` | tracked | 7.2 KB | 2026-08-16 11:19 | Auditor: field-audit safety wrapper, robots.txt check (has repo URL in User-Agent). |
| `auditor/storage.py` | tracked | 3.1 KB | 2026-08-16 11:19 | Auditor: evidence storage helpers. |
| `auditor/validate.py` | tracked | 13.1 KB | 2026-10-01 15:23 | Auditor: testbed validation, precision/recall/F1. |
| `data/.gitkeep` | tracked | 0 B | 2026-07-04 11:19 | Keeps data/ in git. |
| `data/judge_validation_samples.json` | tracked | 12.5 KB | 2026-08-07 20:26 | Judge regression dataset (12 cases); used by scripts/validate_judge.py. |
| `demo_run.log` | tracked | 6.3 KB | 2026-07-19 19:44 | UTF-16 log of a 5-episode gemini demo run (Jul 19) with LiteLLM errors. |
| `docker-compose.yml` | tracked | 831 B | 2026-07-04 19:49 | Local Postgres service. |
| `docs/ChhalBench_TestSpec.xlsx` | tracked | 18.5 KB | 2026-07-04 11:53 | Phase-0 CCPA-13 test spec (old project name ChhalBench). |
| `docs/GATE3_FINDINGS.md` | tracked | 8.2 KB | 2026-08-22 20:06 | Gate 3 Findings — Deterministic Pilot (150 episodes) |
| `docs/audit/CORRECTED_TABLES.md` | tracked | 31.6 KB | 2026-10-01 22:06 | Armavour — Corrected Results Tables |
| `docs/audit/FOLLOWUP_REPORT.md` | tracked | 20.5 KB | 2026-10-01 18:20 | Armavour — Follow-up Report |
| `docs/audit/SPEC_DIVERGENCE.md` | tracked | 29.9 KB | 2026-10-01 21:17 | Armavour — Spec vs Implementation Divergence Audit (12 patterns) |
| `docs/claude_code_prompt.md` | tracked | 11.0 KB | 2026-08-22 20:08 | Claude Code prompt — Armavour repo work |
| `docs/context.md` | tracked | 2.8 KB | 2026-07-04 11:29 | Armavour — Project Context (start here) |
| `docs/contracts.md` | tracked | 8.6 KB | 2026-10-01 15:26 | Armavour — Interface Contracts |
| `docs/decisions.md` | tracked | 8.6 KB | 2026-10-01 15:26 | Decision log (dated one-liners). |
| `docs/e1b_analysis.md` | tracked | 14.0 KB | 2026-08-22 20:06 | Investigation: two E1b (browseruse) anomalies |
| `docs/ef_df_analysis.md` | tracked | 10.5 KB | 2026-08-22 20:06 | Investigation: the `avoided` default on the no-oracle path |
| `docs/element_ids.md` | tracked | 3.3 KB | 2026-08-22 20:34 | Element IDs per Pattern (Contract 3) |
| `docs/identifier_audit.md` | tracked | 23.6 KB | 2026-08-22 20:35 | Identifier Leakage Audit — Task 1 |
| `docs/judge_decision_note.md` | tracked | 4.4 KB | 2026-08-07 20:19 | Methodology Decision Note: Evaluating Agent Susceptibility When Reasoning Acknowledges Dark Patterns |
| `docs/legal/2509.10723v1.pdf` | tracked | 10.6 MB | 2026-07-03 12:28 | Related-work paper (arXiv). |
| `docs/legal/2510.11035v2.pdf` | tracked | 11.4 MB | 2026-07-03 12:27 | Related-work paper (arXiv). |
| `docs/legal/2510.18113v1.pdf` | tracked | 1.0 MB | 2026-07-03 12:27 | Related-work paper (arXiv). |
| `docs/legal/Advisory-7.pdf` | tracked | 287.4 KB | 2026-07-03 12:18 | CCPA advisory (legal source). |
| `docs/legal/Physics_Wallah_Limited_Order_01June2026.pdf` | tracked | 11.3 MB | 2026-07-03 12:25 | CCPA enforcement order (legal source). |
| `docs/legal/Press Release Page _ Press Information Bureau_PW.pdf` | tracked | 220.4 KB | 2026-07-03 12:20 | PIB press release on PW order (legal source). |
| `docs/legal/The Guidelines for Prevention and Regulation of Dark Patterns, 2023_1732707717.pdf` | tracked | 1.4 MB | 2026-07-03 12:14 | CCPA Dark Pattern Guidelines 2023 (legal source). |
| `docs/matrix-design-proposal.md` | tracked | 7.7 KB | 2026-08-05 20:08 | Full Matrix Design Proposal — E1 + E2 |
| `docs/matrix-design.md` | tracked | 12.3 KB | 2026-08-08 17:50 | Full Matrix Design — E1 + E2 |
| `docs/oracle_fields.md` | tracked | 2.4 KB | 2026-07-06 12:38 | Oracle Fields per Pattern (Contract 2 companion) |
| `docs/paper/DRAFT_STATUS.md` | tracked | 2.3 KB | 2026-10-02 08:42 | FAccT draft — status |
| `docs/paper/NUMBERS.md` | tracked | 19.2 KB | 2026-10-02 08:40 | NUMBERS — ledger for `armavour_facct.tex` |
| `docs/paper/REVIEW_NOTES.md` | tracked | 9.4 KB | 2026-10-02 08:42 | REVIEW NOTES — `armavour_facct.tex` (draft of 2026-10-02) |
| `docs/paper/armavour_facct.aux` | tracked | 11.4 KB | 2026-10-02 09:05 | LaTeX build artefact of the old armavour_facct.tex (now reference_generated_draft.tex). |
| `docs/paper/armavour_facct.bbl` | tracked | 6.4 KB | 2026-10-02 09:05 | LaTeX build artefact (bibtex output). |
| `docs/paper/armavour_facct.blg` | tracked | 3.7 KB | 2026-10-02 09:05 | LaTeX build artefact (bibtex log). |
| `docs/paper/armavour_facct.fdb_latexmk` | tracked | 27.1 KB | 2026-10-02 09:05 | latexmk database (build artefact). |
| `docs/paper/armavour_facct.fls` | tracked | 40.0 KB | 2026-10-02 09:05 | LaTeX file list (build artefact). |
| `docs/paper/armavour_facct.log` | tracked | 52.0 KB | 2026-10-02 09:05 | LaTeX log (build artefact). |
| `docs/paper/armavour_facct.out` | tracked | 2.3 KB | 2026-10-02 09:05 | hyperref outline (build artefact). |
| `docs/paper/armavour_facct.pdf` | tracked | 512.7 KB | 2026-10-02 09:05 | PDF of the LLM-generated draft (stale; source renamed). |
| `docs/paper/armavour_paper.aux` | tracked | 6.1 KB | 2026-08-22 20:06 | LaTeX build artefact of the IEEE draft. |
| `docs/paper/armavour_paper.log` | tracked | 19.7 KB | 2026-08-22 20:06 | LaTeX log of the IEEE draft. |
| `docs/paper/armavour_paper.pdf` | tracked | 199.6 KB | 2026-08-22 20:06 | Aug-22 PDF of IEEE draft; older than the .tex (edited Oct 1), so stale. |
| `docs/paper/armavour_paper.tex` | tracked | 46.7 KB | 2026-10-01 16:27 | Superseded IEEE draft (original claims; author block, repo URL). |
| `docs/paper/discussion-forced-action-interface-interference.md` | tracked | 4.5 KB | 2026-08-04 19:36 | Discussion: forced_action and interface_interference |
| `docs/paper/reference_generated_draft.tex` | tracked, staged rename | 44.1 KB | 2026-10-02 08:41 | LLM-generated acmart draft, reference only (staged rename from armavour_facct.tex). |
| `docs/paper/refs.bib` | tracked | 3.4 KB | 2026-10-01 22:28 | Candidate bibliography (14 entries, all % VERIFY). |
| `docs/paper/results-deterministic.md` | tracked | 7.3 KB | 2026-08-04 19:31 | Results: Deterministic Pattern Pilot |
| `docs/paper/tables/T1_outcome.tex` | tracked | 1011 B | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/paper/tables/T2_control.tex` | tracked | 820 B | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/paper/tables/T3_intensity.tex` | tracked | 815 B | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/paper/tables/T4_patterns.tex` | tracked | 1.3 KB | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/paper/tables/T5_language.tex` | tracked | 780 B | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/paper/tables/T6_mcnemar.tex` | tracked | 683 B | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/paper/tables/T7_language_pattern.tex` | tracked | 1.3 KB | 2026-10-01 22:02 | Paper table generated by scripts/corrected_tables.py (pre-rerun numbers). |
| `docs/rubrics.md` | tracked | 943 B | 2026-07-05 09:32 | Judge Rubrics — Index |
| `docs/rubrics/confirm_shaming.md` | tracked | 2.8 KB | 2026-08-07 20:19 | Judge rubric (confirm_shaming, Contract 5). |
| `docs/rubrics/false_urgency.md` | tracked | 1.9 KB | 2026-08-07 20:19 | Judge rubric (false_urgency, Contract 5). |
| `docs/rubrics/interface_interference.md` | tracked | 3.3 KB | 2026-08-16 11:43 | Judge rubric (interface_interference, Contract 5). |
| `docs/rubrics/trick_question.md` | tracked | 3.5 KB | 2026-08-16 11:43 | Judge rubric (trick_question, Contract 5). |
| `docs/specs/bait_and_switch.md` | tracked | 2.9 KB | 2026-07-04 19:02 | Pattern/task spec (bait_and_switch). |
| `docs/specs/basket_sneaking.md` | tracked | 6.5 KB | 2026-07-04 18:50 | Pattern/task spec (basket_sneaking). |
| `docs/specs/confirm_shaming.md` | tracked | 3.6 KB | 2026-08-01 20:01 | Pattern/task spec (confirm_shaming). |
| `docs/specs/disguised_advertisement.md` | tracked | 6.1 KB | 2026-08-08 22:00 | Pattern/task spec (disguised_advertisement). |
| `docs/specs/drip_pricing.md` | tracked | 4.2 KB | 2026-07-04 19:02 | Pattern/task spec (drip_pricing). |
| `docs/specs/false_urgency.md` | tracked | 3.2 KB | 2026-08-01 20:02 | Pattern/task spec (false_urgency). |
| `docs/specs/forced_action.md` | tracked | 3.4 KB | 2026-07-04 19:02 | Pattern/task spec (forced_action). |
| `docs/specs/interface_interference.md` | tracked | 3.6 KB | 2026-07-04 19:02 | Pattern/task spec (interface_interference). |
| `docs/specs/nagging.md` | tracked | 3.3 KB | 2026-07-04 19:03 | Pattern/task spec (nagging). |
| `docs/specs/pattern.md` | tracked | 2.0 KB | 2026-07-05 19:38 | Pattern/task spec (pattern). |
| `docs/specs/saas_billing.md` | tracked | 3.3 KB | 2026-07-04 19:03 | Pattern/task spec (saas_billing). |
| `docs/specs/subscription_trap.md` | tracked | 3.0 KB | 2026-07-04 19:03 | Pattern/task spec (subscription_trap). |
| `docs/specs/tasks.md` | tracked | 1.9 KB | 2026-07-05 19:33 | Pattern/task spec (tasks). |
| `docs/specs/trick_question.md` | tracked | 3.3 KB | 2026-07-04 19:03 | Pattern/task spec (trick_question). |
| `docs/table_reconciliation.md` | tracked | 21.5 KB | 2026-08-22 20:06 | Table reconciliation — armavour_paper.tex vs. scripts/analysis.py |
| `docs/taxonomy_crosswalk.md` | tracked | 6.6 KB | 2026-07-03 12:42 | ChhalBench Taxonomy Crosswalk (Phase 0 / Step 3) |
| `docs/texput.log` | tracked | 723 B | 2026-08-22 20:06 | Failed empty pdflatex run (Emergency stop), no content. |
| `docs/tier1_extraction_sheets.md` | tracked | 12.1 KB | 2026-07-03 12:35 | Tier-1 Extraction Sheets + Taxonomy Crosswalk |
| `harness/adapters/__init__.py` | tracked | 51 B | 2026-07-04 19:49 | Agent adapter implementations for Armavour. |
| `harness/adapters/agente.py` | tracked | 1.0 KB | 2026-07-19 18:21 | Agent-E adapter (intentional stub). |
| `harness/adapters/browseruse.py` | tracked, modified | 12.1 KB | 2026-10-02 09:25 | Python module |
| `harness/adapters/common.py` | tracked | 118 B | 2026-07-19 18:21 | Shared adapter constants. |
| `harness/adapters/computeruse.py` | tracked, modified | 18.0 KB | 2026-10-02 09:24 | Python module |
| `harness/config.py` | tracked | 16.2 KB | 2026-08-16 11:19 | EpisodeConfig (Contract 1) and config hashing. |
| `harness/evaluator.py` | tracked | 6.0 KB | 2026-08-16 11:19 | Oracle-based outcome scoring (v1). |
| `harness/extract.py` | tracked | 5.8 KB | 2026-08-03 19:07 | Page element extraction for the agent prompt. |
| `harness/judge.py` | tracked | 19.1 KB | 2026-10-01 16:11 | LLM judge for soft patterns. |
| `harness/logger.py` | tracked | 2.2 KB | 2026-08-08 19:43 | Episode row logging to Postgres. |
| `harness/providers/__init__.py` | tracked | 409 B | 2026-08-22 20:06 | Provider package init. |
| `harness/providers/key_pool.py` | tracked | 13.7 KB | 2026-08-22 20:09 | Groq API key rotation pool. |
| `harness/requirements.txt` | tracked | 201 B | 2026-10-01 15:23 | Python dependencies. |
| `harness/runner.py` | tracked, modified | 20.5 KB | 2026-10-02 09:25 | Python module |
| `harness/verify_page.py` | tracked | 1.1 KB | 2026-07-28 12:10 | verify_page.py — Zero-API sanity check for the Armavour spike. |
| `infra/migrations/env.py` | tracked | 1.4 KB | 2026-07-04 19:49 | Alembic environment. |
| `infra/migrations/versions/0001_create_episodes.py` | tracked | 2.2 KB | 2026-07-28 12:10 | Alembic migration 0001_create_episodes. |
| `infra/migrations/versions/0002_episode_idempotency_and_crash_nullable.py` | tracked | 755 B | 2026-10-01 19:20 | Alembic migration 0002_episode_idempotency_and_crash_nullable. |
| `infra/migrations/versions/0003_add_duration_seconds.py` | tracked | 461 B | 2026-08-06 20:35 | Alembic migration 0003_add_duration_seconds. |
| `infra/migrations/versions/0004_add_provider_latency.py` | tracked | 479 B | 2026-08-06 20:35 | Alembic migration 0004_add_provider_latency. |
| `infra/migrations/versions/0005_add_instruction_language.py` | tracked | 842 B | 2026-08-16 11:19 | Alembic migration 0005_add_instruction_language. |
| `infra/migrations/versions/0006_add_judge_model_and_code_sha.py` | tracked | 869 B | 2026-10-01 18:31 | Alembic migration 0006_add_judge_model_and_code_sha. |
| `infra/smoke_test.py` | tracked | 1.6 KB | 2026-08-06 20:35 | DB/infra smoke test (inserts a spike row). |
| `pytest.ini` | tracked | 124 B | 2026-10-01 15:23 | Pytest config (testpaths=tests, pythonpath=.). |
| `scripts/analysis.py` | tracked | 38.4 KB | 2026-10-01 15:23 | scripts/analysis.py — Read-only Postgres analysis for the Armavour results tables. |
| `scripts/analyze_ablation.py` | tracked | 10.9 KB | 2026-10-01 19:11 | scripts/analyze_ablation.py — F6 config-leak ablation analysis. |
| `scripts/check_episode_data.py` | tracked | 695 B | 2026-08-05 20:51 | One-off DB check of episode rows (Aug 5). |
| `scripts/check_models.py` | tracked | 952 B | 2026-08-22 20:06 | One-off DB query: models used in matrix-full-e1e2. |
| `scripts/check_rerun_failure.py` | tracked | 813 B | 2026-08-05 20:51 | One-off DB check of a failed rerun (Aug 5). |
| `scripts/check_traces.py` | tracked | 475 B | 2026-08-05 20:51 | One-off trace inspection (Aug 5). |
| `scripts/corrected_tables.py` | tracked | 25.9 KB | 2026-10-01 22:02 | scripts/corrected_tables.py — paper tables recomputed after the spec-divergence |
| `scripts/debug_detector.py` | tracked | 1.6 KB | 2026-08-22 20:09 | One-off auditor detector debug helper. |
| `scripts/diagnose_context_text.py` | tracked | 1.8 KB | 2026-08-06 20:35 | One-off diagnostic of extracted context text. |
| `scripts/pilot_run.py` | tracked | 3.0 KB | 2026-07-28 19:55 | Gate-3 deterministic pilot runner. |
| `scripts/pull_qualitative_traces.py` | tracked | 1.5 KB | 2026-08-05 20:51 | Pulls traces for qualitative analysis. |
| `scripts/rejudge.py` | tracked | 16.0 KB | 2026-10-01 16:25 | scripts/rejudge.py — F7: re-judge every matrix-full-e1e2 row the judge originally |
| `scripts/rerun_disguised_ad.py` | tracked | 1.5 KB | 2026-08-22 20:36 | One-off rerun of disguised_ad cells. |
| `scripts/rerun_drip_aggressive.py` | tracked | 668 B | 2026-07-28 19:55 | One-off rerun of drip_pricing aggressive. |
| `scripts/rerun_post_id_fix.py` | tracked | 8.4 KB | 2026-10-01 15:23 | Re-run of interface_interference and confirm_shaming at aggressive intensity |
| `scripts/run_10_e1b.py` | tracked | 2.2 KB | 2026-08-16 11:19 | 10-episode E1b (browseruse) probe. |
| `scripts/run_leak_ablation.py` | tracked | 14.7 KB | 2026-10-01 19:11 | scripts/run_leak_ablation.py — F6 config-leak ablation, two arms x 200 episodes. |
| `scripts/run_matrix.py` | tracked | 45.1 KB | 2026-10-01 18:16 | scripts/run_matrix.py — Official Armavour Full Matrix Benchmark Runner (~1,560 episodes). |
| `scripts/run_spotcheck.py` | tracked | 12.8 KB | 2026-10-01 18:16 | scripts/run_spotcheck.py — Armavour Cross-Model Spot-Check Benchmark Runner (60 episodes). |
| `scripts/smoke_test.py` | tracked | 10.1 KB | 2026-08-07 20:19 | Harness smoke run (few configs). |
| `scripts/soft_pilot.py` | tracked | 2.5 KB | 2026-08-05 20:51 | Soft-pattern pilot runner. |
| `scripts/test_localization.py` | tracked | 2.5 KB | 2026-10-01 15:23 | Ad-hoc localization/config-hash check (lives in scripts/, not collected by pytest). |
| `scripts/trace.py` | tracked | 1.2 KB | 2026-08-22 20:09 | One-off debug script (header says debug_validate.py). |
| `scripts/validate_judge.py` | tracked | 6.5 KB | 2026-08-06 20:35 | Judge validation against data/judge_validation_samples.json. |
| `scripts/verify_judge_parse_error.py` | tracked | 4.2 KB | 2026-08-06 20:35 | One-off judge parse-error verification. |
| `testbed-app/.vite/deps/_metadata.json` | tracked | 146 B | 2026-07-04 19:14 | Stray Vite dep-cache from a scaffold in the wrong folder (Jul 4). |
| `testbed-app/.vite/deps/package.json` | tracked | 23 B | 2026-07-04 19:14 | Stray Vite dep-cache (junk). |
| `testbed/.gitignore` | tracked | 253 B | 2026-07-04 19:10 | Vite template ignore rules. |
| `testbed/README.md` | tracked | 2.4 KB | 2026-07-04 19:12 | Unmodified Vite template README. |
| `testbed/eslint.config.js` | tracked | 591 B | 2026-07-04 19:12 | ESLint config. |
| `testbed/index.html` | tracked | 363 B | 2026-07-04 19:12 | Vite entry HTML. |
| `testbed/package-lock.json` | tracked | 92.9 KB | 2026-10-01 18:35 | npm lockfile. |
| `testbed/package.json` | tracked | 712 B | 2026-07-04 19:12 | Testbed npm manifest. |
| `testbed/public/favicon.svg` | tracked | 9.3 KB | 2026-07-04 19:10 | Vite template asset. |
| `testbed/public/icons.svg` | tracked | 4.9 KB | 2026-07-04 19:10 | Vite template asset. |
| `testbed/spike/checkout.html` | tracked | 4.0 KB | 2026-07-04 11:23 | Phase-0 spike page; used by harness/verify_page.py, tests/test_evaluator.py, CI. |
| `testbed/src/App.css` | tracked, modified | 7.1 KB | 2026-10-02 09:32 | Testbed styles. |
| `testbed/src/App.tsx` | tracked | 938 B | 2026-07-06 12:23 | Testbed router (config -> pattern screen). |
| `testbed/src/BaitAndSwitch.tsx` | tracked | 2.4 KB | 2026-07-08 12:06 | Testbed screen/pattern component (BaitAndSwitch). |
| `testbed/src/BasketSneaking.tsx` | tracked | 1.6 KB | 2026-07-08 12:06 | Testbed screen/pattern component (BasketSneaking). |
| `testbed/src/CheckoutScreen.tsx` | tracked, modified | 7.7 KB | 2026-10-02 09:31 | Testbed screen/pattern component (CheckoutScreen). |
| `testbed/src/ConfirmShaming.tsx` | tracked | 2.3 KB | 2026-08-22 20:30 | Testbed screen/pattern component (ConfirmShaming). |
| `testbed/src/ContentScreen.tsx` | tracked, modified | 2.9 KB | 2026-10-02 09:32 | Testbed screen/pattern component (ContentScreen). |
| `testbed/src/CourseScreen.tsx` | tracked | 1.1 KB | 2026-07-08 12:06 | Testbed screen/pattern component (CourseScreen). |
| `testbed/src/DisguisedAd.tsx` | tracked | 2.3 KB | 2026-08-22 20:30 | Testbed screen/pattern component (DisguisedAd). |
| `testbed/src/DripPricing.tsx` | tracked, modified | 1.8 KB | 2026-10-02 09:31 | Testbed screen/pattern component (DripPricing). |
| `testbed/src/FalseUrgency.tsx` | tracked | 2.4 KB | 2026-08-22 20:30 | Testbed screen/pattern component (FalseUrgency). |
| `testbed/src/ForcedAction.tsx` | tracked | 3.1 KB | 2026-07-08 12:06 | Testbed screen/pattern component (ForcedAction). |
| `testbed/src/InterfaceInterference.tsx` | tracked | 2.9 KB | 2026-08-22 20:30 | Testbed screen/pattern component (InterfaceInterference). |
| `testbed/src/Nagging.tsx` | tracked, modified | 2.4 KB | 2026-10-02 09:32 | Testbed screen/pattern component (Nagging). |
| `testbed/src/SaasBilling.tsx` | tracked, modified | 3.6 KB | 2026-10-02 09:31 | Testbed screen/pattern component (SaasBilling). |
| `testbed/src/SubscriptionScreen.tsx` | tracked, modified | 2.5 KB | 2026-10-02 09:31 | Testbed screen/pattern component (SubscriptionScreen). |
| `testbed/src/SubscriptionTrap.tsx` | tracked | 1.9 KB | 2026-07-08 12:06 | Testbed screen/pattern component (SubscriptionTrap). |
| `testbed/src/TrickQuestion.tsx` | tracked, modified | 2.2 KB | 2026-10-02 09:31 | Testbed screen/pattern component (TrickQuestion). |
| `testbed/src/assets/hero.png` | tracked | 12.8 KB | 2026-07-04 19:10 | Vite template asset. |
| `testbed/src/assets/react.svg` | tracked | 4.0 KB | 2026-07-04 19:10 | Vite template asset. |
| `testbed/src/assets/vite.svg` | tracked | 8.5 KB | 2026-07-04 19:10 | Vite template asset. |
| `testbed/src/config.ts` | tracked | 873 B | 2026-07-04 19:21 | Episode config parsing (Contract 1). |
| `testbed/src/i18n.ts` | tracked, modified | 20.7 KB | 2026-10-02 09:32 | Trilingual strings (en/hi/hinglish). |
| `testbed/src/index.css` | tracked | 2.1 KB | 2026-07-04 19:10 | Global CSS. |
| `testbed/src/lib/ids.ts` | tracked | 3.1 KB | 2026-08-22 20:29 | Seed-derived opaque element ids. |
| `testbed/src/main.tsx` | tracked | 230 B | 2026-07-04 19:10 | React entry. |
| `testbed/src/oracle.ts` | tracked | 1.0 KB | 2026-07-05 09:55 | Oracle emitter (window.__ARMAVOUR_RESULT__). |
| `testbed/tsconfig.app.json` | tracked | 655 B | 2026-07-04 19:10 | TS config. |
| `testbed/tsconfig.json` | tracked | 119 B | 2026-07-04 19:10 | TS config. |
| `testbed/tsconfig.node.json` | tracked | 558 B | 2026-07-04 19:10 | TS config. |
| `testbed/vite.config.ts` | tracked | 161 B | 2026-07-04 19:10 | Vite config. |
| `tests/test_adapters.py` | tracked | 27.5 KB | 2026-10-01 19:12 | Tests (test_adapters). |
| `tests/test_analysis.py` | tracked | 31.1 KB | 2026-08-22 20:06 | Tests (test_analysis). |
| `tests/test_auditor.py` | tracked | 13.2 KB | 2026-10-01 15:23 | Tests (test_auditor). |
| `tests/test_corrected_tables.py` | tracked | 4.2 KB | 2026-10-01 22:03 | Tests (test_corrected_tables). |
| `tests/test_evaluator.py` | tracked | 5.1 KB | 2026-08-16 11:19 | Tests (test_evaluator). |
| `tests/test_extract.py` | tracked | 1.8 KB | 2026-08-03 19:07 | Tests (test_extract). |
| `tests/test_identifier_audit.py` | tracked | 5.4 KB | 2026-08-22 20:38 | Tests (test_identifier_audit). |
| `tests/test_judge.py` | tracked | 7.9 KB | 2026-08-22 20:06 | Tests (test_judge). |
| `tests/test_key_pool.py` | tracked | 11.1 KB | 2026-08-22 20:06 | Tests (test_key_pool). |
| `tests/test_localization.py` | tracked | 4.3 KB | 2026-10-01 15:23 | Tests (test_localization). |
| `tests/test_logger.py` | tracked | 2.8 KB | 2026-07-28 12:10 | Tests (test_logger). |
| `tests/test_run_matrix.py` | tracked | 4.7 KB | 2026-08-16 11:19 | Tests (test_run_matrix). |
| `tests/test_runner.py` | tracked | 9.5 KB | 2026-10-01 15:23 | Tests (test_runner). |

### B. Untracked (7 files) + empty untracked dirs

| path | state | size | last modified | purpose |
|---|---|---|---|---|
| `cleanup_repo.ps1` | untracked | 11.1 KB | 2026-10-02 09:50 |  |
| `docs/audit/02_AUDIT_F6_F8.md` | untracked | 46.4 KB | 2026-10-01 22:20 | F6/F7/F8 data audit (moved by hand from root; byte-identical to HEAD:AUDIT_F6_F8.md). |
| `docs/audit/RERUN_STATUS.md` | untracked | 8.7 KB | 2026-10-02 09:28 | Corrected-rerun status (active, owned by the rerun). |
| `infra/migrations/versions/0007_oracle_result_variant.py` | untracked | 1.4 KB | 2026-10-02 09:25 | Rerun migration 0007 (active, owned by the rerun). |
| `tests/conftest.py` | untracked | 785 B | 2026-10-02 09:42 | Pytest fixtures (active, appeared during this analysis). |
| `tests/test_item_paths.py` | untracked | 25.2 KB | 2026-10-02 09:42 | Rerun path-check tests (active, appeared during this analysis). |
| `tests/test_rerun_persistence.py` | untracked | 10.8 KB | 2026-10-02 09:26 | Rerun persistence tests (active, owned by the rerun). |
| `analysis/` | untracked, empty dir | 0 B | 2026-07-04 11:19 | Empty placeholder (named in README layout). |
| `papers/` | untracked, empty dir | 0 B | 2026-07-04 11:19 | Empty placeholder (named in README layout). |

### C. Gitignored

| path | state | size | last modified | purpose |
|---|---|---|---|---|
| `.env` | ignored | 2.1 KB | 2026-10-01 18:38 | Local secrets/config (gitignored; contents not read). |
| `.claude/settings.local.json` | ignored | 1.3 KB | 2026-08-19 22:22 | Claude Code local permissions (gitignored). |
| `.checkpoints/provider_state.json` | ignored | 58 B | 2026-10-01 21:03 | Runtime provider/key-rotation state (groq). |
| `.pytest_cache/` | ignored | 9.5 KB | 2026-08-22 20:44 | Pytest cache. |
| `.ruff_cache/` | ignored | 5.1 KB | 2026-08-22 20:36 | Ruff cache. |
| `.venv/` | ignored | 545.0 MB | 2026-08-19 21:37 | Python virtualenv (contents skipped). |
| `testbed/node_modules/` | ignored | 103.4 MB | 2026-10-02 09:32 | npm deps (contents skipped). |
| `auditor/__pycache__/` | ignored | 100.1 KB | 2026-10-01 15:29 | Bytecode cache. |
| `harness/__pycache__/` | ignored | 80.6 KB | 2026-10-02 09:27 | Bytecode cache. |
| `harness/adapters/__pycache__/` | ignored | 37.1 KB | 2026-10-02 09:27 | Bytecode cache. |
| `harness/providers/__pycache__/` | ignored | 19.6 KB | 2026-08-22 20:36 | Bytecode cache. |
| `infra/migrations/__pycache__/` | ignored | 2.3 KB | 2026-07-09 10:23 | Bytecode cache. |
| `infra/migrations/versions/__pycache__/` | ignored | 11.8 KB | 2026-10-02 09:28 | Bytecode cache. |
| `scripts/__pycache__/` | ignored | 187.8 KB | 2026-10-02 09:27 | Bytecode cache. |
| `tests/__pycache__/` | ignored | 694.9 KB | 2026-10-02 09:42 | Bytecode cache. |
| `logs/matrix_ablation-config-01.llama-retired.log` | ignored | 9.4 KB | 2026-10-01 18:54 | Run log (run_matrix.py) - Llama-3.3-70b attempt, model retired |
| `logs/matrix_ablation-config-01.log` | ignored | 30.8 KB | 2026-10-01 21:03 | Run log (run_matrix.py) |
| `logs/matrix_ablation-noconfig-01.llama-retired.log` | ignored | 1.7 KB | 2026-10-01 18:41 | Run log (run_matrix.py) - Llama-3.3-70b attempt, model retired |
| `logs/matrix_ablation-noconfig-01.log` | ignored | 30.8 KB | 2026-10-01 20:11 | Run log (run_matrix.py) |
| `logs/matrix_matrix-full-e1e2.log` | ignored | 4.1 KB | 2026-08-08 19:28 | Run log (run_matrix.py) |
| `results/ablation/cs_ii_noconfig.csv` | ignored | 246 B | 2026-10-01 21:05 | scripts/analyze_ablation.py export. |
| `results/ablation/mcnemar_primary_config_vs_noconfig.csv` | ignored | 543 B | 2026-10-01 21:05 | scripts/analyze_ablation.py export. |
| `results/ablation/pairs_primary_config_vs_noconfig.csv` | ignored | 34.5 KB | 2026-10-01 21:05 | scripts/analyze_ablation.py export. |
| `results/analysis/table_10a___pattern_table__e1b_only.csv` | ignored | 575 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_10b___pattern_table__e1a_vs_e1b__n_40_cell.csv` | ignored | 364 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_11___language_effect_by_pattern__english_instruction__n_30_cell.csv` | ignored | 949 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_1___intensity_gradient__e1a_only.csv` | ignored | 341 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_2___pattern_table__e1a_only.csv` | ignored | 584 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_3___language_table__five_conditions.csv` | ignored | 511 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_4___paired_language_comparison__mcnemar_s_exact_test.csv` | ignored | 253 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_4b___unmatched__pattern__intensity__seed__keys.csv` | ignored | 48 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_5___control_condition_deceptions__comprehension_execution_failures.csv` | ignored | 6.0 KB | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_6___ef_breakdown_by_arm_agent_pattern_steps_terminal_reason.csv` | ignored | 1.3 KB | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_7___excluded_patterns__disguised_advertisement__false_urgency.csv` | ignored | 1.6 KB | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_8___outcome_distribution_by_arm__all_six_arms.csv` | ignored | 475 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_9a___intensity_gradient__e1b_only.csv` | ignored | 321 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis/table_9b___intensity_gradient__e1a_vs_e1b__scored__n_100_cell.csv` | ignored | 171 B | 2026-08-20 19:54 | scripts/analysis.py export (matrix-full-e1e2, Aug 20). |
| `results/analysis_corrected/C2_counts.csv` | ignored | 776 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/S1_outcome_sensitivity.csv` | ignored | 2.7 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/S3_intensity_sensitivity.csv` | ignored | 3.7 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/S4_pattern_sensitivity.csv` | ignored | 2.9 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T1_corrected.csv` | ignored | 490 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T1_raw.csv` | ignored | 475 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T2_corrected.csv` | ignored | 220 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T2_raw.csv` | ignored | 220 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T3_corrected.csv` | ignored | 666 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T3_raw.csv` | ignored | 574 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T4_corrected.csv` | ignored | 417 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T4_raw.csv` | ignored | 423 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T4b_corrected.csv` | ignored | 2.7 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T4b_raw.csv` | ignored | 2.7 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T5_corrected.csv` | ignored | 635 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T5_raw.csv` | ignored | 511 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T6_cells_corrected.csv` | ignored | 1.2 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T6_cells_raw.csv` | ignored | 1.5 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T6_sign_corrected.csv` | ignored | 133 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T6_sign_raw.csv` | ignored | 136 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T6_summary_corrected.csv` | ignored | 252 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T6_summary_raw.csv` | ignored | 253 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T7_corrected.csv` | ignored | 1.0 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T7_raw.csv` | ignored | 949 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/T8_attribution_raw.csv` | ignored | 342 B | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/analysis_corrected/tables.md` | ignored | 18.1 KB | 2026-10-01 22:02 | scripts/corrected_tables.py export. |
| `results/configs_ablation-config-01.json` | ignored | 52.7 KB | 2026-10-01 20:12 | Run-time config enumeration (run_matrix.py). |
| `results/configs_ablation-noconfig-01.json` | ignored | 52.7 KB | 2026-10-01 19:22 | Run-time config enumeration (run_matrix.py). |
| `results/configs_matrix-full-e1e2.json` | ignored | 422.7 KB | 2026-08-08 19:28 | Run-time config enumeration (run_matrix.py). |
| `results/crashes_ablation-config-01.llama-retired.csv` | ignored | 18.8 KB | 2026-10-01 18:54 | Crash rows of the retired-Llama ablation attempt (52 rows); cited by NUMBERS.md:254. |
| `results/environment_ablation-config-01.json` | ignored | 333 B | 2026-10-01 20:12 | Run environment snapshot (run_matrix.py). |
| `results/environment_ablation-noconfig-01.json` | ignored | 333 B | 2026-10-01 19:22 | Run environment snapshot (run_matrix.py). |
| `results/environment_matrix-full-e1e2.json` | ignored | 341 B | 2026-08-08 19:28 | Run environment snapshot (run_matrix.py). |
| `results/manifest_ablation-config-01.json` | ignored | 920 B | 2026-10-01 20:12 | Run manifest (run_matrix.py). |
| `results/manifest_ablation-noconfig-01.json` | ignored | 922 B | 2026-10-01 19:22 | Run manifest (run_matrix.py). |
| `results/manifest_final_ablation-config-01.json` | ignored | 705 B | 2026-10-01 21:03 | Run manifest (run_matrix.py). |
| `results/manifest_final_ablation-noconfig-01.json` | ignored | 704 B | 2026-10-01 20:11 | Run manifest (run_matrix.py). |
| `results/manifest_matrix-full-e1e2.json` | ignored | 935 B | 2026-08-08 19:28 | Run manifest (run_matrix.py). |
| `results/matrix_summary_ablation-config-01.csv` | ignored | 50.1 KB | 2026-10-01 21:03 | Run summary export (run_matrix.py). |
| `results/matrix_summary_ablation-config-01.json` | ignored | 860 B | 2026-10-01 21:03 | Run summary export (run_matrix.py). |
| `results/matrix_summary_ablation-noconfig-01.csv` | ignored | 50.3 KB | 2026-10-01 20:11 | Run summary export (run_matrix.py). |
| `results/matrix_summary_ablation-noconfig-01.json` | ignored | 861 B | 2026-10-01 20:11 | Run summary export (run_matrix.py). |
