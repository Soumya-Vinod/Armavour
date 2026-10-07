#!/usr/bin/env python3
"""
scripts/analyze_lang_control.py - analysis of the language x control replication.

Implements docs/audit/LANGCTL_PLAN.md §3-§6 exactly; nothing here is chosen
after seeing the data. Reads armavour_langctl read-only (scripts/score_v2.load_rows:
SELECT inside a READ ONLY transaction) and writes:

  results/langctl/cells.csv           pattern x condition: v1 and v2 counts, v2 rate + Wilson CI,
                                      Fisher exact vs en/en (two-sided, and one-sided "greater"),
                                      Holm across patterns within each comparison
  results/langctl/pooled.csv          condition: pooled v2 counts, Wilson CI
  results/langctl/comparisons.csv     H1-H3: primary one-sided exact stratified test (strata = pattern),
                                      verdict level, patterns strictly higher, within-cell ICC;
                                      descriptive only: pooled RD with pattern-resampling bootstrap CI, GEE
  results/langctl/judge.csv           confirm_shaming v1 judge-adjusted rate per condition (secondary)
  results/langctl/qualitative.csv     every deceived episode: first-step reasoning, final action,
                                      empty columns for the author's hand coding (§6)
  results/langctl/check_false.csv     check actions with value=false (§7)
  docs/audit/LANGCTL_RESULTS.md

  python scripts/analyze_lang_control.py            # run_id langctl-qwen-t07-01
  python scripts/analyze_lang_control.py --run-id smoke-langctl-01 --no-md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import csv
import json
import os
import zlib
from collections import Counter
from fractions import Fraction
from math import comb
from collections.abc import Iterable
from typing import Any

import numpy as np

from scripts.analyze_rerun import fisher, holm, wilson
from scripts.score_v2 import load_rows, score_row

REPO = Path(__file__).resolve().parent.parent
DEFAULT_URL = "postgresql+psycopg://armavour:armavour@localhost:5433/armavour_langctl"
RUN_ID = "langctl-qwen-t07-01"
OUT_DIR = REPO / "results" / "langctl"
MD_PATH = REPO / "docs" / "audit" / "LANGCTL_RESULTS.md"

PATTERNS = ("trick_question", "confirm_shaming", "interface_interference", "forced_action", "saas_billing")
REFERENCE = ("en", "en")
CONDITIONS = (("en", "en"), ("en", "hi"), ("en", "hinglish"), ("hi", "hi"), ("hinglish", "hinglish"))
# (hypothesis, condition vs en/en, role)
COMPARISONS = (
    ("H1", ("hi", "hi"), "primary"),
    ("H2", ("en", "hi"), "secondary"),
    ("H3a", ("hinglish", "hinglish"), "exploratory"),
    ("H3b", ("en", "hinglish"), "exploratory"),
)
JUDGE_PATTERNS = frozenset({"confirm_shaming"})
DECEIVED = frozenset({"DC", "DF"})
SCORED_V2 = frozenset({"EC", "DC", "DF", "RF"})
SEED = 20261007
N_BOOT = 10_000
ALPHA = 0.05
LEVELS = ("replicates", "pattern-specific replication", "does not replicate")


def cond(row: dict[str, Any]) -> tuple[str, str]:
    return (row["instruction_language"], row["language"])


def label(c: tuple[str, str]) -> str:
    return f"{c[0]}/{c[1]}"


def _rng(name: str) -> np.random.Generator:
    return np.random.default_rng([SEED, zlib.crc32(name.encode("utf-8"))])


# ---- per-row scoring -----------------------------------------------------------


def scored_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        v2 = score_row(r)
        out.append({**r, "v1": r.get("outcome") if r.get("outcome") is not None else "CRASH", "v2": v2.outcome, "v2_reason": v2.reason})
    return out


def check_design(rows: list[dict[str, Any]]) -> None:
    unknown = {(r["pattern"], cond(r)) for r in rows if r["pattern"] not in PATTERNS or cond(r) not in CONDITIONS or r.get("intensity") != "control"}
    if unknown:
        raise SystemExit(f"rows outside the design (pattern, condition) or not control: {sorted(unknown)}")
    dupes = [k for k, n in Counter(r["config_hash"] for r in rows).items() if n > 1]
    if dupes:
        raise SystemExit(f"duplicate config_hash rows: {dupes[:5]}")


# ---- §3/§4 tables ---------------------------------------------------------------


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    v2 = Counter(r["v2"] for r in rows)
    v1 = Counter(r["v1"] for r in rows)
    k = sum(v2[c] for c in DECEIVED)
    n = sum(v2[c] for c in SCORED_V2)
    return {"episodes": len(rows), **{f"v2_{c}": v2[c] for c in ("EC", "DC", "DF", "RF", "NC")},
            "deceived": k, "n": n, **{f"v1_{c}": v1[c] for c in ("EC", "DC", "EF", "DF", "CRASH")}}


def judge_adjusted(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    """v1 judge-adjusted DC (analysis._split_dc_by_judge_flag): DC of judge patterns only with judge_flag True.

    Returns (dc_raw, dc_judge, n_v1_scored) with n = rows with a stored outcome."""
    placed = [r for r in rows if r["v1"] != "CRASH"]
    dc = [r for r in placed if r["v1"] == "DC"]
    dc_judge = [r for r in dc if r["pattern"] not in JUDGE_PATTERNS or r.get("judge_flag") is True]
    return len(dc), len(dc_judge), len(placed)


def _rate(k: int, n: int) -> float | None:
    return k / n if n else None


def cell_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {(p, c): [r for r in rows if r["pattern"] == p and cond(r) == c] for p in PATTERNS for c in CONDITIONS}
    out = []
    for p in PATTERNS:
        for c in CONDITIONS:
            ct = counts(by[(p, c)])
            rate, lo, hi = wilson(ct["deceived"], ct["n"])
            out.append({"pattern": p, "condition": label(c), **ct, "rate": rate, "wilson_lo": lo, "wilson_hi": hi})
    ref = {r["pattern"]: r for r in out if r["condition"] == label(REFERENCE)}
    for _, c, _role in COMPARISONS:
        cells = [r for r in out if r["condition"] == label(c)]
        tables = [(r["deceived"], r["n"] - r["deceived"], ref[r["pattern"]]["deceived"], ref[r["pattern"]]["n"] - ref[r["pattern"]]["deceived"]) for r in cells]
        ps = [fisher(*t) for t in tables]
        pg = [fisher_greater(*t) for t in tables]
        for r, p, adj, g, gadj in zip(cells, ps, holm(ps), pg, holm(pg)):
            r["fisher_p_vs_en_en"], r["holm_p"] = p, adj
            r["fisher_greater_p"], r["holm_greater_p"] = g, gadj
    return out


def fisher_greater(a: int, b: int, c: int, d: int) -> float | None:
    """One-sided Fisher exact, [[a, b], [c, d]] = [[cond deceived, cond not], [en/en deceived, en/en not]], H1: cond > en/en."""
    if (a + b) == 0 or (c + d) == 0:
        return None
    return exact_stratified_p([(a, a + b, c, c + d)])


def exact_stratified_p(strata: list[tuple[int, int, int, int]]) -> float | None:
    """One-sided exact conditional test of a common odds ratio > 1 across strata (exact CMH; stratified permutation).

    Each stratum is (a, n1, c, n0): deceived/n in the tested condition and in en/en. Conditional on every
    stratum's margins, a follows a hypergeometric law; T = sum(a) has their convolution. p = P(T >= T_obs).
    Strata with n1 = 0 or n0 = 0 carry no information and are dropped. Exact rational arithmetic.
    None if no stratum is informative.
    """
    dist = {0: Fraction(1)}
    t_obs, used = 0, 0
    for a, n1, c, n0 in strata:
        if n1 == 0 or n0 == 0:
            continue
        used += 1
        m, total = a + c, n1 + n0
        denom = comb(total, n1)
        pmf = {k: Fraction(comb(m, k) * comb(total - m, n1 - k), denom) for k in range(max(0, m - n0), min(m, n1) + 1)}
        nxt: dict[int, Fraction] = {}
        for t, pt in dist.items():
            for k, pk in pmf.items():
                nxt[t + k] = nxt.get(t + k, Fraction(0)) + pt * pk
        dist = nxt
        t_obs += a
    if not used:
        return None
    return float(sum(pt for t, pt in dist.items() if t >= t_obs))


def within_cell_icc(rows: list[dict[str, Any]], conditions: Iterable[tuple[str, str]]) -> float | None:
    """ICC(1) of the deceived indicator within pattern x condition cells (v2-scored episodes)."""
    from scripts.review_analyses import icc_oneway

    groups = [[float(r["v2"] in DECEIVED) for r in rows if r["pattern"] == p and cond(r) == c and r["v2"] in SCORED_V2]
              for p in PATTERNS for c in conditions]
    return icc_oneway(groups)


def pooled_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in CONDITIONS:
        ct = counts([r for r in rows if cond(r) == c])
        rate, lo, hi = wilson(ct["deceived"], ct["n"])
        out.append({"condition": label(c), **ct, "rate": rate, "wilson_lo": lo, "wilson_hi": hi})
    return out


def bootstrap_rd(K: np.ndarray, N: np.ndarray, name: str, reps: int = N_BOOT) -> tuple[float | None, float | None]:
    """K, N: (patterns x 2) for [condition, en/en]. Resample patterns jointly; percentile 95% CI of the pooled RD."""
    rng = _rng(name)
    m = K.shape[0]
    idx = rng.integers(0, m, size=(reps, m))
    k, n = K[idx].sum(axis=1), N[idx].sum(axis=1)  # reps x 2
    ok = (n > 0).all(axis=1)
    if not ok.any():
        return None, None
    rd = k[ok, 0] / n[ok, 0] - k[ok, 1] / n[ok, 1]
    return float(np.percentile(rd, 2.5)), float(np.percentile(rd, 97.5))


def gee_rd(rows: list[dict[str, Any]], c: tuple[str, str]) -> dict[str, Any]:
    """Secondary: logistic GEE, deceived ~ condition, exchangeable within pattern (5 clusters only)."""
    from scripts.review_analyses import gee_logistic_exchangeable

    sub = [r for r in rows if cond(r) in (c, REFERENCE) and r["v2"] in SCORED_V2]
    if len({cond(r) for r in sub}) < 2:
        return {"gee_or": None, "gee_lo": None, "gee_hi": None, "gee_p": None, "gee_note": "condition missing"}
    y = np.array([r["v2"] in DECEIVED for r in sub], float)
    x = np.array([cond(r) == c for r in sub], float)
    none = {"gee_or": None, "gee_lo": None, "gee_hi": None, "gee_p": None}
    # every (condition, outcome) combination must occur, else the logit is separated and has no finite estimate
    if len({(a, b) for a, b in zip(x, y)}) < 4:
        return {**none, "gee_note": "not estimable (a condition has 0 or all deceived)"}
    X = np.column_stack([np.ones_like(x), x])
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            res = gee_logistic_exchangeable(y, X, np.array([r["pattern"] for r in sub]))
    except (np.linalg.LinAlgError, FloatingPointError) as exc:
        return {**none, "gee_note": f"not estimable ({type(exc).__name__})"}
    from scipy import stats

    b, se = float(res.beta[1]), float(res.se[1])
    if not (np.isfinite(b) and np.isfinite(se)):
        return {**none, "gee_note": "not estimable (non-finite estimate)"}
    z = b / se if se > 0 else float("nan")
    return {"gee_or": float(np.exp(b)), "gee_lo": float(np.exp(b - 1.959963984540054 * se)), "gee_hi": float(np.exp(b + 1.959963984540054 * se)),
            "gee_p": float(2 * stats.norm.sf(abs(z))) if np.isfinite(z) else None,
            "gee_note": f"5 clusters; rho={res.alpha:.3f}; converged={res.converged}"}


def comparison_table(rows: list[dict[str, Any]], cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§4: primary exact stratified test and verdict level per hypothesis; bootstrap CI and GEE descriptive only."""
    cell = {(r["pattern"], r["condition"]): r for r in cells}
    out = []
    for hyp, c, role in COMPARISONS:
        cc = {p: cell[(p, label(c))] for p in PATTERNS}
        cr = {p: cell[(p, label(REFERENCE))] for p in PATTERNS}
        K = np.array([[cc[p]["deceived"], cr[p]["deceived"]] for p in PATTERNS], float)
        N = np.array([[cc[p]["n"], cr[p]["n"]] for p in PATTERNS], float)
        rc, rr = _rate(int(K[:, 0].sum()), int(N[:, 0].sum())), _rate(int(K[:, 1].sum()), int(N[:, 1].sum()))
        rd = rc - rr if rc is not None and rr is not None else None
        exact_p = exact_stratified_p([(cc[p]["deceived"], cc[p]["n"], cr[p]["deceived"], cr[p]["n"]) for p in PATTERNS])
        pooled_higher = rd is not None and rd > 0
        primary_met = exact_p is not None and exact_p < ALPHA and pooled_higher
        higher = [p for p in PATTERNS if cc[p]["rate"] is not None and cr[p]["rate"] is not None and cc[p]["rate"] > cr[p]["rate"]]
        specific = [p for p in higher if cc[p].get("holm_greater_p") is not None and cc[p]["holm_greater_p"] < ALPHA]
        level = LEVELS[0] if primary_met else (LEVELS[1] if specific else LEVELS[2])
        lo, hi = bootstrap_rd(K, N, f"langctl-{hyp}")
        out.append({"hypothesis": hyp, "role": role, "comparison": f"{label(c)} vs {label(REFERENCE)}",
                    "deceived_cond": int(K[:, 0].sum()), "n_cond": int(N[:, 0].sum()), "deceived_ref": int(K[:, 1].sum()), "n_ref": int(N[:, 1].sum()),
                    "rate_cond": rc, "rate_ref": rr, "rd": rd,
                    "exact_stratified_p": exact_p, "pooled_higher": pooled_higher, "primary_met": primary_met,
                    "patterns_higher": len(higher), "patterns_higher_list": ";".join(higher),
                    "patterns_undefined": sum(1 for p in PATTERNS if cc[p]["rate"] is None or cr[p]["rate"] is None),
                    "pattern_specific": ";".join(specific), "level": level,
                    "icc_within_cell": within_cell_icc(rows, (c, REFERENCE)),
                    "boot_lo": lo, "boot_hi": hi, **gee_rd(rows, c)})
    return out


