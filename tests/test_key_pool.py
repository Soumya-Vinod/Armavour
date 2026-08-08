from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from litellm.exceptions import RateLimitError

from harness.providers.key_pool import APIKeyPool, completion_with_rotation, is_rate_limit_error


def test_single_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_single_key_123")
    ckpt = tmp_path / "provider_state.json"
    pool = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)

    assert pool.total_keys() == 1
    assert pool.current_key() == "gsk_single_key_123"
    assert pool.current_index() == 0


def test_multiple_keys_and_whitespace_trimming_and_empty_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "  gsk_key1 ,  , gsk_key2  ,, gsk_key3  ")
    ckpt = tmp_path / "provider_state.json"
    pool = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)

    assert pool.total_keys() == 3
    assert pool.current_key() == "gsk_key1"
    assert pool.current_index() == 0


def test_rotation_order_and_checkpoint_persistence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "key_a,key_b,key_c")
    ckpt = tmp_path / "provider_state.json"
    pool = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)

    assert pool.current_key() == "key_a"
    assert pool.current_index() == 0

    # Rotate 1: key_a -> key_b (index 1)
    k2 = pool.rotate()
    assert k2 == "key_b"
    assert pool.current_index() == 1
    assert ckpt.exists()
    state1 = json.loads(ckpt.read_text(encoding="utf-8"))
    assert state1["groq"]["current_key_index"] == 1

    # Rotate 2: key_b -> key_c (index 2)
    k3 = pool.rotate()
    assert k3 == "key_c"
    assert pool.current_index() == 2
    state2 = json.loads(ckpt.read_text(encoding="utf-8"))
    assert state2["groq"]["current_key_index"] == 2

    # Rotate 3: wrap around key_c -> key_a (index 0)
    k1 = pool.rotate()
    assert k1 == "key_a"
    assert pool.current_index() == 0

    captured = capsys.readouterr().out
    assert "key_a" not in captured
    assert "key_b" not in captured
    assert "key_c" not in captured
    assert "Switching to key 2/3" in captured


def test_restore_after_restart(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "key_1,key_2,key_3")
    ckpt = tmp_path / "provider_state.json"

    # Instance 1 rotates to index 2
    pool1 = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)
    pool1.rotate()  # -> index 1
    pool1.rotate()  # -> index 2
    assert pool1.current_index() == 2

    # Instance 2 loads saved checkpoint from disk
    pool2 = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)
    assert pool2.current_index() == 2
    assert pool2.current_key() == "key_3"


def test_rate_limit_detection() -> None:
    exc1 = RateLimitError(message="Rate limit reached", model="groq/llama-3.3-70b-versatile", llm_provider="groq")  # type: ignore
    exc2 = RuntimeError("HTTP 429: insufficient_quota for key")
    exc3 = ValueError("Invalid prompt format")

    assert is_rate_limit_error(exc1) is True
    assert is_rate_limit_error(exc2) is True
    assert is_rate_limit_error(exc3) is False


def test_completion_with_rotation_retries_and_exhaustion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "key_1,key_2,key_3")
    ckpt = tmp_path / "provider_state.json"
    pool = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)

    # Mock litellm.completion to fail with RateLimitError on first 2 calls, then succeed on key 3
    calls: list[str | None] = []

    def mock_completion(*args: object, **kwargs: object) -> str:
        api_key = str(kwargs.get("api_key"))
        calls.append(api_key)
        if len(calls) < 3:
            raise RateLimitError(
                message=f"Rate limit for {api_key}",
                model="groq/llama-3.3-70b-versatile",
                llm_provider="groq",
            )
        return "SUCCESS_RESPONSE"

    with patch("harness.providers.key_pool.litellm.completion", side_effect=mock_completion):
        res = completion_with_rotation(model="groq/llama-3.3-70b-versatile", messages=[], pool=pool)

    assert res == "SUCCESS_RESPONSE"
    assert len(calls) == 3
    assert calls == ["key_1", "key_2", "key_3"]
    assert pool.current_index() == 2  # Settled on key 3

    out = capsys.readouterr().out
    assert "key_1" not in out
    assert "key_2" not in out
    assert "key_3" not in out
    assert "Switching to key 2/3" in out


def test_exhaustion_and_no_infinite_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "key_1,key_2")
    ckpt = tmp_path / "provider_state.json"
    pool = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)

    attempts = 0

    def mock_failing_completion(*args: object, **kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        raise RateLimitError(
            message="429 Rate limit exceeded",
            model="groq/llama-3.3-70b-versatile",
            llm_provider="groq",
        )

    with (
        patch("harness.providers.key_pool.litellm.completion", side_effect=mock_failing_completion),
        pytest.raises(RateLimitError),
    ):
        completion_with_rotation(model="groq/llama-3.3-70b-versatile", messages=[], pool=pool)

    # Exactly 2 attempts (total_keys=2), no infinite loop!
    assert attempts == 2


def test_non_rate_limit_error_does_not_rotate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "key_1,key_2")
    ckpt = tmp_path / "provider_state.json"
    pool = APIKeyPool(provider="groq", env_var="GROQ_API_KEY", checkpoint_path=ckpt)

    def mock_bad_request(*args: object, **kwargs: object) -> None:
        raise ValueError("400 Bad Request: prompt contains invalid tokens")

    with (
        patch("harness.providers.key_pool.litellm.completion", side_effect=mock_bad_request),
        pytest.raises(ValueError, match="400 Bad Request"),
    ):
        completion_with_rotation(model="groq/llama-3.3-70b-versatile", messages=[], pool=pool)

    # Should NOT rotate on 400 Bad Request!
    assert pool.current_index() == 0
