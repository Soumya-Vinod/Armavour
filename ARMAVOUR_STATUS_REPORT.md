# Armavour — Status Report (audit as of 2026-10-01)

Scope: read-only audit of the repo at `D:\BCA\MCA\RESEARCH\armavour`, HEAD `c33293a` (2026-08-22 20:09 IST) plus uncommitted working tree. No git writes, no file modifications except this file, no episodes run, no LLM calls (no API keys present in env or `.env`; verified by `grep -c` = 0), no migrations.

**Data access:** the project Postgres was **not reachable**. Port 5432 answers but rejects `armavour:armavour` (`FATAL: password authentication failed`); it is a native PostgreSQL install (`/c/Program Files/PostgreSQL/17|18` on PATH), not the compose container. Docker daemon is not running. Port 5433 is closed. `.env` has no `DATABASE_URL`. No `pgdump_*.sql` exists in the repo. All numeric verification below therefore uses the exported CSVs in `results/analysis/*.csv` (written 2026-08-20 19:54) and `analysis_output.txt` (UTF-16, the stdout of the same run, committed in `de1e3e1`). Anything that needs traces or `created_at` is marked UNVERIFIED.

Naming: git authors are `SOUMYA VINOD` (Dev 1 per `docs/context.md`: testbed, spec, analysis, paper; presumed "Sam") and `chinmay` (Dev 2: harness, judge, evaluator, Postgres, auditor).

---

## 1. Executive summary

The benchmark ran once at scale: run_id `matrix-full-e1e2`, 1,928 rows, 1,600 scored. The paper is **Draft 3**, not Draft 2 (`a4de20d`, "draft 3 — add identifier leakage as fifth validity failure"). It is titled around **Five** failures (`armavour_paper.tex:18-19`), in IEEEtran format. It is not acmart, which FAccT requires. Every results-table number in the paper matches the exported CSVs exactly. Three prose numbers do not match: the pooled control-failure count (34/300), the judge accuracy (72.7% on "twelve" cases), and the "four of the language-arm patterns" wording.

The validity story is incomplete and the paper is stale against the repo in five ways:

1. **Config leakage, not mentioned anywhere in repo docs or the paper.** The ComputerUse agent prompt has contained the full episode config since the harness skeleton (`computeruse.py:131`, `"config": _jsonable(config)`). That config includes `pattern` and `intensity`. The BrowserUse task text has included the episode URL (`?pattern=…&intensity=…`) since 2026-08-09. This affects every pattern in every arm.
2. **Judge-model provenance contradiction.** The matrix manifest records the judge as `groq/llama-3.1-8b-instant`, the judge the paper says was rejected. The code default changed to `gpt-oss-120b` only on 2026-08-16, after the matrix ran. The judge model is not stored per row.
3. **Code drift during the run.** The manifest pins commit `a2f4ef7`. The evaluator, the ComputerUse adapter, the BrowserUse adapter (7 commits), and the disguised-ad price all changed while the matrix was running. Commit `5c31414` also says it purged E1b EF rows.
4. **Identifier audit is stale in the paper.** `docs/identifier_audit.md` now covers all 12 patterns and finds `confirm_shaming` and `interface_interference` also leaking at aggressive intensity. The paper still says "we have not audited the remaining ten" and reports both as clean nulls in its pattern-class result. BrowserUse also exposes DOM `id`s to the model (`browser_use/dom/views.py:23`).
5. **The fix is uncommitted.** All ID-fix work (testbed `lib/ids.ts`, 4 components, the `judge.py` prefix match, docs, the new test) is uncommitted.

There is no evidence in the repo of a run named `rerun-post-id-fix-01` or of a sixth denominator-drift instance. Those can only be checked against the DB.

---

## 2. Component status

| Component | Status | Evidence |
|---|---|---|
| Testbed (React/TS/Vite) | 12 patterns implemented; opaque seed-derived IDs for 4 patterns **in working tree only (uncommitted)** | `testbed/src/lib/ids.ts` (untracked); diffs to `DisguisedAd.tsx`, `FalseUrgency.tsx`, `ConfirmShaming.tsx`, `InterfaceInterference.tsx`, `CheckoutScreen.tsx`, `ContentScreen.tsx`, `SubscriptionScreen.tsx`. Served by Vite dev server (`BASE_URL=http://localhost:5173`, `.env.example`), so source edits hot-apply to in-flight runs. I did not run a TS type-check. |
| Oracle | Working; fires on terminal action per pattern | `testbed/src/oracle.ts:20-31` |
| `computeruse` adapter | Working. Element-N relabel in prompt (`19bdebe`). **Leaks config (pattern/intensity) in prompt** | `harness/adapters/computeruse.py:129-139`, `:253-262` |
| `browseruse` adapter | Working (browser-use 0.13.4). Rewritten 2026-08-09 mid-matrix. **Exposes `id` attrs and the episode URL to the model.** Trace is action strings only, with no reasoning. No `last_elements`. | `browseruse.py:52-53,209-223`; `requirements.txt:4`; `browser_use/dom/views.py:18-24` (installed copy) |
| `agente` adapter | Stub (intentional) | `decisions.md` 2026-07-16; `harness/adapters/agente.py` (35 lines) |
| Extractor | Working; passes raw `id` into `ElementInfo` | `harness/extract.py:59-76` |
| Evaluator | Working; **no-oracle path still `avoided=True` unconditionally** | `harness/evaluator.py:98-108` (and the soft path at `:69`) |
| Judge | Default `groq/openai/gpt-oss-120b` since `37f78ac` (2026-08-16). Prefix-match fix uncommitted. Trace-only (no vision). | `harness/judge.py:20,69-71,235-273,325-348` |
| Analysis | Produces Tables 1–11. The **McNemar table crashes under the installed pandas 3.0.5** (unit test fails). | `scripts/analysis.py`; `tests/test_analysis.py::test_paired_language_mcnemar_matches_on_key_and_computes_discordant_counts` → `TypeError: unsupported operand type(s) for &: 'StringArray'`; `requirements.txt` has `pandas>=2.0` unpinned |
| DB / migrations | 0001–0005; 0005 adds `instruction_language`/`ui_language`/`instruction_prompt` with `server_default="en"` and **no backfill from `language`** | `infra/migrations/versions/0005_add_instruction_language.py:13-24` |
| Auditor (`auditor/`) | Built Aug 15–21 by chinmay; 37 offline tests pass (with the other suites run); not mentioned in the paper | `git log` Aug 15–21; `tests/test_auditor.py` |
| Infra / Docker | Compose provides only Postgres 16 + Adminer; no harness container. CI workflow exists. Docker not running on this machine. | `docker-compose.yml`; `.github/workflows/ci.yml` |
| Tests (offline run by me) | 104 passed, 2 failed: the pandas McNemar failure above, and `test_browseruse_adapter_groq_llm_configuration` (browser_use is not in `.venv`; it is installed in user site-packages) | `pytest -p no:cacheprovider` over all `tests/` files |