def verdict(comparisons: list[dict[str, Any]]) -> str:
    """Headline replication verdict = H1's level (§4); H2 and H3 levels are reported alongside."""
    return next(r["level"] for r in comparisons if r["hypothesis"] == "H1")


def judge_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in CONDITIONS:
        sub = [r for r in rows if r["pattern"] in JUDGE_PATTERNS and cond(r) == c]
        dc, dcj, n = judge_adjusted(sub)
        out.append({"pattern": "confirm_shaming", "condition": label(c), "v1_n": n, "v1_DC": dc, "v1_DC_judge": dcj,
                    "v1_rate": _rate(dc, n), "v1_rate_judge": _rate(dcj, n)})
    return out


# ---- §6 / §7 ----------------------------------------------------------------------


def _steps(trace: Any) -> list[Any]:
    if isinstance(trace, str):
        trace = json.loads(trace)
    return trace if isinstance(trace, list) else []


def first_reasoning(trace: Any) -> str:
    for s in _steps(trace):
        if isinstance(s, dict) and s.get("reasoning"):
            return str(s["reasoning"])
    return ""


def final_action(trace: Any) -> str:
    acts = [s["action"] for s in _steps(trace) if isinstance(s, dict) and isinstance(s.get("action"), dict)]
    return json.dumps(acts[-1], ensure_ascii=False) if acts else ""


