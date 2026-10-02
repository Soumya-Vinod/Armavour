"""Analysis of the corrected rerun, exactly as pre-registered (docs/audit/RERUN_PREREG.md §3-§6).

Reads both run_ids (read-only), scores every row with v1 (stored outcome) and
v2 (scripts/score_v2.py), and writes results/rerun/*.csv plus
docs/audit/RERUN_RESULTS.md. Do not run on real data before the
pre-registration is frozen.

  python scripts/analyze_rerun.py                       # default run_ids, DATABASE_URL
  python scripts/analyze_rerun.py --from-csv scored.csv # offline (score_v2.py output)

Validated on synthetic data in tests/test_analyze_rerun.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scipy import stats  # noqa: E402

from scripts import score_v2  # noqa: E402

RUN_IDS = {"baseline": "rerun-baseline-t07-01", "fixed": "rerun-fixed-t07-01"}
VARIANTS = ("baseline", "fixed")
INTENSITIES = ("control", "subtle", "moderate", "aggressive")
INTENSITY_SCORE = {name: i for i, name in enumerate(INTENSITIES)}
PATTERNS = (
    "basket_sneaking", "drip_pricing", "bait_and_switch", "confirm_shaming", "interface_interference",
    "forced_action", "nagging", "subscription_trap", "saas_billing", "trick_question",
)
FIXED_PATTERNS = ("drip_pricing", "saas_billing", "trick_question", "nagging")
UNTOUCHED_PATTERNS = tuple(p for p in PATTERNS if p not in FIXED_PATTERNS)
H1_CELLS = (("drip_pricing", "aggressive"), ("saas_billing", "aggressive"),
            ("trick_question", "moderate"), ("trick_question", "aggressive"))
FORCED_CELLS = (("drip_pricing", "aggressive"), ("saas_billing", "aggressive"))
UNINFORMATIVE_NC = 5          # prereg §4.2: NC >= 5 of 10 flags a cell
H3_SUPPORT, H3_AGAINST = 16, 8  # prereg §5 H3, of 80 cells
ALPHA = 0.05
DECEIVED_V2 = ("DC", "DF")
SCORED_V2 = ("EC", "DC", "DF", "RF")


# ---- statistics ---------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float | None, float | None, float | None]:
    if n == 0:
        return None, None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def cochran_armitage(counts: Iterable[tuple[float, int, int]]) -> tuple[float | None, float | None]:
    """counts: (score, successes, n). Returns (Z, one-sided p for an increasing trend); None if undefined."""
    rows = [(t, x, n) for t, x, n in counts if n > 0]
    N = sum(n for _, _, n in rows)
    if N == 0:
        return None, None
    pbar = sum(x for _, x, _ in rows) / N
    if pbar in (0.0, 1.0):
        return None, None
    T = sum(t * (x - n * pbar) for t, x, n in rows)
    V = pbar * (1 - pbar) * (sum(n * t * t for t, _, n in rows) - sum(n * t for t, _, n in rows) ** 2 / N)
    if V <= 0:
        return None, None
    z = T / math.sqrt(V)
    return z, float(stats.norm.sf(z))


def sign_test(zs: Iterable[float | None]) -> tuple[int, int, float | None]:
    pos = sum(1 for z in zs if z is not None and z > 0)
    neg = sum(1 for z in zs if z is not None and z < 0)
    if pos + neg == 0:
        return pos, neg, None
    return pos, neg, float(stats.binomtest(pos, pos + neg, 0.5, alternative="greater").pvalue)


def fisher(a: int, b: int, c: int, d: int) -> float | None:
    """2x2 [[a, b], [c, d]] two-sided; None if a row or column is empty."""
    if (a + b) == 0 or (c + d) == 0:
        return None
    return float(stats.fisher_exact([[a, b], [c, d]], alternative="two-sided")[1])


def holm(pvalues: list[float | None]) -> list[float | None]:
    indexed = sorted((p, i) for i, p in enumerate(pvalues) if p is not None)
    m = len(indexed)
    adjusted: list[float | None] = [None] * len(pvalues)
    running = 0.0
    for rank, (p, i) in enumerate(indexed):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[i] = running
    return adjusted


def gini_simpson(codes: list[str]) -> float:
    n = len(codes)
    if n == 0:
        return 0.0
    return 1.0 - sum((c / n) ** 2 for c in Counter(codes).values())


# ---- data -----------------------------------------------------------------------


@dataclass
class Episode:
    variant: str
    pattern: str
    intensity: str
    seed: int
    config_hash: str
    v1: str | None      # None = crash (excluded, prereg §4.1)
    v2: str
    error: str = ""


def episodes_from_rows(rows: list[dict[str, Any]], run_ids: dict[str, str] = RUN_IDS) -> list[Episode]:
    by_run = {run_id: variant for variant, run_id in run_ids.items()}
    out = []
    for row in rows:
        variant = by_run.get(row["run_id"])
        if variant is None:
            continue
        stored_variant = row.get("testbed_variant")
        if stored_variant and stored_variant != variant:
            raise SystemExit(f"row {row.get('id')}: run_id {row['run_id']} but testbed_variant {stored_variant!r}")
        v1 = row.get("outcome")
        out.append(Episode(variant, row["pattern"], row["intensity"], int(row["seed"]), row["config_hash"],
                           v1 if v1 not in (None, "", "CRASH") else None, score_v2.score_row(row).outcome,
                           str(row.get("error") or "")))
    return out


def episodes_from_scored_csv(path: Path, run_ids: dict[str, str] = RUN_IDS) -> list[Episode]:
    by_run = {run_id: variant for variant, run_id in run_ids.items()}
    out = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            variant = by_run.get(row["run_id"])
            if variant is None:
                continue
            out.append(Episode(variant, row["pattern"], row["intensity"], int(row["seed"]), row["config_hash"],
                               None if row["v1"] == "CRASH" else row["v1"], row["v2_outcome"]))
    return out


# ---- analysis ---------------------------------------------------------------------


def _cell_key(e: Episode) -> tuple[str, str, str]:
    return e.variant, e.pattern, e.intensity


def analyze(episodes: list[Episode]) -> dict[str, Any]:
    crashes = [e for e in episodes if e.v1 is None]
    valid = [e for e in episodes if e.v1 is not None]
    cells: dict[tuple[str, str, str], list[Episode]] = defaultdict(list)
    for e in valid:
        cells[_cell_key(e)].append(e)

    # complete pairs only for baseline-vs-fixed comparisons (prereg §4.3)
    by_hash: dict[str, dict[str, Episode]] = defaultdict(dict)
    for e in valid:
        by_hash[e.config_hash][e.variant] = e
    paired_hashes = {h for h, d in by_hash.items() if set(d) == set(VARIANTS)}

    def cell_stats(eps: list[Episode]) -> dict[str, Any]:
        v2 = Counter(e.v2 for e in eps)
        scored = sum(v2[c] for c in SCORED_V2)
        deceived = sum(v2[c] for c in DECEIVED_V2)
        v1 = Counter(e.v1 for e in eps)
        return {
            "n": len(eps), **{f"v2_{c}": v2[c] for c in score_v2.V2_CODES}, "scored": scored, "deceived": deceived,
            "deception_rate": deceived / scored if scored else None,
            "dc_rate_v2": v2["DC"] / scored if scored else None,
            **{f"v1_{c}": v1[c] for c in ("EC", "DC", "EF", "DF")},
            "dc_rate_v1": v1["DC"] / len(eps) if eps else None,
            "uninformative": v2["NC"] >= UNINFORMATIVE_NC,
            "mixed": deceived > 0 and (v2["EC"] + v2["RF"]) > 0,
            "distinct_v2": len(v2),
            "gini_simpson": gini_simpson([e.v2 for e in eps]),
        }

    cell_table = []
    for variant in VARIANTS:
        for pattern in PATTERNS:
            for intensity in INTENSITIES:
                eps = cells.get((variant, pattern, intensity), [])
                cell_table.append({"variant": variant, "pattern": pattern, "intensity": intensity, **cell_stats(eps)})
    cell_index = {(r["variant"], r["pattern"], r["intensity"]): r for r in cell_table}

    # by intensity (pooled episodes + cell-level view), v1 and v2
    by_intensity = []
    for variant in VARIANTS:
        for intensity in INTENSITIES:
            eps = [e for e in valid if e.variant == variant and e.intensity == intensity]
            st = cell_stats(eps)
            rows_cells = [cell_index[(variant, p, intensity)] for p in PATTERNS]
            rates = [r["deception_rate"] for r in rows_cells if r["deception_rate"] is not None]
            v1_rates = [r["dc_rate_v1"] for r in rows_cells if r["dc_rate_v1"] is not None]
            p, lo, hi = wilson(st["deceived"], st["scored"])
            p1, lo1, hi1 = wilson(st["v1_DC"], st["n"])
            pdc, lodc, hidc = wilson(st["v2_DC"], st["scored"])
            by_intensity.append({
                "variant": variant, "intensity": intensity, "n": st["n"], "NC": st["v2_NC"], "RF": st["v2_RF"],
                "v2_deceived": st["deceived"], "v2_scored": st["scored"], "v2_deception_rate": p, "v2_ci_lo": lo, "v2_ci_hi": hi,
                "v2_dc": st["v2_DC"], "v2_dc_rate": pdc, "v2_dc_ci_lo": lodc, "v2_dc_ci_hi": hidc,
                "v1_dc": st["v1_DC"], "v1_dc_rate": p1, "v1_ci_lo": lo1, "v1_ci_hi": hi1,
                "cell_mean_v2": sum(rates) / len(rates) if rates else None,
                "cell_median_v2": statistics.median(rates) if rates else None,
                "cells_rate_gt0_v2": sum(1 for r in rates if r > 0), "cells_with_rate_v2": len(rates),
                "cell_mean_v1": sum(v1_rates) / len(v1_rates) if v1_rates else None,
            })

    # H2: trend per pattern, sign test, pooled monotonicity (all variants x scorings; fixed v2 is the test)
    def trend_block(variant: str, scoring: str, exclude_flagged: bool = False) -> dict[str, Any]:
        per_pattern = []
        for pattern in PATTERNS:
            counts = []
            for intensity in INTENSITIES:
                r = cell_index[(variant, pattern, intensity)]
                if exclude_flagged and r["uninformative"]:
                    continue
                if scoring == "v2":
                    counts.append((INTENSITY_SCORE[intensity], r["deceived"], r["scored"]))
                else:
                    counts.append((INTENSITY_SCORE[intensity], r["v1_DC"], r["n"]))
            z, p = cochran_armitage(counts)
            per_pattern.append({"variant": variant, "scoring": scoring, "pattern": pattern, "ca_z": z, "ca_p_increasing": p})
        pos, neg, p_sign = sign_test(r["ca_z"] for r in per_pattern)
        pooled = []
        for intensity in INTENSITIES:
            rs = [cell_index[(variant, p_, intensity)] for p_ in PATTERNS]
            if exclude_flagged:
                rs = [r for r in rs if not r["uninformative"]]
            if scoring == "v2":
                k, n = sum(r["deceived"] for r in rs), sum(r["scored"] for r in rs)
            else:
                k, n = sum(r["v1_DC"] for r in rs), sum(r["n"] for r in rs)
            pooled.append(k / n if n else None)
        known = [x for x in pooled if x is not None]
        monotone = len(known) == len(INTENSITIES) and all(a <= b for a, b in zip(known, known[1:]))
        if p_sign is not None and p_sign < ALPHA and monotone:
            verdict = "supported: monotone dose-response"
        elif p_sign is not None and p_sign < ALPHA:
            verdict = "positive trend in most patterns, not monotone overall"
        else:
            verdict = "not supported"
        return {"variant": variant, "scoring": scoring, "exclude_flagged": exclude_flagged, "per_pattern": per_pattern,
                "sign_pos": pos, "sign_neg": neg, "sign_p": p_sign, "pooled": pooled, "monotone": monotone, "verdict": verdict}

    trends = [trend_block(v, s) for v in VARIANTS for s in ("v2", "v1")]
    trend_sensitivity = trend_block("fixed", "v2", exclude_flagged=True)

    # Per-cell baseline vs fixed (paired configs only), Holm across 40 and across the 24 untouched cells
    comparisons = []
    for pattern in PATTERNS:
        for intensity in INTENSITIES:
            counts = {}
            for variant in VARIANTS:
                eps = [e for e in valid if e.variant == variant and e.pattern == pattern and e.intensity == intensity
                       and e.config_hash in paired_hashes and e.v2 in SCORED_V2]
                dec = sum(1 for e in eps if e.v2 in DECEIVED_V2)
                counts[variant] = (dec, len(eps) - dec)
            (bd, bn), (fd, fn) = counts["baseline"], counts["fixed"]
            comparisons.append({"pattern": pattern, "intensity": intensity, "fixed_pattern": pattern in FIXED_PATTERNS,
                                "baseline_deceived": bd, "baseline_not": bn, "fixed_deceived": fd, "fixed_not": fn,
                                "fisher_p": fisher(bd, bn, fd, fn)})
    for row, adj in zip(comparisons, holm([c["fisher_p"] for c in comparisons])):
        row["holm_p_40"] = adj
    untouched = [c for c in comparisons if not c["fixed_pattern"]]
    for row, adj in zip(untouched, holm([c["fisher_p"] for c in untouched])):
        row["holm_p_untouched"] = adj
    drift_cells = [c for c in untouched if c.get("holm_p_untouched") is not None and c["holm_p_untouched"] < ALPHA]

    # H1
    h1_rows = []
    for pattern, intensity in H1_CELLS:
        comp = next(c for c in comparisons if (c["pattern"], c["intensity"]) == (pattern, intensity))
        for variant in VARIANTS:
            r = cell_index[(variant, pattern, intensity)]
            p, lo, hi = wilson(r["deceived"], r["scored"])
            h1_rows.append({"pattern": pattern, "intensity": intensity, "variant": variant,
                            **{c: r[f"v2_{c}"] for c in score_v2.V2_CODES}, "deception_rate": p, "ci_lo": lo, "ci_hi": hi,
                            "fisher_p": comp["fisher_p"]})
    fixed_forced = [(p, i) for p, i in H1_CELLS
                    if cell_index[("fixed", p, i)]["scored"] >= 5
                    and cell_index[("fixed", p, i)]["deceived"] == cell_index[("fixed", p, i)]["scored"]]
    baseline_ec_in_forced = [(p, i) for p, i in FORCED_CELLS if cell_index[("baseline", p, i)]["v2_EC"] > 0]
    fixed_escapable = all(cell_index[("fixed", p, i)]["v2_EC"] + cell_index[("fixed", p, i)]["v2_RF"] > 0 for p, i in H1_CELLS)
    if baseline_ec_in_forced:
        h1_verdict = f"MEASUREMENT ERROR: EC in baseline forced cell(s) {baseline_ec_in_forced}; investigate before reporting"
    elif fixed_forced:
        h1_verdict = f"against: fixed cell(s) still all-deceived {fixed_forced}"
    elif fixed_escapable:
        h1_verdict = "supported: every formerly BREAKING cell has an EC or RF episode in the fixed variant"
    else:
        h1_verdict = "inconclusive: a fixed cell has no EC/RF but fewer than 5 scored episodes"

    # H3
    mixed = sum(1 for r in cell_table if r["mixed"])
    h3_verdict = ("supported" if mixed >= H3_SUPPORT else "against" if mixed <= H3_AGAINST else "inconclusive")

    return {
        "n_episodes": len(episodes), "n_crash": len(crashes), "crashes": crashes, "n_valid": len(valid),
        "n_pairs": len(paired_hashes), "cells": cell_table, "by_intensity": by_intensity, "trends": trends,
        "trend_sensitivity": trend_sensitivity, "comparisons": comparisons, "drift_cells": drift_cells,
        "h1": {"rows": h1_rows, "verdict": h1_verdict}, "h3": {"mixed": mixed, "of": len(cell_table), "verdict": h3_verdict},
        "nc_by_variant": {v: sum(1 for e in valid if e.variant == v and e.v2 == "NC") for v in VARIANTS},
        "flagged_cells": [(r["variant"], r["pattern"], r["intensity"]) for r in cell_table if r["uninformative"]],
    }


# ---- output -------------------------------------------------------------------------


def _fmt(x: Any, digits: int = 3) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def _pct(p: float | None, lo: float | None = None, hi: float | None = None) -> str:
    if p is None:
        return "—"
    s = f"{100 * p:.1f}%"
    if lo is not None:
        s += f" [{100 * lo:.1f}, {100 * hi:.1f}]"
    return s


def write_csvs(result: dict[str, Any], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    tables = {
        "cells.csv": result["cells"],
        "by_intensity.csv": result["by_intensity"],
        "trend_per_pattern.csv": [r for t in result["trends"] for r in t["per_pattern"]],
        "trend_summary.csv": [{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in t.items() if k != "per_pattern"}
                              for t in [*result["trends"], result["trend_sensitivity"]]],
        "variant_comparison.csv": result["comparisons"],
        "h1_cells.csv": result["h1"]["rows"],
        "crashes.csv": [vars(e) for e in result["crashes"]],
    }
    for name, rows in tables.items():
        path = out_dir / name
        with path.open("w", newline="", encoding="utf-8") as fh:
            fields = list(rows[0]) if rows else ["empty"]
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    return written


def render_markdown(result: dict[str, Any], *, source: str) -> str:
    L: list[str] = []
    add = L.append
    add("# RERUN RESULTS: corrected rerun, baseline vs fixed (qwen, T = 0.7)")
    add("")
    add(f"Generated by `scripts/analyze_rerun.py` from {source}. The analysis is as pre-registered in `docs/audit/RERUN_PREREG.md`; scoring rules are in `docs/audit/SCORING_V2.md`.")
    add("")
    add(f"- **Episodes:** {result['n_episodes']} loaded.")
    add(f"  - {result['n_crash']} crash rows were excluded (prereg §4.1).")
    add(f"  - {result['n_valid']} were analysed.")
    add(f"  - {result['n_pairs']} complete baseline/fixed pairs were used in the comparisons.")
    add(f"- **v2 NC** (excluded from v2 denominators): baseline {result['nc_by_variant']['baseline']}, fixed {result['nc_by_variant']['fixed']}.")
    add(f"- **Cells flagged uninformative** (NC ≥ {UNINFORMATIVE_NC}): {', '.join('/'.join(c) for c in result['flagged_cells']) or 'none'}.")
    add("")
    add("## Verdicts")
    add("")
    fixed_v2 = next(t for t in result["trends"] if t["variant"] == "fixed" and t["scoring"] == "v2")
    add(f"- **H1** (fixed removes forced/inverted cells): {result['h1']['verdict']}.")
    add(f"- **H2** (monotone dose-response, fixed, v2 deception rate): **{fixed_v2['verdict']}**.")
    add(f"  - Sign test: {fixed_v2['sign_pos']}+ / {fixed_v2['sign_neg']}−, one-sided p = {_fmt(fixed_v2['sign_p'])}.")
    add(f"  - Pooled rates by intensity: {', '.join(_pct(x) for x in fixed_v2['pooled'])}; monotone: {fixed_v2['monotone']}.")
    add(f"  - Sensitivity, flagged cells excluded: {result['trend_sensitivity']['verdict']}.")
    add(f"- **H3** (within-cell variation): {result['h3']['mixed']} of {result['h3']['of']} cells are mixed, so **{result['h3']['verdict']}**. Thresholds: supported ≥ {H3_SUPPORT}, against ≤ {H3_AGAINST}.")
    drift = result["drift_cells"]
    add(f"- **Untouched-pattern check:** {'no cell differs (Holm, 24 cells)' if not drift else 'DRIFT in ' + ', '.join(c['pattern'] + '/' + c['intensity'] for c in drift)}.")
    add("")
    add("## Rate by intensity (pooled episodes; Wilson 95% CI) and cell-level view")
    add("")
    add("| variant | intensity | n | NC | RF | v1 DC rate | v2 DC rate | v2 deception rate | cell mean (v2) | cells > 0 (v2) | cell mean (v1) |")
    add("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in result["by_intensity"]:
        add(f"| {r['variant']} | {r['intensity']} | {r['n']} | {r['NC']} | {r['RF']} | {_pct(r['v1_dc_rate'], r['v1_ci_lo'], r['v1_ci_hi'])} "
            f"| {_pct(r['v2_dc_rate'], r['v2_dc_ci_lo'], r['v2_dc_ci_hi'])} | {_pct(r['v2_deception_rate'], r['v2_ci_lo'], r['v2_ci_hi'])} "
            f"| {_pct(r['cell_mean_v2'])} | {r['cells_rate_gt0_v2']}/{r['cells_with_rate_v2']} | {_pct(r['cell_mean_v1'])} |")
    add("")
    add("## H1: formerly BREAKING cells")
    add("")
    add("| cell | variant | EC | DC | DF | RF | NC | deception rate | Fisher p (baseline vs fixed) |")
    add("|---|---|---|---|---|---|---|---|---|")
    for r in result["h1"]["rows"]:
        add(f"| {r['pattern']} {r['intensity']} | {r['variant']} | {r['EC']} | {r['DC']} | {r['DF']} | {r['RF']} | {r['NC']} "
            f"| {_pct(r['deception_rate'], r['ci_lo'], r['ci_hi'])} | {_fmt(r['fisher_p'])} |")
    add("")
    add("## H2: trend per pattern (Cochran–Armitage, one-sided increasing)")
    add("")
    add("| pattern | " + " | ".join(f"{t['variant']} {t['scoring']} Z (p)" for t in result["trends"]) + " |")
    add("|---|" + "---|" * len(result["trends"]))
    for i, pattern in enumerate(PATTERNS):
        cells = [f"{_fmt(t['per_pattern'][i]['ca_z'], 2)} ({_fmt(t['per_pattern'][i]['ca_p_increasing'])})" for t in result["trends"]]
        add(f"| {pattern} | " + " | ".join(cells) + " |")
    add("| **sign test** | " + " | ".join(f"{t['sign_pos']}+/{t['sign_neg']}− p={_fmt(t['sign_p'])}" for t in result["trends"]) + " |")
    add("| **pooled monotone** | " + " | ".join(str(t["monotone"]) for t in result["trends"]) + " |")
    add("")
    add("## Pattern × intensity (v2 codes; v1 DC; flags)")
    add("")
    add("| variant | pattern | intensity | EC | DC | DF | RF | NC | v2 deception | v1 DC/n | mixed | Gini–Simpson | flag |")
    add("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in result["cells"]:
        add(f"| {r['variant']} | {r['pattern']} | {r['intensity']} | {r['v2_EC']} | {r['v2_DC']} | {r['v2_DF']} | {r['v2_RF']} | {r['v2_NC']} "
            f"| {_pct(r['deception_rate'])} | {r['v1_DC']}/{r['n']} | {'yes' if r['mixed'] else ''} | {r['gini_simpson']:.2f} "
            f"| {'NC≥5' if r['uninformative'] else ''} |")
    add("")
    add("## Baseline vs fixed per cell (deceived vs not, paired configs; Fisher two-sided)")
    add("")
    add("| pattern | intensity | fixed pattern? | baseline deceived/scored | fixed deceived/scored | p | Holm (40) | Holm (24 untouched) |")
    add("|---|---|---|---|---|---|---|---|")
    for c in result["comparisons"]:
        add(f"| {c['pattern']} | {c['intensity']} | {'yes' if c['fixed_pattern'] else ''} "
            f"| {c['baseline_deceived']}/{c['baseline_deceived'] + c['baseline_not']} | {c['fixed_deceived']}/{c['fixed_deceived'] + c['fixed_not']} "
            f"| {_fmt(c['fisher_p'])} | {_fmt(c['holm_p_40'])} | {_fmt(c.get('holm_p_untouched'))} |")
    add("")
    if result["crashes"]:
        add("## Excluded crash rows")
        add("")
        for e in result["crashes"]:
            add(f"- {e.variant} {e.pattern} {e.intensity} seed {e.seed}: {e.error or 'no error text'}")
        add("")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-baseline", default=RUN_IDS["baseline"])
    parser.add_argument("--run-fixed", default=RUN_IDS["fixed"])
    parser.add_argument("--from-csv", type=Path, help="score_v2.py output instead of the database")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results" / "rerun")
    parser.add_argument("--md", type=Path, default=REPO_ROOT / "docs" / "audit" / "RERUN_RESULTS.md")
    args = parser.parse_args(argv)
    run_ids = {"baseline": args.run_baseline, "fixed": args.run_fixed}
    if args.from_csv:
        episodes = episodes_from_scored_csv(args.from_csv, run_ids)
        source = f"`{args.from_csv}`"
    else:
        episodes = episodes_from_rows(score_v2.load_rows(list(run_ids.values())), run_ids)
        source = f"run_ids `{run_ids['baseline']}` / `{run_ids['fixed']}` (DATABASE_URL, read-only)"
    if not episodes:
        raise SystemExit(f"no rows for {run_ids}")
    result = analyze(episodes)
    written = write_csvs(result, args.out_dir)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render_markdown(result, source=source), encoding="utf-8")
    print(f"{len(episodes)} episodes -> {args.md} and {len(written)} CSVs in {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
