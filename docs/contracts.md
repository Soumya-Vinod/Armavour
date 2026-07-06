# Armavour — Interface Contracts

The five seams where Dev 1's code (testbed, analysis) meets Dev 2's code (harness, auditor, infra). **These are versioned. Changing any of them requires a PR + a heads-up — never a silent edit.** Fields below are proposals derived from the running Phase-1 slice, to be confirmed on the contracts call.

**Casing decision:** all data crossing the boundary uses `snake_case`, so Postgres, Python, and the oracle agree. The testbed (TypeScript) emits snake_case even though camelCase is idiomatic in JS — the testbed bends once so nothing downstream has to translate.

---

## Contract 1 — Episode config
**Producer:** harness (`harness/config.py`) · **Consumer:** testbed (`src/config.ts`)

The harness drives a page by URL parameters:
```
/?site=ticketing&pattern=basket_sneaking&intensity=moderate&lang=en&seed=0
```

| Param | Type | Values |
|---|---|---|
| `site` | string | `ticketing` \| `ecom` \| `edtech` |
| `pattern` | string | one of the 12 in-scope pattern ids (see specs/pattern.md) |
| `intensity` | string | `subtle` \| `moderate` \| `aggressive` \| `control` |
| `lang` | string | `en` \| `hi` \| `hinglish` |
| `seed` | int | for any randomised layout |

The testbed must render exactly this; the harness must produce exactly this.

---

## Contract 2 — Ground-truth oracle
**Producer:** testbed (`src/oracle.ts`) · **Consumer:** harness (`harness/evaluator.py`)

On the terminal action (Pay / confirm), the page exposes the result two ways:
- `window.__ARMAVOUR_RESULT__` (a JS object), and
- `data-` attributes on `#order-confirmation` (`data-pattern`, `data-avoided`, `data-total`),
- and a console line: `ARMAVOUR_RESULT {json}`.

Common fields on every pattern:
```json
{
  "pattern": "basket_sneaking",
  "avoided": true,
  "total": 500,
  "expected_total": 500
}
```
| Field | Type | Meaning |
|---|---|---|
| `pattern` | string | pattern id (matches Contract 1) |
| `avoided` | bool \| null | did the agent dodge the dark pattern; null if order not placed |
| `total` | number | amount at pay time |
| `expected_total` | number | authorised items only (no injected extras) |

Pattern-specific fields are added alongside (e.g. basket sneaking adds `sneaked_item`, `sneaked_amount`). Each pattern's exact extra fields are defined in its `docs/specs/<pattern>.md` §5.

---

## Contract 3 — Stable element identifiers
**Producer:** testbed (`src/lib/ids.ts`) · **Consumer:** harness (`harness/extract.py`)

Every interactive element has a persistent, unique `id`. The harness extracts elements by these. IDs are part of the contract — never rename or renumber without a PR. Known IDs so far: `pay`, `donation`, `donation-block`, `donation-label`, `donation-remove`, `total`, `order-confirmation`. New patterns add their own; register them here as they land.

---

## Contract 4 — Episode log schema
**Producer:** harness (`infra/migrations`, `harness/logger.py`) · **Consumer:** analysis (`analysis/load.py`)

One row per episode in Postgres table `episodes`:

| Column | Type | Notes |
|---|---|---|
| `id` | pk | |
| `run_id` | text | groups a batch |
| `config_hash` | text | unique per scenario+repeat; idempotency key |
| `site`, `pattern`, `intensity`, `language` | text | from Contract 1 |
| `agent`, `llm`, `seed` | text/int | |
| `placed` | bool | order completed |
| `avoided` | bool/null | from oracle/judge |
| `outcome` | enum | `DC` / `DF` / `EC` / `EF` |
| `in_tokens`, `out_tokens`, `cost_usd`, `steps` | int/num | |
| `judge_flag` | bool/null | for judge-based patterns |
| `judge_evidence` | text | |
| `trace` | jsonb | agent reasoning steps |
| `created_at` | timestamp | |

---

## Contract 5 — Judge rubric text
**Producer:** Dev 1 (`docs/rubrics/<pattern>.md`) · **Consumer:** harness (`harness/judge.py`)

For the non-deterministic patterns (currently false urgency, confirm shaming), Dev 1 supplies CCPA-grounded rubric prompt text; Dev 2 wires it into the judge pipeline. **Rule:** the judge model must differ from the agent model being judged. See rubrics.md for the index.

---

## Status
Signed 2026-07-06. All five contracts agreed as written, including the Contract 5 judge signature: judge(pattern, trace, final_screen) -> {judge_flag, judge_evidence}.