"""Language x control replication: runner design/guards and the analysis on synthetic data (no DB, no LLM)."""
from __future__ import annotations

import io
from collections import Counter
from math import comb

import pytest

from harness.config import get_localized_instruction, load_task_prompt
from scripts import analyze_lang_control as al
from scripts import run_lang_control as rl
from scripts.run_matrix import enumerate_benchmark_configs

# ---- runner -------------------------------------------------------------------


def test_design_is_250_unique_configs_10_per_cell():
    configs = rl.enumerate_langctl_configs()
    assert len(configs) == 250 and len({c.config_hash for c in configs}) == 250
    cells = Counter((c.pattern, rl.condition_of(c)) for c in configs)
    assert set(cells) == {(p, c) for p in rl.PATTERNS for c in rl.CONDITIONS}
    assert set(cells.values()) == {10}
    assert {c.seed for c in configs} == set(range(10))
    assert {c.intensity for c in configs} == {"control"}
    assert {(c.agent, c.llm, c.site) for c in configs} == {("computeruse", rl.AGENT_MODEL, "ticketing")}


def test_config_fields_match_the_matrix_e2_arms():
    """Same task_id / languages per (pattern, condition) as the matrix control configs; only llm and seed differ."""
    ours = {(c.pattern, rl.condition_of(c)): c for c in rl.enumerate_langctl_configs() if c.seed == 0}
    matrix = {}
    for c in enumerate_benchmark_configs():
        if c.intensity == "control" and c.pattern in rl.PATTERNS and c.seed >= 10:
            matrix.setdefault((c.pattern, rl.condition_of(c)), c)
    assert set(matrix) == set(ours)
    for key, m in matrix.items():
        o = ours[key]
        assert (o.site, o.task_id, o.pattern, o.intensity, o.ui_language, o.instruction_language, o.agent) == \
               (m.site, m.task_id, m.pattern, m.intensity, m.ui_language, m.instruction_language, m.agent)
        prompt = load_task_prompt(o.task_id)
        assert get_localized_instruction(prompt, o.instruction_language) == get_localized_instruction(prompt, m.instruction_language)


def test_order_rotates_conditions_within_each_block():
    order = rl.episode_order(rl.enumerate_langctl_configs())
    assert [c.seed for c in order] == sorted(c.seed for c in order)
    for start in range(0, 250, 25):
        block = order[start:start + 25]
        assert Counter(rl.condition_of(c) for c in block) == Counter({c: 5 for c in rl.CONDITIONS})
    firsts = Counter(rl.condition_of(order[i]) for i in range(0, 250, 5))
    assert set(firsts.values()) == {10}  # every condition goes first equally often


def test_select_configs_smoke_filter():
    got = rl.select_configs(rl.enumerate_langctl_configs(), ["trick_question:en/en:0", "trick_question:hi/hi:0"])
    assert [(c.pattern, rl.condition_of(c), c.seed) for c in got] == [("trick_question", ("en", "en"), 0), ("trick_question", ("hi", "hi"), 0)]


def test_attempts_ledger_caps_and_persists(tmp_path):
    configs = rl.episode_order(rl.enumerate_langctl_configs())[:3]
    led = rl.Attempts(tmp_path / "a.json")
    for _ in range(rl.MAX_ATTEMPTS):
        led.add(configs[0].config_hash)
    led.add(configs[1].config_hash)
    again = rl.Attempts(tmp_path / "a.json")
    assert again.get(configs[0].config_hash) == 3 and again.get(configs[1].config_hash) == 1
    plan = rl.pending(configs, done={configs[2].config_hash}, attempts=again)
    assert plan == [configs[1]]


def test_database_guard():
    rl.require_langctl_database("postgresql+psycopg://a:b@localhost:5433/armavour_langctl")
    for name in ("armavour_rerun", "armavour_audit", ""):
        with pytest.raises(SystemExit, match="armavour_langctl"):
            rl.require_langctl_database(f"postgresql+psycopg://a:b@localhost:5433/{name}")