def qualitative_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": r["id"], "pattern": r["pattern"], "condition": label(cond(r)), "seed": r["seed"], "v1": r["v1"], "v2": r["v2"],
             "v2_reason": r["v2_reason"], "first_step_reasoning": first_reasoning(r.get("trace")), "final_action": final_action(r.get("trace")),
             "author_code": "", "author_notes": ""}
            for r in sorted(rows, key=lambda r: (PATTERNS.index(r["pattern"]), CONDITIONS.index(cond(r)), r["seed"]))
            if r["v2"] in DECEIVED]


def check_false_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        for i, s in enumerate(_steps(r.get("trace"))):
            a = s.get("action") if isinstance(s, dict) else None
            if isinstance(a, dict) and a.get("action") == "check" and a.get("value") is False:
                out.append({"id": r["id"], "pattern": r["pattern"], "condition": label(cond(r)), "seed": r["seed"], "step": i,
                            "index": a.get("index"), "v1": r["v1"], "v2": r["v2"]})
    return out


# ---- output -------------------------------------------------------------------------


def analyze(raw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = scored_rows(raw_rows)
    check_design(rows)
    cells = cell_table(rows)
    comps = comparison_table(rows, cells)
    return {"rows": rows, "cells": cells, "pooled": pooled_table(rows), "comparisons": comps, "verdict": verdict(comps),
            "judge": judge_table(rows), "qualitative": qualitative_rows(rows), "check_false": check_false_rows(rows),
            "nc": sum(1 for r in rows if r["v2"] == "NC"), "episodes": len(rows), "icc_all": within_cell_icc(rows, CONDITIONS)}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else ["(empty)"])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_csvs(res: dict[str, Any], out_dir: Path = OUT_DIR) -> list[Path]:
    files = {"cells.csv": res["cells"], "pooled.csv": res["pooled"], "comparisons.csv": res["comparisons"], "judge.csv": res["judge"]}
    paths = []
    for name, rows in files.items():
        _write_csv(out_dir / name, rows)
        paths.append(out_dir / name)
    q_fields = ["id", "pattern", "condition", "seed", "v1", "v2", "v2_reason", "first_step_reasoning", "final_action", "author_code", "author_notes"]
    _write_csv(out_dir / "qualitative.csv", res["qualitative"], q_fields)
    _write_csv(out_dir / "check_false.csv", res["check_false"], ["id", "pattern", "condition", "seed", "step", "index", "v1", "v2"])
    return paths + [out_dir / "qualitative.csv", out_dir / "check_false.csv"]


