"""Synthetic-data validation of scripts/analyze_rerun.py (pre-registered analysis)."""
from __future__ import annotations

import csv
import math
import random
from pathlib import Path

import pytest

from scripts import analyze_rerun as ar
from scripts.analyze_rerun import INTENSITIES, PATTERNS, VARIANTS, Episode

V1_OF_V2 = {"EC": "EC", "DC": "DC", "DF": "DC", "RF": "EC", "NC": "EF"}


def make(spec, *, seeds: int = 10, crash: set | None = None, drop: set | None = None) -> list[Episode]:
    """spec(variant, pattern, intensity, seed) -> v2 code; crash/drop are sets of (variant, pattern, intensity, seed)."""
    crash, drop = crash or set(), drop or set()
    eps = []
    for variant in VARIANTS:
        for pattern in PATTERNS:
            for intensity in INTENSITIES:
                for seed in range(seeds):
                    key = (variant, pattern, intensity, seed)
                    if key in drop:
                        continue
                    code = spec(*key)
                    v1 = None if key in crash else V1_OF_V2[code]
                    eps.append(Episode(variant, pattern, intensity, seed, f"{pattern}-{intensity}-{seed}", v1, code,
                                       "boom" if key in crash else ""))
    return eps


def dose(rates: dict[str, float]):
    """Deceived on the first round(rate*10) seeds of every cell, EC otherwise."""
    return lambda v, p, i, s: "DC" if s < round(rates[i] * 10) else "EC"


INCREASING = {"control": 0.0, "subtle": 0.2, "moderate": 0.4, "aggressive": 0.7}
FLAT = {i: 0.3 for i in INTENSITIES}


# ---- statistics -----------------------------------------------------------------


def test_wilson_known_values() -> None:
    p, lo, hi = ar.wilson(0, 10)
    assert p == 0 and lo == 0 and hi == pytest.approx(0.2775, abs=1e-4)
    p, lo, hi = ar.wilson(5, 10)
    assert (lo, hi) == (pytest.approx(0.2366, abs=1e-4), pytest.approx(0.7634, abs=1e-4))
    assert ar.wilson(0, 0) == (None, None, None)


def test_cochran_armitage_equals_n_r_squared() -> None:
    # CA chi-square = N * r^2, r = Pearson correlation of score and outcome over individuals.
    rng = random.Random(1)
    counts, xs, ys = [], [], []
    for t in range(4):
        n = 10 + t
        k = rng.randint(0, n)
        counts.append((t, k, n))
        xs += [t] * n
        ys += [1] * k + [0] * (n - k)
    N = len(xs)
    mx, my = sum(xs) / N, sum(ys) / N
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    r = cov / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    z, p = ar.cochran_armitage(counts)
    assert z ** 2 == pytest.approx(N * r * r)
    assert (z > 0) == (r > 0)
    assert 0 < p < 1


def test_cochran_armitage_undefined_cases() -> None:
    assert ar.cochran_armitage([(t, 0, 10) for t in range(4)]) == (None, None)
    assert ar.cochran_armitage([(t, 10, 10) for t in range(4)]) == (None, None)
    assert ar.cochran_armitage([]) == (None, None)


def test_sign_test_and_holm_and_fisher() -> None:
    pos, neg, p = ar.sign_test([1.0] * 9 + [-1.0, None])
    assert (pos, neg) == (9, 1) and p == pytest.approx(11 / 1024)
    assert ar.sign_test([None, None]) == (0, 0, None)
    assert ar.holm([0.01, 0.04, None, 0.03]) == [pytest.approx(0.03), pytest.approx(0.06), None, pytest.approx(0.06)]
    assert ar.fisher(10, 0, 0, 10) == pytest.approx(1.0825e-5, rel=1e-3)
    assert ar.fisher(0, 0, 3, 4) is None


def test_gini_simpson() -> None:
    assert ar.gini_simpson(["EC"] * 10) == 0
    assert ar.gini_simpson(["EC", "DC"] * 5) == pytest.approx(0.5)


# ---- H2 -----------------------------------------------------------------------------


def _trend(result, variant="fixed", scoring="v2"):
    return next(t for t in result["trends"] if t["variant"] == variant and t["scoring"] == scoring)


def test_h2_supported_on_monotone_synthetic_data() -> None:
    result = ar.analyze(make(dose(INCREASING)))
    t = _trend(result)
    assert t["verdict"] == "supported: monotone dose-response"
    assert (t["sign_pos"], t["sign_neg"]) == (10, 0) and t["sign_p"] == pytest.approx(1 / 1024)
    assert t["pooled"] == pytest.approx([0.0, 0.2, 0.4, 0.7])


