"""Offline tests for scripts/review_analyses.py and scripts/export_traces.py (no database, no network)."""

from __future__ import annotations

import numpy as np
import pytest

from scripts import export_traces as ex
from scripts import review_analyses as ra


# --- GEE: pinned to statsmodels 0.15.0 GEE(Binomial, Exchangeable) on the same synthetic data -----------


def _synthetic():
    rng = np.random.default_rng(1)
    n = 300
    g = rng.integers(0, 15, n)
    x = rng.normal(size=n)
    u = rng.normal(size=15)[g]
    y = (rng.random(n) < 1 / (1 + np.exp(-(0.3 + 0.8 * x + u)))).astype(float)
    return y, np.column_stack([np.ones(n), x]), g


def test_gee_matches_statsmodels_reference():
    y, X, g = _synthetic()
    r = ra.gee_logistic_exchangeable(y, X, g)
    assert r.converged
    np.testing.assert_allclose(r.beta, [0.58919569, 0.79465831], atol=1e-6)
    np.testing.assert_allclose(r.se, [0.23552151, 0.1085127], atol=1e-6)
    assert r.alpha == pytest.approx(0.13987671, abs=1e-6)


def test_gee_group_labels_may_be_strings():
    y, X, g = _synthetic()
    a = ra.gee_logistic_exchangeable(y, X, g)
    b = ra.gee_logistic_exchangeable(y, X, np.array([f"cell-{v}" for v in g]))
    np.testing.assert_allclose(a.beta, b.beta)
    np.testing.assert_allclose(a.se, b.se)


# --- ICC and bootstrap -------------------------------------------------------------------------------------


def test_icc_extremes():
    assert ra.icc_oneway([[1, 1, 1], [0, 0, 0]]) == pytest.approx(1.0)
    assert ra.icc_oneway([[1, 0], [1, 0], [1, 0]]) == pytest.approx(-1.0)
    assert ra.icc_oneway([[0, 0], [0, 0]]) is None  # no variance at all
    assert ra.icc_oneway([[1, 0, 1]]) is None  # one group


def test_cluster_bootstrap_is_deterministic_and_bounded():
    k, n = [0, 5, 10, 2], [10, 10, 10, 10]
    a = ra.cluster_bootstrap(k, n, "t", reps=2000)
    b = ra.cluster_bootstrap(k, n, "t", reps=2000)
    assert a == b
    assert 0.0 <= a[0] <= 17 / 40 <= a[1] <= 1.0
    assert ra.cluster_bootstrap([], [], "t") == (None, None)


def test_profile_bootstrap_resamples_clusters_jointly():
    K = np.array([[0, 0, 5, 9], [0, 0, 0, 0]], float)
    N = np.full((2, 4), 10.0)
    prof = ra.cluster_bootstrap_profile(K, N, "p", reps=500)
    assert prof[0] == (0.0, 0.0)
    assert prof[3][0] == 0.0 and prof[3][1] == pytest.approx(0.9)


# --- trick question replay and re-scoring -----------------------------------------------------------------


def _step(action, index, value=None):
    return {"step": 0, "reasoning": "", "action": {"action": action, "index": index, "value": value}}


def test_cu_box_state_replay():
    assert ra.cu_box_state([_step("click", 1)]) == {"checked": False, "touched": False, "last_click": 1}
    assert ra.cu_box_state([_step("check", 0), _step("click", 1)])["checked"] is True
    # 'check' sets the box whatever `value` says (computeruse.py at a2f4ef7 calls handle.check())
    assert ra.cu_box_state([_step("check", 0, False), _step("click", 1)])["checked"] is True
    assert ra.cu_box_state([_step("check", 0), _step("uncheck", 0), _step("click", 1)])["checked"] is False
    st = ra.cu_box_state([_step("click", 0), _step("click", 0), _step("click", 1)])
    assert st["checked"] is False and st["touched"] is True


def test_cu_box_state_honour_false_and_detector():
    t = [_step("check", 0, False), _step("click", 1)]
    assert ra.cu_box_state(t)["checked"] is True  # as executed: handle.check() ignores value
    assert ra.cu_box_state(t, honour_false=True)["checked"] is False
    assert ra.cu_box_state([_step("check", 0, True), _step("click", 1)], honour_false=True)["checked"] is True
    assert ra.cu_box_state([_step("check", 0), _step("click", 1)], honour_false=True)["checked"] is True  # value None
    assert ra.has_check_false(t)
    assert not ra.has_check_false([_step("check", 0), _step("uncheck", 0, False)])
    assert not ra.has_check_false([_step("check", 3, False)])  # not the checkbox element
    assert ra.box_sequence(t) == "check(value=False)"


