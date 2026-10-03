# Armavour — Project Context (start here)

## What this is
A research benchmark + audit suite testing whether LLM computer-use agents
get fooled by India's legally-defined dark patterns (the CCPA "Guidelines for
Prevention and Regulation of Dark Patterns, 2023"), in English, Hindi, and
Hinglish. Target: FAccT / COMPASS 2027. Repo is private until the arXiv preprint.

## The one mental model: an "episode"
Everything runs on one unit of work. An episode = one AGENT attempting one TASK
on one fake shopping page that has exactly one DARK PATTERN switched on, at one
INTENSITY, in one LANGUAGE. Pipeline: a config describes the episode -> the
testbed renders it -> the harness drives an agent through it -> an oracle
(deterministic) or a judge (fuzzy cases) decides if the agent got tricked ->
one row is written to Postgres. Repeat across the whole matrix, then analyse.

"Dark pattern" = a deceptive UI trick (e.g. a pre-ticked donation added to the
cart unless you untick it). "Avoided" = the agent removed/declined the trick.

## Who owns what
- Dev 1: testbed (React sites + 12 patterns + oracle), legal spec, analysis, paper.
- Dev 2: harness (Playwright + agent frameworks), judge, evaluator, Postgres,
  Docker/CI, auditor.
Full detail: docs/armavour_build_spec_detailed.md and the division-of-labour doc.

## The five interface contracts (where our code meets — see docs/contracts.md)
1. Episode config — JSON the testbed accepts / the harness sends.
2. Oracle — deterministic result the page exposes after the agent acts.
3. Element IDs — stable unique IDs the harness relies on.
4. Episode log schema — the Postgres table analysis reads.
5. Judge rubric — CCPA-grounded prompt text for non-deterministic patterns.
Never change a contract silently — PR + a heads-up.

## Status right now
Phase 0. The spike is built and the deterministic oracle is VERIFIED
(harness/verify_page.py prints PASS). Test spec legal definitions are being
filled from the Gazette. Testbed/harness/auditor not built yet.

## How we work
main is protected. Branch -> push -> pull request -> the other reviews -> merge.
Nobody pushes straight to main. Weekly 30-min sync: what ran, what's blocked,
did any contract change. Every non-obvious decision gets one line in
docs/decisions.md.

## Setup (per person, after cloning)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r harness\requirements.txt
    python -m playwright install chromium
    python harness\verify_page.py      # should print PASS
Copy .env.example to .env for your API key (never commit .env).

## Where to read more (docs/)
- Blueprint, execution guide (8 phases with gates)
- CCPA-13 test spec (ChhalBench_TestSpec.xlsx)
- Taxonomy crosswalk (vs SusBench, Ersoy, Tang)
- Detailed build spec + architecture diagram