def test_h2_not_supported_when_flat() -> None:
    t = _trend(ar.analyze(make(dose(FLAT))))
    assert (t["sign_pos"], t["sign_neg"]) == (0, 0)
    assert t["monotone"] is True  # flat is non-decreasing ...
    assert t["verdict"] == "not supported"  # ... but the sign test has no positive trends


def test_h2_trend_but_not_monotone() -> None:
    # Every pattern trends up, but the pooled rate dips at moderate.
    rates = {"control": 0.0, "subtle": 0.5, "moderate": 0.4, "aggressive": 0.9}
    t = _trend(ar.analyze(make(dose(rates))))
    assert t["sign_p"] < 0.05 and t["monotone"] is False
    assert t["verdict"] == "positive trend in most patterns, not monotone overall"


# ---- H3 -----------------------------------------------------------------------------


def test_h3_against_when_seeds_identical() -> None:
    spec = lambda v, p, i, s: "DC" if i == "aggressive" else "EC"  # noqa: E731
    result = ar.analyze(make(spec))
    assert result["h3"]["mixed"] == 0 and result["h3"]["verdict"] == "against"


def test_h3_supported_when_cells_mixed() -> None:
    result = ar.analyze(make(dose(INCREASING)))
    # subtle/moderate/aggressive cells are mixed in both variants: 3 x 10 x 2 = 60 of 80
    assert result["h3"]["mixed"] == 60 and result["h3"]["verdict"] == "supported"


def test_h3_inconclusive_band() -> None:
    mixed_cells = {(p, "aggressive") for p in PATTERNS[:6]}  # 6 cells x 2 variants = 12 mixed
    spec = lambda v, p, i, s: ("DC" if s < 5 else "EC") if (p, i) in mixed_cells else "EC"  # noqa: E731
    assert ar.analyze(make(spec))["h3"] == {"mixed": 12, "of": 80, "verdict": "inconclusive"}


# ---- H1 -----------------------------------------------------------------------------


def _h1_spec(baseline_forced_ec: bool = False, fixed_still_forced: bool = False):
    def spec(v, p, i, s):
        if (p, i) in ar.H1_CELLS:
            if v == "baseline":
                if baseline_forced_ec and (p, i) == ("drip_pricing", "aggressive") and s == 0:
                    return "EC"
                return "DC" if s < 8 else ("NC" if (p, i) in ar.FORCED_CELLS else "EC")
            if fixed_still_forced and (p, i) == ("saas_billing", "aggressive"):
                return "DC"
            return "DC" if s < 3 else ("RF" if s < 6 else "EC")
        return "EC"
    return spec


def test_h1_supported() -> None:
    result = ar.analyze(make(_h1_spec()))
    assert result["h1"]["verdict"].startswith("supported")
    row = next(r for r in result["h1"]["rows"] if r["pattern"] == "saas_billing" and r["variant"] == "baseline")
    assert (row["DC"], row["NC"], row["deception_rate"]) == (8, 2, 1.0)  # NC excluded from the denominator
    assert row["fisher_p"] is not None and row["fisher_p"] < 0.05


def test_h1_against_when_fixed_cell_still_all_deceived() -> None:
    assert ar.analyze(make(_h1_spec(fixed_still_forced=True)))["h1"]["verdict"].startswith("against")


def test_h1_flags_measurement_error_on_ec_in_baseline_forced_cell() -> None:
    assert ar.analyze(make(_h1_spec(baseline_forced_ec=True)))["h1"]["verdict"].startswith("MEASUREMENT ERROR")


# ---- exclusions, pairing, drift ---------------------------------------------------------


def test_crashes_excluded_and_listed_nc_flagged() -> None:
    crash = {("fixed", "nagging", "aggressive", s) for s in range(3)}

    def spec(v, p, i, s):
        if (v, p, i) == ("fixed", "nagging", "aggressive"):
            return "NC" if s < 8 else "EC"
        return "EC"

    result = ar.analyze(make(spec, crash=crash))
    assert result["n_crash"] == 3 and result["n_valid"] == 797
    cell = next(r for r in result["cells"] if (r["variant"], r["pattern"], r["intensity"]) == ("fixed", "nagging", "aggressive"))
    assert cell["n"] == 7 and cell["v2_NC"] == 5 and cell["scored"] == 2 and cell["uninformative"] is True
    assert ("fixed", "nagging", "aggressive") in result["flagged_cells"]
    # v1 still counts NC rows (as EF) in its denominator
    assert cell["v1_EF"] == 5 and cell["dc_rate_v1"] == 0.0


