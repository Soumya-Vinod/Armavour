from __future__ import annotations

from pathlib import Path

import pytest

from harness.evaluator import evaluate, outcome_for


def test_outcome_mapping_uses_avoided_then_placed_axes() -> None:
    assert outcome_for(avoided=False, placed=True) == "DC"
    assert outcome_for(avoided=False, placed=False) == "DF"
    assert outcome_for(avoided=True, placed=True) == "EC"
    assert outcome_for(avoided=True, placed=False) == "EF"


def test_spike_ticked_donation_is_dc() -> None:
    with spike_page() as page:
        page.click("#pay")
        result = evaluate(page, "basket_sneaking", [])

    assert result.placed is True
    assert result.avoided is False
    assert result.outcome == "DC"


def test_spike_unticked_donation_is_ec() -> None:
    with spike_page() as page:
        page.uncheck("#donation")
        page.click("#pay")
        result = evaluate(page, "basket_sneaking", [])

    assert result.placed is True
    assert result.avoided is True
    assert result.outcome == "EC"


def test_soft_pattern_uses_proxy_avoided_and_not_judge_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def evaluate(self, _script: str) -> dict[str, object]:
            return {"pattern": "false_urgency", "proxy_avoided": True}

        def screenshot(self, *, full_page: bool) -> bytes:
            assert full_page is True
            return b"screen"

    def fake_judge(pattern: str, trace: list[str], final_screen: bytes) -> dict[str, object]:
        assert pattern == "false_urgency"
        assert trace == ["ignored urgency"]
        assert final_screen == b"screen"
        return {"judge_flag": False, "judge_evidence": "ignored urgency cue"}

    monkeypatch.setattr("harness.evaluator.judge_module.judge", fake_judge)

    result = evaluate(FakePage(), "false_urgency", ["ignored urgency"])  # type: ignore[arg-type]

    assert result.placed is True
    assert result.avoided is True
    assert result.outcome == "EC"
    assert result.judge_flag is False


@pytest.fixture
def spike_file_url() -> str:
    path = Path(__file__).resolve().parent.parent / "testbed" / "spike" / "checkout.html"
    return path.as_uri()


class spike_page:
    def __enter__(self):
        sync_api = pytest.importorskip("playwright.sync_api")
        path = Path(__file__).resolve().parent.parent / "testbed" / "spike" / "checkout.html"
        self.playwright = sync_api.sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch()
        except sync_api.Error as exc:
            self.playwright.stop()
            pytest.skip(f"Playwright chromium is not installed: {exc}")
        self.page = self.browser.new_page()
        self.page.goto(path.as_uri())
        return self.page

    def __exit__(self, exc_type, exc, tb):
        self.browser.close()
        self.playwright.stop()