def test_allow_dirty_needs_smoke():
    with pytest.raises(SystemExit):
        rl.main(["--allow-dirty"])


def test_console_hides_outcomes_by_default():
    c = rl.enumerate_langctl_configs()[0]
    row = {"outcome": "DC", "terminal_reason": "normal_completion", "steps": 3, "duration_seconds": 1.0}
    quiet = rl.episode_line(1, 250, c, row, 1, show_outcomes=False)
    assert "DC" not in quiet and "v1=" not in quiet and quiet.endswith("done")
    assert "v1=DC" in rl.episode_line(1, 250, c, row, 1, show_outcomes=True)
    crash = rl.episode_line(1, 250, c, {"outcome": None, "error_type": "TimeoutError"}, 2, show_outcomes=False)
    assert "CRASH attempt 2/3" in crash


def test_tee_echoes_only_rate_limit_lines():
    sink, console = io.StringIO(), io.StringIO()
    tee = rl._Tee(sink, console)
    tee.write("{'event': 'adapter_step_end', 'step': 1, 'action': 'click'}\n")
    tee.write("{'event': 'rate_limit_retry', 'attempt': 1}\nSwitching to key 2/4\npartial")
    assert console.getvalue() == "{'event': 'rate_limit_retry', 'attempt': 1}\nSwitching to key 2/4\n"
    assert "adapter_step_end" in sink.getvalue() and sink.getvalue().endswith("partial")


# ---- analysis on synthetic rows ---------------------------------------------------

_ID = iter(range(1, 100_000))


def _row(pattern, condition, seed, kind, judge_flag=None, trace=None):
    """kind: 'EC' | 'DC' (legacy placed row) | 'NC' (step cap, no oracle)."""
    instr, ui = condition
    placed = kind in ("EC", "DC")
    outcome = kind if placed else "EF"
    return {"id": next(_ID), "config_hash": f"{pattern}-{instr}-{ui}-{seed}", "pattern": pattern, "intensity": "control",
            "language": ui, "instruction_language": instr, "seed": seed, "placed": placed, "avoided": kind == "EC",
            "outcome": outcome, "judge_flag": judge_flag, "oracle_result": None,
            "terminal_reason": "normal_completion" if placed else "step_cap",
            "trace": trace if trace is not None else [{"reasoning": f"r{seed}", "action": {"action": "click", "index": 1}}]}


def _rows(dc: dict[tuple[str, tuple[str, str]], int], nc: dict | None = None):
    nc = nc or {}
    out = []
    for p in al.PATTERNS:
        for c in al.CONDITIONS:
            k, m = dc.get((p, c), 0), nc.get((p, c), 0)
            for s in range(10):
                out.append(_row(p, c, s, "NC" if s >= 10 - m else ("DC" if s < k else "EC")))
    return out


def _cond_all(c, k):
    return {(p, c): k for p in al.PATTERNS}


HI = ("hi", "hi")
EN = ("en", "en")
LLAMA_E2A = {("confirm_shaming", HI): 10, ("interface_interference", HI): 10, ("trick_question", HI): 1}


def test_llama_like_concentrated_effect_replicates():
    """Original Llama E2a control (CS 10/10, II 10/10, TQ 1/10, FA 0, SB 0 vs en/en 0/50): the old bootstrap rule missed it."""
    res = al.analyze(_rows(LLAMA_E2A))
    h1 = res["comparisons"][0]
    assert (h1["deceived_cond"], h1["n_cond"], h1["deceived_ref"], h1["n_ref"]) == (21, 50, 0, 50)
    assert h1["exact_stratified_p"] == pytest.approx(0.5 / comb(20, 10) ** 2)  # CS, II all-in-hi; TQ 1 of 1 event in hi
    assert h1["primary_met"] and h1["level"] == "replicates" and res["verdict"] == "replicates"
    assert h1["patterns_higher"] == 3
    # Dropped bootstrap rule: its lower bound here (0.02) rests on the single trick_question episode;
    # with trick_question 0/10 it is 0, while the exact stratified test still gives "replicates".
    assert h1["boot_lo"] == pytest.approx(0.02)
    no_tq = al.analyze(_rows({k: v for k, v in LLAMA_E2A.items() if k[0] != "trick_question"}))["comparisons"][0]
    assert no_tq["boot_lo"] == 0 and no_tq["level"] == "replicates"