---

## 3. Experiments

| Arm | run_id | Agent / model | Design | Episodes (raw / scored) | Comparability notes |
|---|---|---|---|---|---|
| pilot-01 | `pilot-01` | computeruse / llama-3.3-70b | 10 deterministic patterns × 3 int × 5 seeds | 150 (per GATE3) | Pre-matrix. Data was on chinmay's local Postgres (`docs/GATE3_FINDINGS.md`). DA 60% here is the "perception gap" result in the paper's §V-A. |
| pilot-soft-01 | `pilot-soft-01` | computeruse | soft patterns | UNVERIFIED | `scripts/soft_pilot.py:11`; cited in `decisions.md` 2026-08-05 |
| E1a | `matrix-full-e1e2` | computeruse / llama-3.3-70b-versatile | 12 pat × 4 int × seeds 0–9, EN | 488 / 400 | 8 surplus rows are all `false_urgency` control (E1a FU n=48, table 7; control n_raw=128, table 1) |
| Spot-check (8B) | `matrix-full-e1e2` | computeruse / llama-3.1-8b-instant | 12 pat × aggressive × seeds 0–4 | 60 / 50 | `run_matrix.py:159-174`. Same model string as the manifest judge, so judge==agent is possible; see §5 F7. |
| E1b | `matrix-full-e1e2` | browseruse / llama-3.3-70b | E1a matrix | 480 / 400 | Ran on the 08-09 adapter rewrite, not the manifest commit. Some EF rows purged and presumably rerun (`5c31414`); extent UNVERIFIED. |
| E2 | `matrix-full-e1e2` | computeruse / 70b | **6** patterns (incl. FU) × {control, moderate, aggressive} × {en, hi, hinglish} UI × seeds 10–19, EN instruction | 540 / 450 | `run_matrix.py:193-216`. The paper says "five patterns". |
| E2a | `matrix-full-e1e2` | computeruse / 70b | 6 pat × 3 int × hi UI + hi instruction × seeds 20–29 | 180 / 150 | Run 2026-08-12 per `analysis.py:118-123`. `instruction_language` not persisted; reconstructed from seed block. |
| E2b | `matrix-full-e1e2` | computeruse / 70b | same, hinglish/hinglish, seeds 30–39 | 180 / 150 | Same as E2a |
| Spot-check (gpt-oss-20b) | presumably `spotcheck-groq-openai-gpt-oss-20b` (default from `run_spotcheck.py:91`); UNVERIFIED | computeruse / gpt-oss-20b | 12 pat × aggressive × seeds 0–4 | 60 (paper: "16 of 60") | **Default `--max-steps 5`** (`run_spotcheck.py:110-114`) vs matrix 20 (`adapters/common.py:3`). Not in the exported CSVs. Ran before the element-N fix. `get_batch_name_for_config` would classify these rows as **E1a** if pooled (`run_matrix.py:115`). |
| DA v2 rerun | `rerun-disguised-ad-v2` | — | DA with ad cheapest | **0 rows** as of 2026-08-20 | `table_7…csv` last row: "NO ROWS FOUND". The script at HEAD has unresolved merge-conflict markers (lines 2–5); fixed only in the working tree. |
| Post-ID-fix rerun | `rerun-post-id-fix-01` | gpt-oss-20b (per your brief) | — | UNVERIFIED | The string does not appear anywhere in the repo (`grep -rn post-id-fix` returns nothing). |

Totals check: 488+60+480+540+180+180 = 1,928; scored 400+50+400+450+150+150 = 1,600 (`table_8…csv`). Manifest `total_enumerated_configs: 1560` is E1a+spot+E1b+E2 only, because E2a/E2b were added later in `d46adfb` (2026-08-12 23:34).

---

## 4. Headline results as they stand in the exported data