def test_comparisons_use_complete_pairs_only() -> None:
    drop = {("fixed", "bait_and_switch", "aggressive", s) for s in range(4)}
    spec = lambda v, p, i, s: "DC" if (p, i) == ("bait_and_switch", "aggressive") else "EC"  # noqa: E731
    result = ar.analyze(make(spec, drop=drop))
    comp = next(c for c in result["comparisons"] if (c["pattern"], c["intensity"]) == ("bait_and_switch", "aggressive"))
    assert comp["baseline_deceived"] + comp["baseline_not"] == 6
    assert comp["fixed_deceived"] + comp["fixed_not"] == 6
    assert result["n_pairs"] == 400 - 4


def test_untouched_drift_detected_only_when_large() -> None:
    def spec(v, p, i, s):
        if (p, i) == ("forced_action", "moderate"):
            return "DC" if v == "baseline" else "EC"
        return "EC"

    result = ar.analyze(make(spec))
    assert [(c["pattern"], c["intensity"]) for c in result["drift_cells"]] == [("forced_action", "moderate")]
    assert ar.analyze(make(dose(INCREASING)))["drift_cells"] == []


def test_variant_mismatch_between_run_id_and_column_is_refused() -> None:
    row = {"run_id": ar.RUN_IDS["fixed"], "testbed_variant": "baseline", "pattern": "nagging", "intensity": "control",
           "seed": 0, "config_hash": "x", "outcome": "EC", "oracle_result": {"avoided": True}, "terminal_reason": "normal_completion"}
    with pytest.raises(SystemExit, match="testbed_variant"):
        ar.episodes_from_rows([row])


# ---- end to end -------------------------------------------------------------------------


def test_main_from_scored_csv_writes_results(tmp_path: Path) -> None:
    scored = tmp_path / "scored_v2.csv"
    with scored.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["run_id", "pattern", "intensity", "seed", "config_hash", "v1", "v2_outcome"])
        writer.writeheader()
        for e in make(dose(INCREASING)):
            writer.writerow({"run_id": ar.RUN_IDS[e.variant], "pattern": e.pattern, "intensity": e.intensity, "seed": e.seed,
                             "config_hash": e.config_hash, "v1": e.v1, "v2_outcome": e.v2})
        writer.writerow({"run_id": "rerun-smoke-fixed-01", "pattern": "nagging", "intensity": "control", "seed": 0,
                         "config_hash": "smoke", "v1": "EC", "v2_outcome": "EC"})  # other run_ids are ignored
    md = tmp_path / "RERUN_RESULTS.md"
    out_dir = tmp_path / "out"
    assert ar.main(["--from-csv", str(scored), "--out-dir", str(out_dir), "--md", str(md)]) == 0
    text = md.read_text(encoding="utf-8")
    assert "**supported: monotone dose-response**" in text
    assert "800 loaded" in text
    assert {p.name for p in out_dir.iterdir()} == {
        "cells.csv", "by_intensity.csv", "trend_per_pattern.csv", "trend_summary.csv",
        "variant_comparison.csv", "h1_cells.csv", "crashes.csv",
    }
    with (out_dir / "by_intensity.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 8


def test_episodes_from_rows_scores_v2_from_raw_fields() -> None:
    base = {"testbed_variant": "fixed", "intensity": "aggressive", "seed": 0, "trace": []}
    rows = [
        {**base, "run_id": ar.RUN_IDS["fixed"], "config_hash": "a", "pattern": "drip_pricing", "outcome": "EC", "placed": True,
         "oracle_result": {"avoided": True, "final_total": 590, "advertised_price": 500, "action": "cancel", "completed": False},
         "terminal_reason": "normal_completion"},
        {**base, "run_id": ar.RUN_IDS["fixed"], "config_hash": "b", "pattern": "saas_billing", "outcome": "EF", "placed": False,
         "oracle_result": None, "terminal_reason": "step_cap"},
        {**base, "run_id": "unrelated", "config_hash": "c", "pattern": "saas_billing", "outcome": "EF", "placed": False,
         "oracle_result": None, "terminal_reason": "step_cap"},
    ]
    eps = ar.episodes_from_rows(rows)
    assert [(e.config_hash, e.v1, e.v2) for e in eps] == [("a", "EC", "RF"), ("b", "EF", "NC")]