def _p(x: float | None) -> str:
    return "—" if x is None else (f"{x:.3g}" if x >= 0.001 else f"{x:.1e}")


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}"


def _ci(lo: float | None, hi: float | None) -> str:
    return "—" if lo is None else f"[{100 * lo:.1f}, {100 * hi:.1f}]"


def _icc(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}"


def _table(header: list[str], rows: list[list[Any]]) -> str:
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(str(v) for v in r) + " |" for r in rows])


def render_markdown(res: dict[str, Any], *, source: str) -> str:
    L: list[str] = []
    w = L.append
    w("# Language x control replication: results")
    w("")
    w(f"Generated by `scripts/analyze_lang_control.py` from {source}, following `docs/audit/LANGCTL_PLAN.md` §3–§7 (pre-specified). Numbers only; interpretation is the author's.")
    w("")
    w(f"Episodes: {res['episodes']}; NC (excluded from v2 denominators): {res['nc']}. v2 rate = (DC+DF)/(EC+DC+DF+RF).")
    w("")
    w(f"**Pre-specified verdict (H1): {res['verdict']}.** Levels for H2 and H3 are in the table; H3 is exploratory.")
    w("")
    w(f"ICC(1) of the deceived indicator within pattern × condition cells, all conditions: {_icc(res['icc_all'])}. "
      "The primary test treats episodes within a cell as replicates; within-cell correlation makes it somewhat anti-conservative.")
    w("")
    w("## Hypotheses (§4)")
    w("")
    w("Primary: one-sided exact stratified test (exact conditional CMH, strata = pattern), α = 0.05. Pattern-specific: one-sided Fisher vs en/en, Holm across the 5 patterns.")
    w("")
    w(_table(["hyp", "role", "comparison", "deceived/n", "en/en deceived/n", "RD (pp)", "exact stratified p (one-sided)", "pooled higher",
              "patterns strictly higher", "pattern-specific (Holm p < 0.05)", "within-cell ICC", "level"],
             [[r["hypothesis"], r["role"], r["comparison"], f"{r['deceived_cond']}/{r['n_cond']}", f"{r['deceived_ref']}/{r['n_ref']}",
               "—" if r["rd"] is None else f"{100 * r['rd']:+.1f}", _p(r["exact_stratified_p"]), "yes" if r["pooled_higher"] else "no",
               f"{r['patterns_higher']}/5" + (f" ({r['patterns_undefined']} undefined)" if r["patterns_undefined"] else ""),
               r["pattern_specific"].replace(";", ", ") or "none", _icc(r["icc_within_cell"]), f"**{r['level']}**"] for r in res["comparisons"]]))
    w("")
    w("Descriptive only, **unreliable with 5 clusters**: pattern-resampling bootstrap CI of the pooled RD, and the GEE.")
    w("")
    w(_table(["hyp", "RD (pp)", f"bootstrap 95% CI ({N_BOOT:,} reps, patterns)", "GEE OR [95% CI], p"],
             [[r["hypothesis"], "—" if r["rd"] is None else f"{100 * r['rd']:+.1f}", _ci(r["boot_lo"], r["boot_hi"]),
               ("—" if r["gee_or"] is None else f"{r['gee_or']:.2f} [{r['gee_lo']:.2f}, {r['gee_hi']:.2f}], p={_p(r['gee_p'])}") + f" ({r['gee_note']})"]
              for r in res["comparisons"]]))
    w("")
    w("## Pooled by condition")
    w("")
    w(_table(["condition", "episodes", "EC", "DC", "DF", "RF", "NC", "deceived/n", "rate %", "Wilson 95% CI"],
             [[r["condition"], r["episodes"], r["v2_EC"], r["v2_DC"], r["v2_DF"], r["v2_RF"], r["v2_NC"], f"{r['deceived']}/{r['n']}", _pct(r["rate"]), _ci(r["wilson_lo"], r["wilson_hi"])]
              for r in res["pooled"]]))
    w("")
    w("## Pattern × condition")
    w("")
    w("Fisher exact vs en/en in the same pattern, two-sided and one-sided (greater); Holm across the 5 patterns within each comparison.")
    w("")
    w(_table(["pattern", "condition", "EC", "DC", "DF", "RF", "NC", "deceived/n", "rate %", "Wilson 95% CI", "Fisher p", "Holm p", "one-sided p", "one-sided Holm p", "v1 EC/DC/EF/DF/crash"],
             [[r["pattern"], r["condition"], r["v2_EC"], r["v2_DC"], r["v2_DF"], r["v2_RF"], r["v2_NC"], f"{r['deceived']}/{r['n']}", _pct(r["rate"]),
               _ci(r["wilson_lo"], r["wilson_hi"]), _p(r.get("fisher_p_vs_en_en")), _p(r.get("holm_p")), _p(r.get("fisher_greater_p")), _p(r.get("holm_greater_p")),
               f"{r['v1_EC']}/{r['v1_DC']}/{r['v1_EF']}/{r['v1_DF']}/{r['v1_CRASH']}"] for r in res["cells"]]))
    w("")
    w("## confirm_shaming, v1 judge-adjusted (secondary)")
    w("")
    w(_table(["condition", "v1 n", "v1 DC", "v1 DC with judge_flag", "v1 DC %", "judge-adjusted %"],
             [[r["condition"], r["v1_n"], r["v1_DC"], r["v1_DC_judge"], _pct(r["v1_rate"]), _pct(r["v1_rate_judge"])] for r in res["judge"]]))
    w("")
    w("## Qualitative check (§6)")
    w("")
    w(f"{len(res['qualitative'])} deceived episodes exported to `results/langctl/qualitative.csv` (first-step reasoning, final action) for the author's hand coding: comprehension failure / language-generation breakdown / other. Not coded here.")
    w("")
    w("## check with value=false (§7)")
    w("")
    cf = res["check_false"]
    w(f"{len(cf)} `check` actions with value=false in {len({r['id'] for r in cf})} episodes" + (": ids " + ", ".join(str(i) for i in sorted({r['id'] for r in cf})) if cf else "") + " (`results/langctl/check_false.csv`).")
    w("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Analyse the language x control replication (read-only)")
    ap.add_argument("--run-id", default=RUN_ID)
    ap.add_argument("--database-url", default=os.getenv("LANGCTL_DATABASE_URL", DEFAULT_URL))
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--no-md", action="store_true", help="do not write docs/audit/LANGCTL_RESULTS.md")
    args = ap.parse_args(argv)
    rows = load_rows([args.run_id], args.database_url)
    if not rows:
        raise SystemExit(f"no rows for run_id {args.run_id}")
    res = analyze(rows)
    for p in write_csvs(res, args.out_dir):
        print(f"wrote {p}")
    if not args.no_md:
        MD_PATH.write_text(render_markdown(res, source=f"`{args.run_id}` (armavour_langctl)"), encoding="utf-8")
        print(f"wrote {MD_PATH}")
    print(f"verdict: {res['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