Source: `results/analysis/*.csv` (generated from DB `matrix-full-e1e2`, 2026-08-20). Excluded patterns (DA, FU) are dropped from every scored column.

- **Outcome by arm** (`table_8`), as DC raw / DC judge: E1a 17.5/17.25; Spot 42.0/38.0; E1b 13.5/13.5; E2 27.78/27.78; E2a 73.33/54.0; E2b 30.0/30.0. EF: E1a 0.75%, Spot 10%, E1b 11.75%, E2 2.44%. DF = 0 everywhere.
- **Intensity, DC raw** (`table_9b`), E1a / E1b: control 0/5, subtle 9/8, moderate 23/15, aggressive 38/26. E1a moderate judge-adjusted is 22% (`table_1`).
- **Pattern, n=40** (`table_10b`), E1a / E1b: SaaS 55/30, TQ 42.5/65, Drip 25/22.5, B&S 22.5/5, FA 15/12.5, BS 12.5/0, CS 2.5 raw (0 judge)/0, ST 0/0, II 0/0, Nag 0/0.
- **Language** (`table_3`): en/en 20.67, en/hinglish 26.67, en/hi 36.0, hinglish/hinglish 30.0, hi/hi 73.33 (judge 54.0).
- **McNemar** (`table_4`), exact binomial on discordant pairs: en vs hi b=3, c=26, p=1.52e-5 (I recomputed `binomtest(3,29)`=1.5236e-5). en vs hinglish 7 vs 16, p=0.0931. 150/150 pairs matched; `table_4b` is empty.
- **Control deceptions** (`table_5`, 39 rows): E1b 5 (SaaS 2, TQ 3); E2 en/hi 6 (TQ); E2a 21 (CS 10, II 10, TQ 1); E2b 7 (TQ).

**Caveat on all of the above:** F6–F8 below are not yet accounted for.

---

## 5. Measurement-validity failures

| # | Failure | Detection signature | Evidence | In paper? |
|---|---|---|---|---|
| F1 | Criterion-bypassable item (DA v1, FU) | Zero intensity slope; disagreement with pilot | Spec v2 note `docs/specs/disguised_advertisement.md:67-71`; `table_7` all 0% | Yes, §V-A. **Caveat:** the DA price flip (`80b0dc6`, 2026-08-08 22:07 IST) landed ~2.5 h after the matrix started (19:28 IST). The Vite dev server hot-reloads, so DA rows run after 22:07 likely saw ad=Rs 149 (cheapest). E1b ran after the 08-09 adapter rewrite, so **E1b DA was probably v2-priced and still scored 0%**. That contradicts the paper's "price explains 0% under both architectures". UNVERIFIED: check `created_at` of DA rows per arm. |
| F2 | Identifier leakage | Trace vocabulary absent from the rendered page | `identifier_audit.md` §2–3: DA, FU, **CS (`cs-remove2`), II (`decline-btn`)** leaking. browser-use includes `id` in `DEFAULT_INCLUDE_ATTRIBUTES` (`browser_use/dom/views.py:23`), so E1b is affected too. | Partly, §V-B. It names only DA/FU and says the remaining ten are unaudited (`tex:442-443, 861-866`). It does not say CS/II leak, yet §VII-C builds the "four nulls" claim on CS and II. Does not say BrowserUse leaks ids. |
| F3 | Completion-signal contamination | Order-of-magnitude EF difference across arms; EF present at control | `evaluator.py:98-108` (deterministic) and `:69` (soft: `oracle_avoided=True` if no oracle). Unchanged since `5c31414` (2026-08-09). | Yes, §V-C. The supporting stats (45/48 done, 6,870 vs 7,163 tokens, 45.2 s vs 37.9 s) are UNVERIFIABLE from the repo; `docs/e1b_analysis.md:8` says traces were not pulled. |
| F4 | Denominator drift (pooled pattern column, n=135/45) | Partial reproduction | `table_reconciliation.md` §2.1 | Yes, §V-D |
| F5 | Baseline contamination (non-EN control failures) | Non-zero null-condition rate split by the manipulated axis | `table_5` | Yes, §V-E (one pooled figure is wrong; see §6) |
| **F6** | **Task-config leakage into the agent prompt** | Agent traces containing `pattern`/`intensity` names or "dark pattern" vocabulary | ComputerUse: the prompt dict includes `"config": _jsonable(config)` (`computeruse.py:131`), and `EpisodeConfig.to_dict()` returns `pattern`, `intensity`, `task_id`, `site`, `seed`, `config_hash`, `llm`, `agent` (`config.py:94-98`). Present at the matrix commit (`git show a2f4ef7:harness/adapters/computeruse.py` line 108) and since `25c408d` (2026-07-04). BrowserUse: `full_task = f"{task}\n\nStart Page URL: {target_url}"` (`browseruse.py:52`), where the URL carries `pattern=` and `intensity=` (`runner.py:51-61`); added `225589c` 2026-08-09, before E1b. | **No.** Not in any doc, decision, or the identifier audit. Affects all 12 patterns and all arms. Behavioural impact UNVERIFIED; it needs a trace grep in the DB. |
| **F7** | **Judge-model provenance** | Manifest vs paper disagreement | `results/manifest_matrix-full-e1e2.json`: `"judge_model": "groq/llama-3.1-8b-instant"`, `CHHAL_JUDGE_MODEL=…8b-instant`. `judge.py` default at `a2f4ef7` was 8b (line 18); changed to gpt-oss-120b in `37f78ac` (2026-08-16). No judge-model column (`0001_create_episodes.py:19-39`). `validate_judge_model` compares against env `CHHAL_MODEL`, not `config.llm` (`judge.py:69-71`), so for the 8B spot-check an 8B judge would pass the check: **judge == agent possible**. | **No.** The paper states judge = gpt-oss-120b (`tex:310`) and that 8b over-flags (`tex:296-304`). This affects every DC_judge number (CS: E1a 1→0, Spot 21→19, E2a 110→81). |
| **F8** | **Code-version drift within one run_id** | Manifest commit ≠ code that produced rows | After the manifest commit `a2f4ef7` (08-08 18:23): `6503198` computeruse click-fallback (19:40), `b78f401` evaluator unplaced→EF (19:44), `80b0dc6` DA price (22:07), 7 browseruse commits (08-09), `5c31414` evaluator + "purge invalid E1b EF rows" (08-09 20:12), `d46adfb`/`eb696f9` config/runner (08-12). No per-row code version. | **No.** The paper calls 1,928 episodes one matrix. |
| F9 (latent) | Migration-0005 relabelling hazard | n_flag in Table 3 would fire; Table 8 has no n_flag | 0005 backfills `instruction_language='en'` and `ui_language='en'` on all existing rows. `analysis.py:206-211` derives only if the column is *absent*. Applying 0005 to the restored dump would silently relabel hi/hinglish rows as en/en. | No (not yet triggered as far as the repo shows) |
| F10 | "6th denominator drift: id-block pooling in the rerun" | — | No artifacts in the repo | UNVERIFIED. Related latent risk: the arm classifier maps any non-8B ComputerUse EN row with seed<10 to E1a (`run_matrix.py:113-125`). |
| — | Mixed metric across tables | — | The intensity table uses raw DC (E1a moderate 23%); the pattern table uses judge-adjusted for CS (0.0%) | Minor; the paper footnotes only the pattern table |

