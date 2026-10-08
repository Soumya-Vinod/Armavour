<!--
## Endmatter (extra page, not counted)
- Generative AI usage statement (required; agree wording with co-author): Claude Code for code, data analysis, audit scripts, tables/figures, literature search, fact ledger and outline; all text written by authors
-->
<!-- Facts to state (write in your own words; agree wording with co-author):
- Claude Code (state model/version) used for: code, testbed fixes, analysis and audit scripts, data analysis, tables and figures, the numbers ledger and section outline, repository/anonymity audit.
- Claude (chat) used for: planning, critique of author drafts, literature search; every source verified by the authors.
- All paper text written by the authors; no LLM-generated text in the paper.
- Name any grammar/spell-check tools used.
- Statement must come from all authors. -->

We used two generative AI tools from Anthropic throughout this project.

*Claude Code*, an AI coding assistant, wrote and debugged much of the project's code, including the testbed repairs, the agent harness, and the analysis and audit scripts. It ran the data analyses through read-only database queries, produced the tables and figures, and compiled the ledger that links every number in the paper to its source. It also wrote the outline of the paper and drafted the text of every section from that outline and the ledger.

*Claude*, the chat assistant, was used for planning, for literature search, and to review every section of the draft.

We directed this work, checked the numbers in the paper against the ledger and the underlying data, and revised the drafts. We take full responsibility for the paper's content, analysis and conclusions.
<!-- TODO(authors), all must be resolved before submission; an inaccurate statement is grounds for desk rejection:
(1) State the model and version(s): this Claude Code session ran Claude Opus 5.5; earlier sessions and the Claude chat sessions may have used other models.
(2) If you rewrite the text in your own words, change "drafted the text of every section" to describe what remains (e.g. "drafted an initial version of the text, which we rewrote"). Do not say "all text was written by us" unless that is literally true.
(3) Add "we checked every cited source" only after the refs.bib entries marked % VERIFY have actually been checked.
(4) Name any grammar or spell-check tools, and match the FAccT 2027 CFP's required wording.
(5) All authors must agree the final statement. -->
