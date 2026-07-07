from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Iterable, Sequence

VALID_INTENSITIES = {"subtle", "moderate", "aggressive", "control"}
TASKS_PATH = Path(__file__).resolve().parent.parent / "docs" / "specs" / "tasks.md"


@dataclass(frozen=True)
class EpisodeConfig:
    site: str
    task_id: str
    pattern: str
    intensity: str
    language: str
    agent: str
    llm: str
    seed: int

    def __post_init__(self) -> None:
        if self.intensity not in VALID_INTENSITIES:
            raise ValueError(
                f"intensity must be one of {sorted(VALID_INTENSITIES)}; got {self.intensity!r}"
            )

    @property
    def config_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, str | int]:
        payload = asdict(self)
        payload["config_hash"] = self.config_hash
        return payload

    def testbed_payload(self) -> dict[str, str | int]:
        return {
            "site": self.site,
            "task_id": self.task_id,
            "pattern": self.pattern,
            "intensity": self.intensity,
            "lang": self.language,
            "seed": self.seed,
        }


def enumerate_configs(
    *,
    site: str,
    task_id: str,
    patterns: Sequence[str],
    intensities: Sequence[str],
    languages: Sequence[str],
    agents: Sequence[str],
    llms: Sequence[str],
    repeat_count: int,
    seed_start: int = 0,
    target_episode_count: int | None = None,
    budget_cap_usd: float | None = None,
    estimated_cost_per_episode_usd: float | None = None,
) -> list[EpisodeConfig]:
    if repeat_count < 1:
        raise ValueError("repeat_count must be >= 1")

    configs = [
        EpisodeConfig(
            site=site,
            task_id=task_id,
            pattern=pattern,
            intensity=intensity,
            language=language,
            agent=agent,
            llm=llm,
            seed=seed_start + repeat,
        )
        for pattern, intensity, language, agent, llm, repeat in product(
            patterns,
            intensities,
            languages,
            agents,
            llms,
            range(repeat_count),
        )
    ]

    cap = target_episode_count
    if budget_cap_usd is not None:
        if estimated_cost_per_episode_usd is None or estimated_cost_per_episode_usd <= 0:
            raise ValueError("estimated_cost_per_episode_usd must be positive when budget_cap_usd is set")
        budget_count = int(budget_cap_usd // estimated_cost_per_episode_usd)
        cap = budget_count if cap is None else min(cap, budget_count)

    if cap is not None:
        configs = downsample(configs, cap)

    return configs


def downsample(configs: Iterable[EpisodeConfig], target_count: int) -> list[EpisodeConfig]:
    configs = list(configs)
    if target_count < 0:
        raise ValueError("target_count must be >= 0")
    if target_count >= len(configs):
        return configs
    return sorted(configs, key=lambda config: config.config_hash)[:target_count]


def load_task_prompt(task_id: str, *, tasks_path: Path = TASKS_PATH) -> str:
    if not tasks_path.exists():
        raise FileNotFoundError(f"task prompt source not found: {tasks_path}")

    row_re = re.compile(
        r"^\|\s*`(?P<task_id>[^`]+)`\s*\|\s*(?P<pattern>[^|]+?)\s*\|\s*(?P<prompt>.+?)\s*\|\s*$"
    )
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        match = row_re.match(line)
        if match and match.group("task_id") == task_id:
            return match.group("prompt").strip()

    # TODO: replace markdown-table parsing with a structured task registry once
    # Dev 1 finalises multilingual prompt storage.
    raise KeyError(f"task_id not found in {tasks_path}: {task_id}")


def demo_configs() -> list[EpisodeConfig]:
    return enumerate_configs(
        site="ticketing",
        task_id="bs_ticket",
        patterns=["basket_sneaking"],
        intensities=["control", "subtle", "moderate", "aggressive"],
        languages=["en"],
        agents=["computeruse"],
        llms=["claude-sonnet-4-5-20250929"],
        repeat_count=2,
        target_episode_count=5,
    )


def demo() -> None:
    configs = demo_configs()
    rerun = demo_configs()
    stable = [config.config_hash for config in configs] == [config.config_hash for config in rerun]
    for config in configs:
        print(json.dumps(config.to_dict(), sort_keys=True))
    print(f"hashes_stable={stable}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enumerate Armavour episode configs.")
    parser.add_argument("--demo", action="store_true", help="Print a deterministic 20-config sample.")
    args = parser.parse_args()
    if args.demo:
        demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
