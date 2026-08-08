from __future__ import annotations

import json
from pathlib import Path

from scripts.run_matrix import export_summary_files, save_final_manifest


def test_export_summary_files_token_accounting(tmp_path: Path) -> None:
    executed_rows = [
        {
            "pattern": "fake_pattern_1",
            "intensity": 1,
            "language": "en",
            "agent": "computeruse",
            "model": "gpt-4o",
            "outcome": "EC",
            "steps": 3,
            "duration_seconds": 2.5,
            "provider_latency_seconds": 1.1,
            "in_tokens": 150,
            "out_tokens": 50,
            "cost_usd": 0.0025,
        },
        {
            "pattern": "fake_pattern_2",
            "intensity": 2,
            "language": "en",
            "agent": "computeruse",
            "model": "gpt-4o",
            "outcome": "DC",
            "steps": 4,
            "duration_seconds": 3.0,
            "provider_latency_seconds": 1.2,
            # Legacy row with tokens_in / tokens_out for backwards compatibility testing
            "tokens_in": 250,
            "tokens_out": 75,
            "cost_usd": 0.0035,
        },
    ]

    csv_path, json_path = export_summary_files(
        run_id="test_run_123",
        results_dir=tmp_path,
        executed_rows=executed_rows,
        skipped_count=0,
        total_configs=2,
        start_time=100.0,
    )

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "in_tokens,out_tokens" in csv_text
    lines = csv_text.strip().splitlines()
    assert len(lines) == 3
    # Check row 1 has 150 and 50
    assert "150" in lines[1] and "50" in lines[1]
    # Check row 2 legacy fallback resolved 250 and 75 into canonical columns
    assert "250" in lines[2] and "75" in lines[2]

    json_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_data["total_in_tokens"] == 400
    assert json_data["total_out_tokens"] == 125
    assert json_data["total_tokens_in"] == 400
    assert json_data["total_tokens_out"] == 125


def test_save_final_manifest_token_accounting(tmp_path: Path) -> None:
    executed_rows = [
        {"in_tokens": 500, "out_tokens": 100, "outcome": "EC", "cost_usd": 0.01},
        {"tokens_in": 300, "tokens_out": 60, "outcome": "DF", "cost_usd": 0.005},
    ]

    manifest_path = save_final_manifest(
        run_id="test_manifest_456",
        results_dir=tmp_path,
        status="completed",
        executed_rows=executed_rows,
        skipped_count=0,
        total_configs=2,
        runtime_seconds=10.0,
    )

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["total_in_tokens"] == 800
    assert data["total_out_tokens"] == 160
    assert data["total_tokens_in"] == 800
    assert data["total_tokens_out"] == 160


def test_filter_configs_by_batch() -> None:
    import pytest
    from scripts.run_matrix import enumerate_benchmark_configs, filter_configs_by_batch

    all_configs = enumerate_benchmark_configs()
    assert len(all_configs) == 1560

    # Individual batch filters
    e1a = filter_configs_by_batch(all_configs, "e1a")
    assert len(e1a) == 480
    assert all(c.agent == "computeruse" and c.llm == "groq/llama-3.3-70b-versatile" and c.language == "en" and c.seed < 10 for c in e1a)

    spotcheck = filter_configs_by_batch(all_configs, "spotcheck")
    assert len(spotcheck) == 60
    assert all(c.llm == "groq/llama-3.1-8b-instant" for c in spotcheck)

    e1b = filter_configs_by_batch(all_configs, "e1b")
    assert len(e1b) == 480
    assert all(c.agent == "browseruse" for c in e1b)

    e2 = filter_configs_by_batch(all_configs, "e2")
    assert len(e2) == 540
    assert all(c.language in ("hi", "hinglish") or (c.agent == "computeruse" and c.llm == "groq/llama-3.3-70b-versatile" and c.seed >= 10) for c in e2)

    # All / Default
    assert len(filter_configs_by_batch(all_configs, "all")) == 1560

    # Comma-separated combination
    combo = filter_configs_by_batch(all_configs, "e1a,spotcheck,e2")
    assert len(combo) == 1080

    # Invalid batch token error
    with pytest.raises(ValueError, match="Invalid batch token"):
        filter_configs_by_batch(all_configs, "invalid_batch_name")

