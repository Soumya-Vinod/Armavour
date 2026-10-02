# FAccT draft — status

Target: `docs/paper/armavour_facct.tex` (acmart `sigconf,review,anonymous`). Deadline 2026-10-27. Double-blind.

| Phase | Status | Notes |
|---|---|---|
| 1 Numbers ledger (`NUMBERS.md`) | DONE | ~110 entries. Ablation trace claims (5/6 name the tactic, 2 verbatim, 0/200, 3 control) and the SaaS Llama 15/15 vs Qwen 10/10 contrast were re-verified by read-only queries Q-P1…P8, whose SQL is in the NUMBERS appendix. |
| 2 Draft (`armavour_facct.tex`, `refs.bib`) | DONE | All sections per brief. Tables T1, T3, T4, T2, T6 are `\input` from `docs/paper/tables/`. `refs.bib` has 14 candidate entries, all `% VERIFY`. |
| 3 Check (compile, ledger cross-check, anonymity, `REVIEW_NOTES.md`) | DONE (compile not possible) | `acmart` is not installed and installing is forbidden, so no PDF. Static checks pass: environments and braces balanced, all `\ref` and `\input` resolve, no non-ASCII. All 163 `% N:` tags resolve to ledger ids; 17 untagged generic number-words are listed in REVIEW_NOTES §5. The anonymity grep is clean: no names, institutions, URLs or commit hashes. Page count is an estimate (~7–8 pp excluding references), UNVERIFIED. |

## Files written in this task

| File | Status |
|---|---|
| `D:\BCA\MCA\RESEARCH\armavour\docs\paper\armavour_facct.tex` | rewritten (FAccT draft) |
| `D:\BCA\MCA\RESEARCH\armavour\docs\paper\refs.bib` | new |
| `D:\BCA\MCA\RESEARCH\armavour\docs\paper\NUMBERS.md` | new (163 ledger ids + SQL appendix) |
| `D:\BCA\MCA\RESEARCH\armavour\docs\paper\DRAFT_STATUS.md` | new |
| `D:\BCA\MCA\RESEARCH\armavour\docs\paper\REVIEW_NOTES.md` | new |

No git writes, no episodes, no LLM calls. Databases were queried only read-only (`default_transaction_read_only=on`): `armavour_ablation` and `armavour_audit`, queries Q-P1…P8. `armavour_paper.tex`, `docs/paper/tables/*.tex`, `docs/audit/*` and all code are untouched.

## Next steps (for the author)

1. Install `acmart`, compile, and fix layout (taxonomy table\*, T1 width). Record the real page count here.
2. Resolve the 3 TODO citations and the 14 `% VERIFY` bibliography entries (REVIEW_NOTES §2–3).
3. Decide the open phrasing questions in REVIEW_NOTES §6 (especially the 1205 quote and the SaaS "two readings" framing).
4. Fill CHECK-CFP items: venue macros, CCS concepts, ethics, adverse impact, positionality.
