from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

import litellm
from litellm.exceptions import RateLimitError

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = Path(".checkpoints")
DEFAULT_CHECKPOINT_FILE = DEFAULT_CHECKPOINT_DIR / "provider_state.json"

RATE_LIMIT_ERROR_KEYWORDS = (
    "429",
    "ratelimiterror",
    "insufficient_quota",
    "quota exceeded",
    "daily limit exceeded",
    "exhausted credits",
    "rate_limit_exceeded",
    "rate limit",
)


class APIKeyPool:
    """Thread-safe, provider-agnostic pool for managing API key rotation and checkpoint state."""

    def __init__(
        self,
        provider: str = "groq",
        env_var: str = "GROQ_API_KEY",
        checkpoint_path: Path | str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.env_var = env_var
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else DEFAULT_CHECKPOINT_FILE
        self._lock = threading.Lock()
        self._keys: list[str] = self._load_keys_from_env()
        self._index: int = 0
        self._rotations_count: int = 0
        self._episodes_per_key: dict[int, int] = {}
        self.load_state()

    def _load_keys_from_env(self) -> list[str]:
        raw_val = os.getenv(self.env_var, "")
        if not raw_val:
            return []
        return [k.strip() for k in raw_val.split(",") if k.strip()]

    def refresh_keys_from_env(self) -> None:
        """Re-read keys from environment while holding lock."""
        with self._lock:
            self._keys = self._load_keys_from_env()
            if self._keys and self._index >= len(self._keys):
                self._index = 0

    def current_key(self) -> str | None:
        """Return current active API key string or None if pool is empty."""
        with self._lock:
            if not self._keys:
                self._keys = self._load_keys_from_env()
                if not self._keys:
                    return None
            idx = self._index % len(self._keys)
            return self._keys[idx]

    def current_index(self) -> int:
        """Return 0-based index of active key."""
        with self._lock:
            return self._index

    def total_keys(self) -> int:
        """Return total number of keys in pool."""
        with self._lock:
            return len(self._keys)

    def record_episode(self) -> None:
        """Record an episode execution against the currently active 1-based key index."""
        with self._lock:
            active_1based = self._index + 1
            self._episodes_per_key[active_1based] = self._episodes_per_key.get(active_1based, 0) + 1

    def get_rotation_summary(self) -> dict[str, Any]:
        """Return summary of API key rotations and per-key episode execution counts."""
        with self._lock:
            return {
                "total_rotations": self._rotations_count,
                "keys_used": sorted(list(self._episodes_per_key.keys())),
                "episodes_per_key": {f"key_{k}": v for k, v in sorted(self._episodes_per_key.items())},
            }

    def rotate(self) -> str | None:
        """Rotate to next key in pool, persist checkpoint state, and return new active key."""
        with self._lock:
            if not self._keys:
                return None
            old_idx = self._index
            self._index = (self._index + 1) % len(self._keys)
            self._rotations_count += 1
            provider_name = self.provider.capitalize()
            total = len(self._keys)
            logger.info(
                f"Rate limit encountered on {provider_name} key {old_idx + 1}/{total}. "
                f"Switching to key {self._index + 1}/{total}"
            )
            print(f"Rate limit encountered on key {old_idx + 1}/{total}")
            print(f"Switching to key {self._index + 1}/{total}")
            self._save_state_locked()
            return self._keys[self._index]

    def exhausted(self, attempted_count: int) -> bool:
        """Return True if attempted_count has reached or exceeded total key count."""
        with self._lock:
            if not self._keys:
                return True
            return attempted_count >= len(self._keys)

    def reset(self) -> None:
        """Reset key index back to 0 and persist state."""
        with self._lock:
            self._index = 0
            self._save_state_locked()

    def save_state(self) -> None:
        """Public thread-safe save state method."""
        with self._lock:
            self._save_state_locked()

    def _save_state_locked(self) -> None:
        """Internal save state holding lock. Atomic write to survive crashes without storing key strings."""
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            existing: dict[str, Any] = {}
            if self.checkpoint_path.exists():
                try:
                    existing = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                    if not isinstance(existing, dict):
                        existing = {}
                except Exception:
                    existing = {}

            existing[self.provider] = {"current_key_index": self._index}

            dir_path = self.checkpoint_path.parent
            with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False, encoding="utf-8") as tf:
                json.dump(existing, tf, indent=4)
                temp_name = tf.name

            os.replace(temp_name, self.checkpoint_path)
            logger.info(f"Checkpoint updated:\n{self.provider} -> key {self._index + 1}")
            print(f"Checkpoint updated:\n{self.provider} -> key {self._index + 1}")
        except Exception as exc:
            logger.warning(f"Failed to save provider state checkpoint: {exc}")

    def load_state(self) -> None:
        """Load 0-based key index from checkpoint file if present."""
        with self._lock:
            if not self.checkpoint_path.exists():
                self._index = 0
                return
            try:
                data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    p_data = data.get(self.provider, {})
                    if isinstance(p_data, dict):
                        idx = p_data.get("current_key_index", 0)
                        if isinstance(idx, int) and idx >= 0:
                            if self._keys:
                                self._index = idx % len(self._keys)
                                logger.info(
                                    f"Restored provider state:\n{self.provider} key {self._index + 1}/{len(self._keys)}"
                                )
                                print(
                                    f"Restored provider state:\n{self.provider} key {self._index + 1}/{len(self._keys)}"
                                )
                            else:
                                self._index = idx
            except Exception as exc:
                logger.warning(f"Failed to load provider state checkpoint: {exc}")
                self._index = 0