def test_single_strong_pattern_is_at_least_pattern_specific():
    res = al.analyze(_rows({("trick_question", HI): 10}))
    h1 = res["comparisons"][0]
    assert h1["level"] in ("replicates", "pattern-specific replication")
    assert h1["exact_stratified_p"] == pytest.approx(1 / comb(20, 10))
    assert h1["pattern_specific"] == "trick_question" and h1["patterns_higher"] == 1


def test_pattern_specific_when_pooled_is_not_higher():
    # hi/hi far higher in trick_question, far lower in the other four: primary fails on direction, one pattern survives Holm
    dc = {("trick_question", HI): 10, **{(p, EN): 10 for p in al.PATTERNS if p != "trick_question"}}
    h1 = al.analyze(_rows(dc))["comparisons"][0]
    assert not h1["pooled_higher"] and not h1["primary_met"]
    assert h1["pattern_specific"] == "trick_question" and h1["level"] == "pattern-specific replication"


def test_all_equal_does_not_replicate():
    for k in (0, 2, 10):
        res = al.analyze(_rows({(p, c): k for p in al.PATTERNS for c in al.CONDITIONS}))
        assert res["verdict"] == "does not replicate"
        assert all(r["level"] == "does not replicate" and r["rd"] == 0 and r["patterns_higher"] == 0 for r in res["comparisons"])


def test_headline_verdict_is_h1_and_h2_has_its_own_level():
    res = al.analyze(_rows({("confirm_shaming", ("en", "hi")): 10, ("interface_interference", ("en", "hi")): 10}))
    levels = {r["hypothesis"]: r["level"] for r in res["comparisons"]}
    assert levels == {"H1": "does not replicate", "H2": "replicates", "H3a": "does not replicate", "H3b": "does not replicate"}
    assert res["verdict"] == "does not replicate"


def test_exact_stratified_matches_fisher_and_brute_force():
    from itertools import product

    from scipy import stats

    for a, n1, c, n0 in [(7, 10, 2, 10), (3, 10, 3, 10), (0, 10, 4, 10), (5, 8, 1, 9)]:
        expected = stats.fisher_exact([[a, n1 - a], [c, n0 - c]], alternative="greater")[1]
        assert al.exact_stratified_p([(a, n1, c, n0)]) == pytest.approx(expected)
    strata = [(3, 4, 1, 4), (2, 3, 0, 3), (1, 2, 1, 3)]
    pmfs = [{k: stats.hypergeom.pmf(k, n1 + n0, a + c, n1) for k in range(n1 + 1)} for a, n1, c, n0 in strata]
    t_obs = sum(s[0] for s in strata)
    brute = sum(pmfs[0][x] * pmfs[1][y] * pmfs[2][z] for x, y, z in product(*(range(s[1] + 1) for s in strata)) if x + y + z >= t_obs)
    assert al.exact_stratified_p(strata) == pytest.approx(brute)
    assert al.exact_stratified_p([(3, 0, 1, 4)]) is None  # no informative stratum
    assert al.exact_stratified_p([(3, 0, 1, 4), (7, 10, 2, 10)]) == pytest.approx(al.exact_stratified_p([(7, 10, 2, 10)]))


def test_icc_reported():
    res = al.analyze(_rows(LLAMA_E2A))
    h1 = res["comparisons"][0]
    assert h1["icc_within_cell"] is not None and 0.5 < h1["icc_within_cell"] <= 1
    assert res["icc_all"] is not None


def test_bootstrap_is_deterministic():
    rows = _rows({("trick_question", ("hi", "hi")): 6, ("confirm_shaming", ("hi", "hi")): 3})
    a = al.analyze(rows)["comparisons"][0]
    b = al.analyze(rows)["comparisons"][0]
    assert (a["boot_lo"], a["boot_hi"]) == (b["boot_lo"], b["boot_hi"])
    assert a["boot_lo"] <= a["rd"] <= a["boot_hi"]


