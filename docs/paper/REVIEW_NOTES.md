# REVIEW NOTES — `armavour_facct.tex` (draft of 2026-10-02)

## 1. Compile status

- **Not compiled.** `acmart.cls` is not installed: it is absent from the MiKTeX trees, and MiKTeX `[MPM]AutoInstall = 2` (ask), so a compile would try to install it. The brief forbids installing anything.
- **To compile yourself:**
  ```
  miktex packages install acmart
  cd docs/paper
  latexmk -pdf armavour_facct.tex
  ```
- **Static checks that passed** (scratch script `check_paper.py`):
  - every `\begin`/`\end` balanced; braces balanced;
  - all five `\input{tables/...}` files exist;
  - every `\ref` resolves (including the labels inside the `\input` tables);
  - no non-ASCII characters in the `.tex` or the `\input` tables.
- **Page count: UNVERIFIED estimate of ~7–8 pages excluding references.**
  - Basis: ~5,100 words of body text, about 4.5–5 pages in sigconf; tables about 2–2.5 pages (patterns table\*, taxonomy table\*, T1/T4/T6 table\*, T2/T3 single-column).
  - That is well under the 14-page target. **CHECK-CFP** the real FAccT limit, and confirm after compiling.
- **Expected warnings on first compile:**
  - three undefined citations (the TODO keys below), which render as [?];
  - possibly overfull boxes in the 11-column T1 table\* and the 5-column taxonomy table\* (`\footnotesize`, fixed-width `p{}` columns).
  - Check the taxonomy table fits on one page.

## 2. TODO citations (`\cite{TODO-...}`, not in refs.bib)

| key | where | what to find |
|---|---|---|
| `TODO-prior-agent-darkpattern-benchmarks` | §2 "Agent benchmarks" | Prior benchmarks of agent susceptibility to dark patterns / deceptive UI. The earlier draft named "SusBench" and cited per-pattern avoidance baselines (~65% DA, ~90% CS, ~45% trick wording, ~11% hidden information) and Tang et al. "Urgency/Scarcity", "Adding Steps", "Trick Questions" (in `docs/specs/*.md` §8). Find exact papers before citing any of these figures; none of them is in the paper now. |
| `TODO-multilingual-llm-evaluation` | §2 "Agent benchmarks" | Evidence that LLM performance degrades in lower-resource languages / Hindi / code-mixed Hinglish. |
| `TODO-contamination-saturation` | §2 "Measurement validity" | A standard reference on benchmark contamination and/or saturation. |

## 3. Bibliography entries to verify (all 14 carry `% VERIFY`)

Every entry in `refs.bib` holds only the fields given in the brief. Specific gaps:

- **Author lists are incomplete.**
  - Surnames only, no initials: `raji2021benchmark`.
  - "and others" placeholders: `mathur2019darkpatterns`, `gray2018dark`, `zhou2024webarena`, `deng2023mind2web`, `xie2024osworld`, `kapoor2024agents`, `reuel2024betterbench`.
  - ACM-Reference-Format will print these as given.
- **Venues are abbreviations** (FAccT, NAACL, CSCW, CHI, ICLR, NeurIPS). Expand them to the full proceedings names.
- `ccpa2023guidelines` has no publisher or issuing ministry, and no gazette reference.
- `browseruse` has no year, version or URL. The paper used **browser-use 0.13.4** (`harness/requirements.txt`); add that and the project URL.
- `kapoor2024agents` is an arXiv preprint. Check whether a published version exists.

## 4. CHECK-CFP items

- `\acmConference`, `\acmYear`, `\setcopyright` (currently `none`): header comment in the `.tex`.
- **CCS concepts** are not chosen. The `CCSXML`/`\ccsdesc` block is commented out (`TODO(ACM)`).
- **Ethical Considerations:** confirm the required heading, placement (inside or outside the page limit) and length.
- **Adverse Impact Statement:** confirm FAccT still requires it, and its required form.
- Whether FAccT also asks for a **Researcher Positionality Statement** or similar. None is drafted.
- **Page limit:** target ≤ 14 pages excluding references. The draft is probably well under, so there is room to expand §2 and §8.
- **Anonymity:**
  - the repository is cited as "[anonymized repository]";
  - no commit hashes appear in the text (a hash could be searched to deanonymise);
  - episode ids (312, 391, 1205, 1214) are internal and safe.

## 5. Numbers without a `% N:` tag (17 lines; none reports a result)

These are generic counting words or task text, not measured quantities. Listed so they can be checked.

