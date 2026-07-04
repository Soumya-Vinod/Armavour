from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import product
from typing import Iterable, Sequence


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
            "language": self.language,
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


def demo() -> None:
    configs = enumerate_configs(
        site="spike",
        task_id="checkout_ticket",
        patterns=["basket_sneaking", "false_urgency", "confirm_shaming"],
        intensities=["low", "moderate", "high"],
        languages=["en", "hi", "hinglish"],
        agents=["computeruse", "browseruse"],
        llms=["claude-sonnet-4-5"],
        repeat_count=3,
        target_episode_count=20,
    )
    rerun = enumerate_configs(
        site="spike",
        task_id="checkout_ticket",
        patterns=["basket_sneaking", "false_urgency", "confirm_shaming"],
        intensities=["low", "moderate", "high"],
        languages=["en", "hi", "hinglish"],
        agents=["computeruse", "browseruse"],
        llms=["claude-sonnet-4-5"],
        repeat_count=3,
        target_episode_count=20,
    )
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