---

## 6. Paper status

**File:** `docs/paper/armavour_paper.tex` (974 lines, `\documentclass[conference]{IEEEtran}`, line 1). Last committed `5e47046` 2026-08-22 20:09. The PDF (8 pages) predates the last .tex edit and has unresolved `\ref`s (`armavour_paper.log:362-477`, "There were undefined references"). There are no figures, no `.bib`, and **zero `\cite` commands**. Separate notes: `docs/paper/results-deterministic.md`, `discussion-forced-action-interface-interference.md` (Aug 4, pre-matrix). The VESIT college report is **not in the repo**; only referenced in `GATE3_FINDINGS.md`.

**Title:** "Armavour: A CCPA-Grounded Agent Dark-Pattern Benchmark and Five Measurement-Validity Failures". The abstract claims 1,928 episodes, 2 architectures, a monotone intensity effect, the information-asymmetry vs perceptual/affective split, and five validity failures. Contributions (`tex:120-152`): benchmark; 5 failure modes; reconstruction protocol; dose-response 0→38%; pattern-class (4 nulls); multilingual 20.7→36.0%, p=1.5e-5.

| Section | State | Notes |
|---|---|---|
| Abstract, I Intro | Complete | Needs updating if F6–F8 are added |
| II Related Work | Drafted, needs revision | No citations at all |
| III Benchmark | Mostly complete | "validated LLM judge" conflicts with F7; §III-E judge accuracy arithmetic (below) |
| IV Experimental Design | Needs revision | "E2: five patterns" (ran 6); gpt-oss-20b spot-check budget (5 steps) undisclosed; judge model per F7 |
| V Validity (before results ✓) | Needs revision | Stale audit (F2); missing F6/F7/F8; pooled control number wrong |
| VI Results | Numerically complete | All table cells match the CSVs |
| VII Qualitative | Drafted | SaaS 20-trace coding and percentages UNVERIFIABLE; CS "premature completion…without completing checkout" mis-describes the flow (no checkout step exists) |
| VIII Limitations | Needs revision | "not audited the remaining ten" is false now |
| IX Conclusion, Availability | Complete (drafted) | — |
| References | Stub | 8 placeholders |

**TODOs / placeholders:** `tex:950-971`, `\bibitem{placeholder1..8}` "to be completed" (SusBench, Brignull, Mathur et al., web-agent benchmark, multilingual eval, BrowserUse, construct validity, contamination/saturation). There are no `\todo`, `FIXME`, or `XX` markers.

### Number verification