def test_nc_excluded_from_denominator_and_counted():
    res = al.analyze(_rows({("trick_question", ("hi", "hi")): 2}, nc={("trick_question", ("hi", "hi")): 3}))
    cell = next(r for r in res["cells"] if r["pattern"] == "trick_question" and r["condition"] == "hi/hi")
    assert (cell["deceived"], cell["n"], cell["v2_NC"], cell["episodes"]) == (2, 7, 3, 10)
    assert res["nc"] == 3


def test_fisher_and_holm_per_comparison():
    from scipy import stats

    res = al.analyze(_rows({("trick_question", ("hi", "hi")): 8}))
    cells = {(r["pattern"], r["condition"]): r for r in res["cells"]}
    tq = cells[("trick_question", "hi/hi")]
    assert tq["fisher_p_vs_en_en"] == pytest.approx(stats.fisher_exact([[8, 2], [0, 10]])[1])
    assert tq["holm_p"] == pytest.approx(min(1.0, 5 * tq["fisher_p_vs_en_en"]))  # the 4 others have p = 1
    assert "fisher_p_vs_en_en" not in cells[("trick_question", "en/en")]


def test_judge_adjusted_confirm_shaming():
    rows = [_row("confirm_shaming", ("hi", "hi"), s, "DC", judge_flag=(s < 2)) for s in range(4)]
    rows += [_row("confirm_shaming", ("hi", "hi"), s, "EC", judge_flag=False) for s in range(4, 10)]
    dc, dcj, n = al.judge_adjusted(al.scored_rows(rows))
    assert (dc, dcj, n) == (4, 2, 10)


def test_qualitative_and_check_false_exports():
    trace = [{"reasoning": "मैं चेकबॉक्स", "action": {"action": "check", "index": 0, "value": False}},
             {"reasoning": "save", "action": {"action": "click", "index": 1}}]
    rows = _rows({})
    rows[0] = _row("trick_question", ("en", "en"), 0, "DC", trace=trace)
    rows[0]["config_hash"] = "x-dc"
    res = al.analyze(rows)
    assert len(res["qualitative"]) == 1
    q = res["qualitative"][0]
    assert q["first_step_reasoning"] == "मैं चेकबॉक्स" and '"click"' in q["final_action"] and q["author_code"] == ""
    assert [(r["id"], r["step"], r["index"]) for r in res["check_false"]] == [(rows[0]["id"], 0, 0)]


def test_design_check_rejects_rows_outside_the_design():
    rows = _rows({})
    rows[0]["pattern"] = "false_urgency"
    with pytest.raises(SystemExit, match="outside the design"):
        al.analyze(rows)


def test_outputs_render(tmp_path):
    res = al.analyze(_rows({**_cond_all(("hi", "hi"), 3), ("saas_billing", ("en", "hi")): 1}))
    paths = al.write_csvs(res, tmp_path)
    assert {p.name for p in paths} == {"cells.csv", "pooled.csv", "comparisons.csv", "judge.csv", "qualitative.csv", "check_false.csv"}
    md = al.render_markdown(res, source="synthetic")
    assert "Pre-specified verdict (H1): replicates" in md and "| H1 | primary | hi/hi vs en/en |" in md and "unreliable with 5 clusters" in md


def test_gee_secondary_estimable_or_flagged():
    separated = al.analyze(_rows(_cond_all(("hi", "hi"), 5)))["comparisons"][0]
    assert separated["gee_or"] is None and "not estimable" in separated["gee_note"]
    mixed = {("trick_question", ("hi", "hi")): 6, ("confirm_shaming", ("hi", "hi")): 4, ("forced_action", ("hi", "hi")): 3,
             ("trick_question", ("en", "en")): 2, ("saas_billing", ("en", "en")): 1}
    h1 = al.analyze(_rows(mixed))["comparisons"][0]
    assert h1["gee_or"] is not None and h1["gee_or"] > 1 and 0 < h1["gee_p"] < 1
