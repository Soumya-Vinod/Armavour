# Armavour

**Do dark patterns fool AI shopping agents — and does consumer-protection law still work when the consumer is an agent?**

Armavour is a benchmark and audit suite for evaluating how LLM computer-use agents respond to India's legally codified dark patterns (the CCPA *Guidelines for Prevention and Regulation of Dark Patterns, 2023*), including tasks replicated from real enforcement actions, in English, Hindi, and Hinglish.

> Research project targeting FAccT / COMPASS 2027. Private until the arXiv preprint (planned Phase 4).

---

## Why this exists

Recent work shows LLM web agents are highly susceptible to dark patterns — but all of it uses academic taxonomies on Western, English-only sites, and it stops at *measuring* the problem. Armavour is different on four axes:

- **Legally grounded.** Built on the CCPA's 13 codified patterns (unfair trade practices under the Consumer Protection Act 2019), not an academic taxonomy.
- **Enforcement-anchored.** Signature benchmark tasks replicate interfaces from real CCPA orders (PhysicsWallah, McAfee).
- **Multilingual.** First English / Hindi / Hinglish evaluation of agent susceptibility.
- **Auditing, not just measuring.** An agent-based auditor that flags CCPA violations, validated on the testbed and deployed as a field audit of real Indian platforms.

## Status

**Phase 0 — foundation.** The spike is built and the deterministic measurement is verified (see quick start). Testbed, harness, and auditor are in progress.

## Architecture

![Armavour architecture](docs/armavour_architecture.svg)

The whole project runs on one unit of work — an **episode**: one agent attempting one task on one page with one dark pattern at one intensity in one language. A config describes the episode → the testbed renders it → the harness drives an agent through it → an oracle (deterministic) or a judge (fuzzy cases) decides whether the agent was deceived → one row lands in Postgres. Repeat across the matrix, then analyse.

## Repository layout

| Path | What lives here |
|---|---|
| `testbed/` | React sites, the 12-pattern injection engine, the trilingual strings, the oracle. |
| `testbed/spike/` | The verified Phase-0 spike (BookMyShow-style ₹1 basket-sneak), used by CI. |
| `harness/` | Playwright + LLM agent runner, adapters, judge, evaluator, logger, and the zero-API verifier. |
| `auditor/` | Agent-as-auditor pipeline + field-audit tooling. |
| `infra/migrations/` | Alembic migrations for the Postgres `episodes` table (`0001`–`0007`). Compose file: `docker-compose.yml`; CI: `.github/workflows/ci.yml`. |
| `scripts/` | Run scripts (`run_matrix.py`, `run_leak_ablation.py`, `run_rerun.py`) and analysis (`analysis.py`, `corrected_tables.py`, `analyze_ablation.py`, `score_v2.py`, `analyze_rerun.py`), plus one-off diagnostics. |
| `tests/` | pytest suite; integration tests (`-m integration`) need the dev servers. |
| `data/` | Judge validation samples (other contents gitignored). |
| `results/`, `logs/` | Run outputs, manifests and logs (gitignored). |
| `docs/` | The five contracts, decision log, element IDs, oracle fields, rubrics, matrix design, taxonomy crosswalk, identifier audit. |
| `docs/specs/` | Per-pattern and task specs. |
| `docs/legal/` | CCPA guidelines, enforcement orders, related-work PDFs. |
| `docs/audit/` | Audit reports and the corrected rerun; start with `docs/audit/README.md` for the reading order. `evidence/` holds raw outputs the reports cite. |
| `docs/paper/` | Reference draft (`reference_generated_draft.tex`), `refs.bib`, generated `tables/`, the numbers ledger `NUMBERS.md`. |
| `docs/archive/` | Superseded material kept for history: the IEEE draft, Aug pilot notes and diagnostics, Phase-0 context and test spec, old prompts, the matrix design proposal, the repo cleanup plan. |

## Quick start

**1. Verify the measurement — no API key needed (~2 min).**

```bash
cd harness
python -m venv ../.venv
../.venv/bin/activate      # Windows: ..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python verify_page.py
```

Expected: `PASS — deterministic measurement works.`

**2. Run the spike — needs an API key.**

```bash
cp .env.example .env        # then edit .env: key, model, live pricing
python agent_spike.py --episodes 10
```

Results and per-episode cost are written to `harness/spike_results.csv`. Set `CHHAL_MODEL` from https://docs.claude.com/en/docs/about-claude/models and the pricing fields from https://www.anthropic.com/pricing before trusting the cost extrapolation.

## The five interface contracts

The codebase meets in exactly five places, defined in `docs/contracts.md` and versioned. Changes go through a PR, never a silent edit.

1. **Episode config** — the JSON the testbed accepts and the harness sends.
2. **Oracle** — the deterministic result the page exposes after the agent acts.
3. **Element IDs** — stable, unique identifiers the harness relies on.
4. **Episode log schema** — the Postgres table analysis reads.
5. **Judge rubric** — CCPA-grounded prompt text for the non-deterministic patterns.

## Team & workflow

Two developers. Dev 1 owns the testbed, legal spec, analysis, and paper; Dev 2 owns the harness, auditor, and infrastructure. Full ownership map, build spec, and phase plan are in `docs/`. `main` is protected — branch, PR, review, merge.

## Roadmap

Phase 0 foundation (spike, infra) → 1 legal spec → 2 testbed → 3 harness + pilot → 4 main experiments + **arXiv preprint** → 5 auditor → 6 field audit → 7 analysis + writing → 8 submit (FAccT → COMPASS → IUI/CHI).

## Docs

Start with `docs/` — the blueprint, the 8-phase execution guide with gates, the CCPA-13 test spec, the taxonomy crosswalk against prior work (SusBench, Ersoy, Tang), and the detailed build spec.

## License

MIT — see `LICENSE`.

## Citation

If you use Armavour, please cite the paper (to appear). A `CITATION.cff` will be added with the preprint.
