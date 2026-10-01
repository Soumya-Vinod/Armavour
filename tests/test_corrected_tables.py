from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts import corrected_tables as ct


def toy_frame() -> pd.DataFrame:
    rows = []
    for pattern in ("drip_pricing", "saas_billing", "trick_question", "subscription_trap", "basket_sneaking"):
        for intensity in ("control", "subtle", "moderate", "aggressive"):
            for lang in ("en", "hi", "hinglish"):
                rows.append({"pattern": pattern, "intensity": intensity, "ui_language": lang,
                             "outcome": "DC", "avoided": False, "arm": "E2"})
    df = pd.DataFrame(rows)
    st = (df["pattern"] == "subscription_trap") & (df["intensity"] == "aggressive")
    df.loc[st, ["outcome", "avoided"]] = ["EF", True]
    return df


def test_exclude_breaking_drops_exactly_the_four_cells_in_every_language() -> None:
    df = toy_frame()
    out = ct.apply_filters(df, exclude_breaking=True)
    dropped = df.drop(out.index)
    assert set(zip(dropped["pattern"], dropped["intensity"])) == ct.BREAKING_CELLS
    assert len(dropped) == len(ct.BREAKING_CELLS) * 3  # all three languages, incl. trick_question hinglish
    assert set(dropped["ui_language"]) == {"en", "hi", "hinglish"}
    assert ct.apply_filters(df).equals(df)  # no flags -> unchanged


def test_st_abandon_modes() -> None:
    df = toy_frame()
    abandon = ct.st_abandon_mask(df)
    assert int(abandon.sum()) == 3

    as_is = ct.apply_filters(df, st_abandon="as-is")
    assert (as_is.loc[abandon, "outcome"] == "EF").all()

    excluded = ct.apply_filters(df, st_abandon="exclude")
    assert len(excluded) == len(df) - 3
    assert not ct.st_abandon_mask(excluded).any()

    as_dc = ct.apply_filters(df, st_abandon="as-dc")
    assert (as_dc.loc[abandon, "outcome"] == "DC").all()
    assert (~as_dc.loc[abandon, "avoided"].astype(bool)).all()
    assert (df.loc[abandon, "outcome"] == "EF").all()  # the input is not mutated

    with pytest.raises(ValueError):
        ct.apply_filters(df, st_abandon="as-ef")


def test_filters_compose() -> None:
    df = toy_frame()
    both = ct.apply_filters(df, exclude_breaking=True, st_abandon="exclude")
    assert len(both) == len(df) - len(ct.BREAKING_CELLS) * 3 - 3


def test_mcnemar_exact_on_toy_pairs() -> None:
    assert ct.mcnemar(6, 0) == pytest.approx(0.03125)
    assert ct.mcnemar(0, 6) == pytest.approx(0.03125)
    assert ct.mcnemar(3, 26) == pytest.approx(1.5236e-05, rel=1e-3)  # paper Table IV
    assert ct.mcnemar(0, 0) is None
    assert ct.mcnemar(5, 5) == pytest.approx(1.0)


def test_e2_pairing_and_cell_counts_on_toy_pairs() -> None:
    rows = []
    # cell A: hi deceived on all 3 seeds, en on none -> c=3 ; cell B: en deceived on 1 seed only -> b=1
    for seed in range(3):
        rows += [
            {"pattern": "forced_action", "intensity": "moderate", "seed": seed, "ui_language": "en", "outcome": "EC"},
            {"pattern": "forced_action", "intensity": "moderate", "seed": seed, "ui_language": "hi", "outcome": "DC"},
            {"pattern": "saas_billing", "intensity": "subtle", "seed": seed, "ui_language": "en", "outcome": "DC" if seed == 0 else "EC"},
            {"pattern": "saas_billing", "intensity": "subtle", "seed": seed, "ui_language": "hi", "outcome": "EC"},
        ]
    df = pd.DataFrame(rows).assign(arm="E2", instruction_language="en")
    pairs = ct.e2_pairs(df, "hi")
    assert len(pairs) == 6
    b = int((pairs["dc_en"] & ~pairs["dc_other"]).sum())
    c = int((~pairs["dc_en"] & pairs["dc_other"]).sum())
    assert (b, c) == (1, 3)
    assert ct.mcnemar(b, c) == pytest.approx(0.625)


def test_regression_check_reports_any_cell_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frame = pd.DataFrame({"arm": ["E1a", "E1b"], "DC": [70, 54], "dc_rate": [0.175, 0.135]})
    frame.to_csv(tmp_path / "t.csv", index=False)
    monkeypatch.setattr(ct, "REGRESSION", {"t.csv": lambda d: d})
    assert ct.regression_check(frame, csv_dir=tmp_path) == []
    changed = frame.copy()
    changed.loc[1, "DC"] = 55
    problems = ct.regression_check(changed, csv_dir=tmp_path)
    assert len(problems) == 1 and "row 1 column DC" in problems[0]