| line (approx) | text | why untagged |
|---|---|---|
| 70 | "three clean findings" | editorial count of the claims listed in the same sentence |
| 153 | "repeated seeds within one condition" | generic |
| 169 | "within one session" | generic |
| 183 | "buy one ticket" | task text (Table 1) |
| 201 | "double negatives" | descriptive term |
| 207 | "asks the model for one action" | describes the adapter |
| 213 | "coded on two axes" | definitional (EC/DC/EF/DF) |
| 256–257 | "one question per reported number", "five procedures" | editorial; the five are (a)–(e) in the same section |
| 313 | "one UI state" | taxonomy table text |
| 328 | "within one run" | taxonomy table text |
| 365 | "Two other divergences" | editorial; the two are named in the same paragraph (nagging, subscription trap) |
| 393 | "double negative requires" | descriptive |
| 523 | "a small one" | quoting the pilot's claim |
| 620 | "one per failure class" | editorial |
| 646 | "and one that understates it" | pronoun |
| 704 | "one retired model, one ablation model" | descriptive, consistent with RET-rows / ABL-model |

All 163 `% N:` tags resolve to ledger ids (109 distinct ids used).

## 6. Claims I was unsure how to phrase

- **"In four of six arms, roughly half" (abstract), "roughly half" (intro).** The shares are E1a 47, Spot 48, E2 49 and E1b 63%; E2b is 44% and E2a 17%. The brief asked for "roughly half of each arm". I narrowed it to four of six arms, because "each" is false for E2a.
- **TQ moderate example (1205).** The agent's reasoning is muddled: it says "check the box to opt out of receiving", then "actually means to opt out". Its final state (ticked = not receiving, on the label's semantics) matches the task, and it was scored DC.
  - The quote is accurate, but a reviewer may read it as confusion rather than a correct reading.
  - **1214 (aggressive) is the clean example.** Consider keeping only 1214.
- **SaaS billing aggressive: "Both behaviours are defensible readings".**
  - Llama completed the only available action (15/15 DC). Qwen declined (10/10 EF per arm).
  - I argue that neither measures susceptibility. A reviewer may argue that Llama's completion *is* susceptibility (the price is disclosed on the page). The point that survives either way: the cell cannot score avoidance-with-completion.
- **Drip pilot: "most likely from a checkout that did not yet contain it".**
  - This is inferred from git ancestry (CT Part A, UNVERIFIED).
  - The phrasing avoids naming who ran it, for anonymity.
- **Ablation significance.** The 6-vs-1 discordance has p = 0.125. The text reports the p-value and says the effect "concentrates in one cell", but does not call it significant. The semantic-use evidence (5/6 name the tactic; 0/200 without config) carries the claim.
- **Language.**
  - Stated as "a consistent direction resting on three or four cells". The pair-level p is reported only with the pseudo-replication caveat, and is not in the abstract (per the brief).
  - "Three or four" reflects that one of the four cells is the non-manipulative TQ control.
- **BrowserUse step budget "probably five".** This is the runner default (FU A1); it cannot be confirmed from the data.
- **Judge size.** The text says the judge was "a gpt-oss model; which size cannot be determined". It omits the earlier draft's claim of gpt-oss-120b.
- **Visual-only manipulations.** These are presented as failures for *text* agents. The specs were written partly with human or vision perception in mind, so a reviewer may see this as a scope limitation rather than an implementation failure.

## 7. Section lengths (approx. words, excluding tables)

| section | words | note |
|---|---|---|
| Abstract | 199 | on target (~200) |
| 1 Introduction | 522 | fine |
| 2 Background & Related Work | 329 | **short**: thin until the TODO citations are filled; expand once references are found |
| 3 The Benchmark | 353 | fine, plus Table 1 |
| 4 Original Results | 136 | short by design ("Short" per brief) |
| 5 Audit Method | 306 | fine |
| 6 Taxonomy | 1,780 | **longest**: carries the paper; if space is needed, trim the visual-only and provenance paragraphs |
| 7 Corrected Results | 583 | fine, plus 5 tables |
| 8 Discussion | 421 | could grow (consumer-protection implications) |
| 9 Limitations | 142 | adequate |
| 10 Conclusion | 120 | fine |
| Ethics / Adverse impact / Availability | 77 / 53 / 18 | CHECK-CFP |

## 8. Other notes

- **Tables T5 and T7 are not `\input`.** The language-condition rates appear in prose instead. Add `\input{tables/T5_language}` and `\input{tables/T7_language_pattern}` if space allows.
- The `\input` table captions contain the literal mode string "(exclude\_breaking=True, st\_abandon=as-is)". That is fine for review; consider a cleaner caption by re-running `scripts/corrected_tables.py` with edited captions. The tables are not edited here, per the brief.
- **The old content of `armavour_facct.tex`** (a mechanical acmart conversion of `armavour_paper.tex`) was replaced entirely. The IEEE draft `armavour_paper.tex` is untouched, and the previous acmart conversion is recoverable from git.
- **Benchmark-description prose** reuses the still-accurate parts of `armavour_paper.tex` §III, condensed. All claims the audit overturned were removed: the "validated LLM judge", "four nulls" as a finding, "monotone dose-response" and the "completion signal" mechanism.