# Global singleton pool registry for thread-safe shared key management
_POOLS: dict[str, APIKeyPool] = {}
_POOLS_LOCK = threading.Lock()


def get_key_pool(
    provider: str = "groq",
    env_var: str = "GROQ_API_KEY",
    checkpoint_path: Path | str | None = None,
) -> APIKeyPool:
    provider_key = provider.lower()
    with _POOLS_LOCK:
        if provider_key not in _POOLS:
            _POOLS[provider_key] = APIKeyPool(
                provider=provider,
                env_var=env_var,
                checkpoint_path=checkpoint_path,
            )
        pool = _POOLS[provider_key]
        pool.refresh_keys_from_env()
        return pool


def is_rate_limit_error(exc: Exception) -> bool:
    """Determine if an exception represents a rate limit / quota exhaustion error."""
    if isinstance(exc, RateLimitError):
        return True
    msg = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    return any(kw in msg or kw in exc_type for kw in RATE_LIMIT_ERROR_KEYWORDS)


def _infer_provider_and_env(model: str, default_provider: str = "groq", default_env: str = "GROQ_API_KEY") -> tuple[str, str]:
    m_lower = str(model or "").lower()
    if m_lower.startswith("openrouter/"):
        return "openrouter", "OPENROUTER_API_KEY"
    if m_lower.startswith("anthropic/"):
        return "anthropic", "ANTHROPIC_API_KEY"
    if m_lower.startswith("gemini/"):
        return "gemini", "GEMINI_API_KEY"
    if m_lower.startswith("openai/"):
        return "openai", "OPENAI_API_KEY"
    if m_lower.startswith("groq/"):
        return "groq", "GROQ_API_KEY"
    return default_provider, default_env


def completion_with_rotation(
    model: str,
    messages: list[dict[str, Any]],
    *,
    pool: APIKeyPool | None = None,
    provider: str = "groq",
    env_var: str = "GROQ_API_KEY",
    **kwargs: Any,
) -> Any:
    """Execute litellm.completion with automatic API key rotation on rate limits."""
    if pool is None:
        p_name, p_env = _infer_provider_and_env(model, provider, env_var)
        pool = get_key_pool(provider=p_name, env_var=p_env)

    attempted = 0
    total_keys = pool.total_keys()
    if total_keys == 0:
        # If env is empty or not parsed into pool, fallback to default litellm call
        return litellm.completion(model=model, messages=messages, **kwargs)

    last_rate_limit_exc: Exception | None = None

    while attempted < total_keys:
        active_key = pool.current_key()
        call_kwargs = dict(kwargs)
        if active_key:
            call_kwargs["api_key"] = active_key

        try:
            return litellm.completion(model=model, messages=messages, **call_kwargs)
        except Exception as exc:
            if not is_rate_limit_error(exc):
                # Non-rate limit error (e.g. 401 auth, 400 bad prompt, 500 server bug) -> raise immediately
                raise

            last_rate_limit_exc = exc
            attempted += 1

            if pool.exhausted(attempted):
                logger.error(f"All {pool.provider.capitalize()} API keys exhausted.")
                print(f"All {pool.provider.capitalize()} API keys exhausted.")
                raise exc

            pool.rotate()

    if last_rate_limit_exc:
        raise last_rate_limit_exc
