from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: needs the testbed dev servers (fixed :5173, baseline :5174); run with -m integration",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # Integration tests drive real browsers against the dev servers, so the
    # default `pytest tests` run (keys blanked, no servers) skips them.
    if "integration" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="integration test: run with -m integration and both dev servers up")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