@pytest.mark.parametrize("intensity,checked,original,rendered", [
    ("control", True, True, True), ("control", False, False, False),
    ("subtle", True, True, True), ("subtle", False, False, False),
    ("moderate", True, True, False), ("moderate", False, False, True),
    ("aggressive", True, False, True), ("aggressive", False, True, False),
])
def test_rescoring_rules(intensity, checked, original, rendered):
    assert ra.deceived_original(intensity, checked) is original
    assert ra.deceived_rendered(intensity, checked) is rendered


# --- NUMBERS block -----------------------------------------------------------------------------------------


def test_write_numbers_inserts_then_replaces_block(tmp_path, monkeypatch):
    path = tmp_path / "NUMBERS.md"
    path.write_text("# N\n\n| id | value | meaning | source |\n|---|---|---|---|\n| T1-E1a | 1 | x | CT |\n\n---\n\n## Appendix\nsql\n", encoding="utf-8")
    monkeypatch.setattr(ra, "NUMBERS_PATH", path)
    L = ra.Ledger()
    L.add("V-X-1", "a|b", "m", "s")
    assert ra.write_numbers(L, []) == 1
    first = path.read_text(encoding="utf-8")
    assert "| T1-E1a | 1 |" in first and "| V-X-1 | a/b | m | s |" in first
    assert first.index(ra.V_END) < first.index("## Appendix")
    L2 = ra.Ledger()
    L2.add("V-X-2", "c", "m", "s")
    ra.write_numbers(L2, [])
    second = path.read_text(encoding="utf-8")
    assert "V-X-1" not in second and "V-X-2" in second and second.count(ra.V_BEGIN) == 1
    with pytest.raises(ValueError):
        L2.add("V-X-2", "dup", "m", "s")


# --- export anonymity check --------------------------------------------------------------------------------


def test_scan_value_flags_identifying_content():
    matchers = ex.build_matchers(["Jane Q Researcher", "Example Institute of Technology"])
    assert ex.scan_value("clicked index 1", matchers) == ([], 0)
    hits, _ = ex.scan_value("thanks to jane q researcher", matchers)
    assert hits
    hits, _ = ex.scan_value("work at EXAMPLE INSTITUTE OF TECHNOLOGY", matchers)
    assert hits
    hits, _ = ex.scan_value(r"saved to C:\Users\someone\file.txt", matchers)
    assert "local user path" in hits
    hits, _ = ex.scan_value("/home/someone/x", matchers)
    assert "local user path" in hits
    hits, ph = ex.scan_value("contact real.person@university.edu", matchers)
    assert "non-placeholder email address" in hits and ph == 0


def test_scan_value_allows_agent_placeholder_emails():
    for addr in ("example@email.com", "dummyemail@example.com", "example@gmail.com", "user@example.com"):
        hits, ph = ex.scan_value(f'fill {addr}', [])
        assert hits == [] and ph == 1, addr


def test_deny_terms_ignores_comments(tmp_path):
    f = tmp_path / "deny.txt"
    f.write_text("# comment\nAcme Univ\n\n  Foo  \n", encoding="utf-8")
    assert ex.deny_terms(f) == ["Acme Univ", "Foo"]
    assert ex.deny_terms(tmp_path / "missing.txt") == []


def test_m4_side_by_side_keeps_changed_and_forced_rows():
    import pandas as pd
    old = pd.DataFrame({"k": ["x", "y", "z"], "v": [1, 2, ""]})
    b = pd.DataFrame({"k": ["x", "y", "z"], "v": [1, 3, ""]})
    c = pd.DataFrame({"k": ["x", "y"], "v": [1, 4]})
    out = ra.m4_side_by_side([old, b, c], ["k"], always=[("x",)])
    assert out.to_dict("records") == [
        {"k": "x", "v": "1 → 1 → 1", "changed": "no"},
        {"k": "y", "v": "2 → 3 → 4", "changed": "yes"},
        {"k": "z", "v": " → " + " → —", "changed": "yes"},
    ]
    assert ra._three(["", "", ""]) == ""