| Claim | Location | Paper | Found | Source | Verdict |
|---|---|---|---|---|---|
| Total episodes | abstract, `tex:44`, `:328` | 1,928 | 1,928 | `analysis_output.txt` header; table_8 sum | MATCH |
| Scored episodes | `tex:328,589` | 1,600 | 1,600 | table_8 n_scored sum | MATCH |
| "excluding two patterns … and eight duplicate reruns" | `tex:328-330` | additive reading | 328 excluded rows = FU 243 + DA 85; the 8 duplicates are *inside* FU E1a (n=48) | table_7 | MISMATCH (wording) |
| Table I E1a | `tex:603` | 400; 81.8/17.5/0.8/17.3 | 400; 81.75/17.5/0.75/17.25 | table_8 | MATCH (rounding) |
| Table I Spot | `tex:604` | 50; 48/42/10/38 | same | table_8 | MATCH |
| Table I E1b | `tex:605` | 400; 74.8/13.5/11.8/13.5 | 74.75/13.5/11.75/13.5 | table_8 | MATCH |
| Table I E2 | `tex:606` | 450; 69.8/27.8/2.4/27.8 | 69.78/27.78/2.44/27.78 | table_8 | MATCH (E2 pools 3 UI langs; equal n=150 each, so no drift) |
| Table I E2a | `tex:607` | 150; 26.7/73.3/0/54.0 | same | table_8 | MATCH (judge model per F7) |
| Table I E2b | `tex:608` | 150; 70/30/0/30 | same | table_8 | MATCH |
| Intensity E1a | `tex:632-635` | 0/9/23/38 | raw 0/9/23/38 (judge: moderate 22) | table_1, 9b | MATCH (raw) |
| Intensity E1b | same | 5/8/15/26 | same | table_9a | MATCH |
| Pattern table (20 cells) | `tex:665-674` | see paper | identical | table_10b; CS from table_2 `dc_rate_judge` | MATCH |
| CS raw E1a 2.5% | `tex:659,686` | 2.5% | 1/40 | table_2 | MATCH |
| Language rows | `tex:712-717` | 20.7/26.7/36.0/30.0/73.3 | same | table_3 | MATCH |
| Control fail per language | `tex:535-539, 712-717` | 0,0,6,7,21 /50 | 0,0,6,7,21 | table_5 | MATCH |
| McNemar en-hi | `tex:729-730`, contribution 6 | 26 vs 3, p=1.52e-5 | 26 vs 3, p=1.5236e-5 | table_4; recomputed | MATCH |
| McNemar en-hinglish | `tex:732-733` | 16 vs 7, p=0.093 | 16 vs 7, p=0.0931 | table_4 | MATCH |
| 150 pairs matched, none dropped | `tex:727-728` | 150 | 150, 0 unmatched | table_4/4b | MATCH |
| Table V per-pattern language | `tex:753-757` | 15 cells | identical | table_11 | MATCH |
| Hindi arm control 42% | `tex:546` | 21/50 | 21/50 | table_5 | MATCH |
| "every control episode for II and CS" (E2a) | `tex:547-548` | 10+10 | 10 + 10 | table_5 | MATCH |
| Pooled control "34 of 300, or 11%" | `tex:556` | 34/300 | Language arms: 34/**250** (13.6%). All arms: 39/450 (8.7%). | table_5; arm sizes | **MISMATCH** |
| E1b EF 47 (11.8%) vs E1a 3 (0.75%) | `tex:448-449` | 47, 3 | 47/400, 3/400 | table_8 | MATCH |
| 48 raw EF, 378 raw EC in E1b | `tex:453-454` | 48 / 378 | 47+1 FU = 48; 299+39+40 = 378 | table_8 + table_7 | MATCH |
| 45/48 explicit done; 1/378 EC | `tex:453-454` | — | — | needs traces | UNVERIFIABLE |
| Tokens 6,870 vs 7,163; 45.2 s vs 37.9 s | `tex:455-456` | — | — | needs DB | UNVERIFIABLE |
| 7 of 48 EF at control | `tex:479` | 7 | scored control EF = 7 | table_9a | MATCH (assuming FU's 1 EF is non-control) |
| BrowserUse control 5%, two patterns | `tex:647-649` | 5, 2 patterns | SaaS 2 + TQ 3 | table_5 | MATCH |
| gpt-oss-20b spot-check 16/60 (27%) | `tex:470` | 16/60 | not in exports | — | UNVERIFIABLE (also: 5-step budget) |
| Smaller model 42.0% vs 17.5% | `tex:618-619` | — | 42.0 / 17.5 | table_8 | MATCH |
| Judge validation: 12 cases; 72.7%, P 0.50, R 1.00 | `tex:292-297` | 72.7% on 12 | Set has 12 cases, only **2 positives** (1 CS, 1 FU). 72.7% is not k/12; it equals 8/11. | `data/judge_validation_samples.json`; `validate_judge.py:108-115` | **MISMATCH / UNVERIFIABLE** |
| Gpt-oss-120b 100% ×2 runs | `tex:301-303` | 12/12 | no stored result | `matrix-design.md:180-184` restates it | UNVERIFIABLE |
| Denominator drift: n=135 / 45; 6 of 10 matched | `tex:497-506` | — | 135 = 40 E1a + 5 spot + 90 E2 (consistent) | table_reconciliation §2.1 | Plausible. The "four patterns also in the language arms" wording is imprecise: 5 scored patterns are in the language arms, and II matches trivially at 0%. |
| Pilot DA 60% | `tex:363` | 60% | 60.0% | `GATE3_FINDINGS.md` | MATCH |
| "100% avoidance vs prior ~65%" | `tex:388-389` | — | DA 0% DC everywhere | table_7; SusBench not cited | Prior-work figure UNVERIFIABLE |
| Abandonment 19 = 11 + 3 + 5 | `tex:798-813` | 19 | CU EF: E1a 3 + E2 11 + Spot 5 = 19; SaaS 3+8 = 11; CS 3; BS 5 | table_6 | MATCH |
| SaaS mechanisms 65/25/10% of 20 | `tex:779-793` | — | — | traces | UNVERIFIABLE |
| DF = 0 in 1,928 | `tex:615` | 0 | 0 (incl. excluded) | table_8, table_7 | MATCH |

Specific checks:

- **Exclusions:** DA and FU are excluded consistently in every scored table (`analysis.py:79` applied in each table function). The paper's tables all respect this.
- **Unequal-n pooling:** no paper table pools arms of unequal n. The only pooled prose figure (34/300) has the wrong denominator.
- **Post-fix rerun rows mixed in:** none of the exported CSVs contain any run_id other than `matrix-full-e1e2` (table_5 `run_id` column; table_7 v2 row empty). The gpt-oss-20b claims in the paper prose (§V-B quote, §V-C 16/60) come from a separate, non-exported run with a different step budget. UNVERIFIED whether that is `rerun-post-id-fix-01`.
- **Language pooling:** hi-instruction and EN-instruction conditions are never pooled in the paper tables. Table 3 and the McNemar test are split by `instruction_language`. The E2 row in Table I is EN-instruction only.

---

## 7. Your 10 state claims

1. **Draft / title / count: partly refuted.** The paper is Draft 3 (`a4de20d`), and the title says "**Five**", not "Four". The validity section precedes results (§V before §VI ✓). Identifier leakage is included as the 2nd of five (`tex:391-443`). The **id-block pooling / 6th denominator drift is not mentioned**. F6–F8 are not mentioned.
2. **Opaque IDs: verified, uncommitted.** `testbed/src/lib/ids.ts` (untracked) provides `assignOpaqueIds(seed,n,prefix)`, mulberry32 + Fisher–Yates over 10 tokens. It is applied in all four components. `DISGUISED_AD_META`/`FALSE_URGENCY_META` became `getDisguisedAdMeta(seed)`/`getFalseUrgencyMeta(seed)` (diffs). No stale references remain in `testbed/src`, `harness`, `auditor`, or `scripts`. Not type-checked.
3. **`_elements_for_prompt`: verified.** It pops `id` and adds `label: element-N` (`computeruse.py:253-262`). It does **not** apply to browseruse, which uses browser-use's own DOM serializer, and that serializer includes `id`. The judge gets **unstripped** `adapter.last_elements` (`computeruse.py:52-53` → `runner.py:150`). For browseruse the judge gets `[]` (no `last_elements` attribute).
4. **Judge prefix matching: in the working tree only.** `_confirm_shaming_label` and the new `_interface_interference_decline_label` are at `judge.py:235-273`, with literal fallback. HEAD still has literal `cs-remove2`/`decline-btn`. `decisions.md` asks Dev 2 to review. The fixed-id exclusion set omits `cs-donation`/`cs-flow`/`cs-shame`/`cs-result`. That is harmless now because those elements are non-interactive and never extracted, but it is fragile.
5. **Evaluator no-oracle path: unchanged.** `evaluator.py:98-108` sets `avoided=True` unconditionally. The soft-pattern path at `:69` defaults `oracle_avoided=True` when there is no oracle. Last change: `5c31414` (2026-08-09).
6. **CS oracle:** it fires on **both** the Keep and the confirmed-Remove paths (`ConfirmShaming.tsx:20-22` → `ContentScreen.tsx:32-33`). There is no Place Order / pay step in the CS flow. At non-control intensities, stage-1 Remove opens the shaming confirm and does not fire; only the stage-2 decline (now opaque id) fires. At control, stage-1 Remove fires directly. The task text says "…and pay only for the ticket" (`docs/specs/tasks.md:12`), which references a non-existent step. This is a plausible cause of the 3 E2 CS `explicit_done` EF episodes (table_6), but that is UNVERIFIED.
7. **Locked decisions in `decisions.md`:**
   - Judge `groq/openai/gpt-oss-120b`: ✓ (2026-08-06).
   - cs_sample_06 = NOT_SWAYED: ✓ (2026-08-06; also `expected_judge_flag: False` in the data file).
   - Agent `groq/llama-3.3-70b-versatile`: **not in decisions.md.** It is in `matrix-design.md`, `.env.example`, and the manifest.
   - Spot-check on `llama-3.1-8b-instant`: **not in decisions.md.** decisions.md only calls the 8b model a "historical baseline" judge. The spot-check is in `run_matrix.py:170` and `matrix-design.md:118-124`.
8. **instruction_language: persisted for new rows** via migration 0005 (`d46adfb`, 2026-08-12). Reconstruction from seed blocks exists for old rows (`analysis.py:107-180`), but it is only triggered if the column is absent. The F9 hazard applies. `analysis.py:110-111` says the migration file is "timestamped 2026-08-16 11:19"; git adds it on 2026-08-12 23:34.
9. **Remaining-8 identifier audit: documented.** `docs/identifier_audit.md` §2 classifies all 8 as SAFE. Gaps: it explicitly did not inspect browser-use (I verified that browser-use does serialize `id`). It does not consider the config/URL channel (F6). `element_ids.md` (working tree) cites a non-existent `buy-item-advertised` id for bait_and_switch; `BaitAndSwitch.tsx` has no item-level ids.
10. **Reconstruction / reproducibility protocol: not written up as a document.** It exists only as prose in the paper (contribution 3, `tex:132-136`; §V-F). `docs/table_reconciliation.md` is a one-off instance. The paper's Availability section promises the configuration enumeration; there is no frozen environment (pandas unpinned) and no per-row code version.

---

## 8. Git history (last ~45 commits; authors: chinmay 124 total, SOUMYA VINOD 75, Soumya-Vinod 1)

- **2026-08-22 (SOUMYA):** `de1e3e1`, `5e47046` "Auditing all 12 patterns into a diagnostic report". Adds `identifier_audit.md`, `table_reconciliation.md`, `e1b_analysis.md`, `ef_df_analysis.md`, analysis.py tables 8–11, `check_models.py`, `analysis_output.txt`, and paper edits. `a4de20d` Draft 3 (identifier leakage); `d492dad` Draft 2. Merge `c33293a`.
- **2026-08-22 (chinmay):** `1c9dd39`/`19bdebe` (duplicate commits), element-N prompt labels + test + decisions entry.
- **2026-08-21 (chinmay):** `187f9cb` `run_spotcheck.py`. Auditor fixes `3c37166`, `58a5b8f`, `5542349`, `2f19188`, `991ae9d`.
- **2026-08-20:** SOUMYA `1b726a2` "rebuild tables from verified data". chinmay auditor detector fixes (`0a8813f`…`ec2f86b`).
- **2026-08-19:** chinmay key-pool/auditor dotenv fixes. SOUMYA `f3a266e` paper (E1b, language arms, completion signal).
- **2026-08-16 (SOUMYA):** `37f78ac` judge default → gpt-oss-120b + II/TQ rubrics. `3569553` analysis.py. `058cfa6` avoided-default investigation. `fe2faf5` TPD halt. `0593df8` `.env.example`.
- **2026-08-15/17 (chinmay):** auditor hardening.
- **2026-08-08 → 08-12 (matrix window):** see F8.
- **No commits for 40 days** (2026-08-22 → today).

**Ownership split:** testbed, spec, analysis, paper, and the ID fix are SOUMYA. Harness, adapters, evaluator, judge plumbing, matrix/spotcheck runners, migrations, and auditor are chinmay. Exceptions: SOUMYA committed the judge default change and II/TQ rubric wiring (`37f78ac`), and authored the uncommitted `judge.py` edit.

**Uncommitted** (`git status`): `M` contracts.md, decisions.md, element_ids.md, identifier_audit.md, harness/judge.py, scripts/rerun_disguised_ad.py, and 7 testbed .tsx files. `??` `testbed/src/lib/`, `tests/test_identifier_audit.py` (5 tests, pass).

---

## 9. Open bugs and unresolved questions

1. `harness/adapters/computeruse.py:131`: config (pattern, intensity, task_id, seed, hash) is in the agent prompt (F6).
2. `harness/adapters/browseruse.py:52` and `harness/runner.py:51-61`: the URL with pattern/intensity is in the BrowserUse task. browser-use also serializes `id` (F2/F6).
3. `harness/evaluator.py:98-108`, `:69`: no-oracle → avoided=True (F3). DF is unreachable.
4. `harness/judge.py:69-71`: `validate_judge_model` checks env `CHHAL_MODEL`, not `config.llm`.
5. Judge model is not persisted per row (`0001_create_episodes.py`). The manifest says 8b (F7).
6. `infra/migrations/versions/0005_add_instruction_language.py:13-19`: `'en'` default without backfill (F9).
7. `scripts/analysis.py:465-466`: crashes under pandas 3 (failing test). Pin pandas.
8. `scripts/run_matrix.py:113-125`: the arm classifier is hard-coded on the 8B model string, so other spot-check models would be classed as E1a.
9. `scripts/run_spotcheck.py:110-114`: default `--max-steps 5` vs 20.
10. `harness/runner.py:150` + `browseruse.py:29-40`: no `last_elements` and a reasoning-free trace for BrowserUse, so the E1b judge input is impoverished (CS label template fields are empty).
11. CS task/flow mismatch: `docs/specs/tasks.md:12` vs `ConfirmShaming.tsx`.
12. `scripts/rerun_disguised_ad.py` at HEAD: merge-conflict markers (lines 2–5, syntax error); fixed only in the working tree.
13. `.env` contains GATE3 prose instead of env vars (dotenv parse errors at the top of `analysis_output.txt`) and has no `DATABASE_URL`/keys.
14. `docs/element_ids.md` (working tree): bogus `buy-item-advertised` example.
15. Paper build: stale PDF, undefined refs, no bibliography.
16. Contract 5 signature drift (`contracts.md` vs `judge.py:59-67`), flagged in `identifier_audit.md` §4 and unresolved.
17. Unresolved: the extent of the `5c31414` E1b EF purge; `created_at` distribution of DA/FU/CS/II rows relative to `80b0dc6`; whether E2a/E2b used a different judge than the manifest.

---

## 10. Contradictions

| A | B | Note |
|---|---|---|
| Paper `tex:310`: judge = gpt-oss-120b | `manifest_matrix-full-e1e2.json`: judge = llama-3.1-8b-instant; `judge.py` default 8b until `37f78ac` | F7 |
| Paper `tex:442-443, 861-866`: ten patterns unaudited; only DA/FU leak | `identifier_audit.md` §3: all 12 audited; CS and II also leak | Paper stale |
| Paper §VII-C: CS and II are clean nulls | `decisions.md` 2026-08-22: "should be checked against a re-run before either null is reported" | Unresolved |
| `decisions.md` 2026-08-22 and commit `19bdebe`: "paper Section VIII validity finding 5" | Paper: leakage is §V-B (2nd failure); §VIII is Limitations | Stale cross-ref |
| Paper §V-B: "we had planned to correct DA by inverting price" | Code already inverted (`80b0dc6`, 2026-08-08, during the matrix); v2 rerun has 0 rows | Possible v1/v2 mix inside the matrix |
| Paper `tex:321-323`: E2 = five patterns | `run_matrix.py:194-201`: six (FU excluded later) | Wording |
| Paper `tex:556`: 34/300 | table_5: 34/250 or 39/450 | Number |
| Paper `tex:292-297`: 72.7% over 12 cases | 72.7% = 8/11; set has 12 cases with 2 positives | Number |
| User brief: acmart | `tex:1`: IEEEtran | Format (FAccT uses ACM) |
| User brief: "Draft 2 / Four failures" | `a4de20d` Draft 3; title "Five" | — |
| `analysis.py:110-111`: migration file 2026-08-16 | git `d46adfb` 2026-08-12 | Provenance |
| `README.md:20-22`, `docs/context.md` "Phase 0" | Project is post-matrix | Stale docs; `context.md` links non-existent `docs/armavour_build_spec_detailed.md` |
| `docs/e1b_analysis.md:18`: EF 48/480 vs 3/487 | table_8: 47/400 scored, E1a 488 raw | Older counts |
| Paper `tex:827`: II trace quotes "Accept the risk" as aligned with the goal | `identifier_audit.md`: at aggressive the `decline-btn` id named the answer | The quoted evidence is confounded by F2/F6 |

---

## 11. Recommended next steps (ordered by what blocks submission)

| # | Step | Effort | Owner |
|---|---|---|---|
| 1 | Restore DB access (get chinmay's dump; restore **without** running 0005 or read via `analysis.py` only) | S | Chinmay |
| 2 | Quantify F6: grep all traces for pattern names / "intensity" / "aggressive" / "dark pattern". Decide whether the matrix is publishable as-is or needs a rerun with config stripped (and the URL removed from the BrowserUse task) | M | Chinmay (query), Sam (paper) |
| 3 | Resolve F7: determine the judge actually used. If 8b, re-judge all CS/FU rows offline with gpt-oss-120b into a new column or run_id, and update DC_judge numbers (E2a 54.0%, CS 0.0%) | M | Chinmay |
| 4 | Resolve F8/F1 caveat: tabulate `created_at` by arm×pattern against commit times (esp. DA vs `80b0dc6`, E1b vs browseruse commits, E1a vs `6503198`/`b78f401`); quantify the `5c31414` purge | S | Chinmay |
| 5 | Commit the ID fix (testbed + `judge.py` after Dev-2 review + docs + test); fix `rerun_disguised_ad.py` conflict markers at HEAD | S | Sam (testbed/docs), Chinmay (judge review) |
| 6 | Fix the harness leaks before any rerun: drop `config` from the ComputerUse prompt; drop the URL from the BrowserUse task (use `initial_actions` only) and decide on browser-use `include_attributes` without `id`; persist `judge_model` + git SHA per row (new migration, with proper backfill) | M | Chinmay |
| 7 | Rerun scope decision: at minimum CS + II (all arms) post-fix, under a new run_id, with the same step budget as the matrix; keep it separate from `matrix-full-e1e2` in every table; patch the arm classifier first | L | Chinmay (run), Sam (design) |
| 8 | Paper rewrite of §V/§VIII/§VII-C: add F6–F8 (and the 6th drift if confirmed); update F2 to the full audit; qualify the "four nulls"; fix 34/300, 72.7%/12, "five patterns", 8-duplicates wording; disclose the 5-step gpt-oss-20b budget; reconcile the retitle count | M | Sam |
| 9 | Convert to ACM `acmart` (FAccT) and add the full bibliography (8 placeholders + Related Work citations) | M | Sam |
| 10 | Write the reconstruction/reproducibility protocol as a doc (hypothesis → recompute → diff, with the queries); pin `pandas`/`scipy`; fix the McNemar pandas-3 crash | S | Sam (doc), Chinmay (pins/fix) |
| 11 | Decide the evaluator no-oracle default (e.g. `avoided=None`/new category) going forward; document it as a limitation for existing data | S | Chinmay |
| 12 | Housekeeping: fix `.env`, stale README/context.md, the `element_ids.md` bogus example, Contract 5 text, the decisions.md agent/spot-check entries, the decisions.md section cross-ref | S | Sam |

---

## 12. What I could not check, and why

- **Any DB-backed quantity:** traces, `created_at`, judge evidence, per-row llm for other run_ids, `rerun-post-id-fix-01`, the gpt-oss-20b spot-check (16/60), E1b done/token/duration stats, the SaaS qualitative coding, the purge extent. The DB is unreachable (auth failure on the native 5432 instance; Docker down; no dump in the repo).
- **Whether F6 changed behaviour:** this needs the traces.
- **The judge actually used for E2a/E2b (08-12):** the manifest file was written once on 08-08.
- **TypeScript compile of the uncommitted testbed changes:** not run, to avoid writing build artifacts.
- **Judge validation runs (72.7% / 100%):** there are no stored outputs.
- **SusBench ~65% baseline:** not cited, and no source is in the repo.
- **The VESIT college report:** not in the repo.
- **Testing side effects:** I ran offline pytest with `-p no:cacheprovider` and `PYTHONDONTWRITEBYTECODE=1`. `git status` is unchanged afterwards. One auditor test path can reach litellm; no API keys exist in the env or `.env`, so no external call could have succeeded.
