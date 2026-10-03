# Writing the submission

## The one rule

- **Edit `drafts/*.md` only.** One file per section; the file names match the section order in `main.tex`.
- **Never edit `sections/*.tex`.** `build.py` overwrites them on every build, and git ignores them.
- `main.tex` holds the title, keywords and section order. Edit it only for those.

Each draft starts with its `# Section title`, followed by an HTML comment holding the outline for that section. Comments never reach the PDF: keep them as notes or delete them as you write. Do not put `-->` inside a comment.

## Markdown cheat sheet

| You type | You get |
|---|---|
| a blank line | a new paragraph |
| `## Heading` / `### Heading` | subsection / subsubsection |
| `*italic*` / `**bold**` | *italic* / **bold** |
| `\cite{key}` or `\cite{key1,key2}` | citation (keys are in `../refs.bib`) |
| `Table~\ref{tab:r1}` | "Table 1", with a non-breaking space |
| `Figure~\ref{fig:dose}` | "Figure 1" |
| `Section~\ref{sec:06_taxonomy}` | section reference (each section's label is `sec:<file name>`) |
| `\input{tables/R1_intensity}` **on its own line** | the table |
| `\input{figures/fig_dose_response}` on its own line | the figure |
| `50%` | a percent sign (no backslash needed) |
| `- item` / `1. item` | bulleted / numbered list |

Any other LaTeX command works as typed. A footnote is `^[footnote text]`.

## Tables and figures

| Label | File | `\input` line | Made by |
|---|---|---|---|
| `tab:r1` | `tables/R1_intensity.tex` | `\input{tables/R1_intensity}` | `python scripts/make_rerun_tables.py` |
| `tab:r2` | `tables/R2_h1_cells.tex` | `\input{tables/R2_h1_cells}` | same |
| `tab:r3` | `tables/R3_pattern_intensity.tex` | `\input{tables/R3_pattern_intensity}` | same |
| `fig:dose` | `figures/fig_dose_response.tex` (+ `.pdf`) | `\input{figures/fig_dose_response}` | `python scripts/make_figures.py` |
| `tab:corr-*` | `../tables/T1_outcome.tex` … `T7_language_pattern.tex` | e.g. `\input{../tables/T3_intensity}` | `python scripts/corrected_tables.py` |

All captions are one-line placeholders. Rewrite them in the generated `.tex` files, or copy a table into `tables/` under a new name if you do not want a regeneration to overwrite your caption.

## Building

Run from the repo root:

```
python docs/paper/submission/build.py            # drafts -> sections -> main.pdf
python docs/paper/submission/build.py --no-pdf   # convert only (fast)
python docs/paper/submission/build.py --watch    # rebuild whenever a draft, table or figure changes
```

The build prints undefined citations and references, the page on which the Conclusion ends (the counted length; the limit is 14 pages excluding references), and the total page count. The PDF is `docs/paper/submission/main.pdf`.

The build uses latexmk if it works, and otherwise falls back to pdflatex → bibtex → pdflatex ×2.

## Where the facts are

- `docs/paper/NUMBERS.md`: every number the paper may use, with its source. Rerun numbers are the `R-*` ids.
- `docs/paper/OUTLINE01.md`: the section-by-section outline. Each draft's comment holds a copy of its section.
- `docs/audit/README.md`: reading order of the audit reports. Later reports override earlier ones.
- `docs/paper/refs.bib`: bibliography. Entries marked `% VERIFY` are not yet checked.
