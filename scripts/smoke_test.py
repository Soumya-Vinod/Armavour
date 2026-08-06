from __future__ import annotations

import os
import sys
import time
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select

sys.path.insert(0, ".")

from harness.config import EpisodeConfig, enumerate_configs
from harness.logger import engine_from_env, episodes_table
from harness.runner import run_batch

load_dotenv()

RUN_ID = f"smoke-e2e-{int(time.time())}"


def build_smoke_configs() -> list[EpisodeConfig]:
    llm_model = os.getenv("CHHAL_MODEL", "groq/llama-3.3-70b-versatile")
    configs = []

    # 1. Oracle-scored pattern (basket_sneaking) - 3 configs
    configs.extend(
        enumerate_configs(
            site="ticketing",
            task_id="bs_ticket",
            patterns=["basket_sneaking"],
            intensities=["subtle", "moderate", "aggressive"],
            languages=["en"],
            agents=["computeruse"],
            llms=[llm_model],
            repeat_count=1,
            seed_start=100,
        )
    )

    # 2. Judge-scored pattern (false_urgency) - 3 configs
    configs.extend(
        enumerate_configs(
            site="ticketing",
            task_id="fu_best",
            patterns=["false_urgency"],
            intensities=["subtle", "moderate", "aggressive"],
            languages=["en"],
            agents=["computeruse"],
            llms=[llm_model],
            repeat_count=1,
            seed_start=200,
        )
    )

    return configs


def get_completed_hashes(run_id: str) -> set[str]:
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.config_hash).where(
        table.c.run_id == run_id,
        table.c.outcome.is_not(None),
    )
    with engine.connect() as conn:
        return {row.config_hash for row in conn.execute(stmt)}


def get_run_rows(run_id: str) -> list[dict[str, Any]]:
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table).where(table.c.run_id == run_id).order_by(table.c.id)
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]


def main() -> dict[str, Any]:
    print("=" * 80)
    print("ARMVOUR END-TO-END SMOKE TEST")
    print(f"RUN ID: {RUN_ID}")
    print("=" * 80)

    start_time = time.time()
    warnings: list[str] = []
    failed_contracts: list[str] = []

    # Step 1: Config Generation & Hash Determinism
    configs = build_smoke_configs()
    configs_repeat = build_smoke_configs()
    print(f"\n[1/5] Config Generation: Generated {len(configs)} configs.")
    
    hashes_original = [c.config_hash for c in configs]
    hashes_repeat = [c.config_hash for c in configs_repeat]
    if hashes_original != hashes_repeat:
        failed_contracts.append("Contract 1 (Episode Config): config_hash non-deterministic across enumerations")
    else:
        print("  -> Deterministic config_hash check: PASSED")

    # Step 2: Checkpoint Verification - Phase 1 (Interrupted Run)
    print("\n[2/5] Execution Phase 1: Running with simulated interruption after 3 episodes...")
    interrupted_count = 0

    def interrupt_after_3(index: int, config: EpisodeConfig, row: dict[str, Any]) -> None:
        nonlocal interrupted_count
        interrupted_count += 1
        print(f"  Completed episode {index}/6: pattern={config.pattern}, intensity={config.intensity}, outcome={row.get('outcome')}")
        if interrupted_count >= 3:
            raise KeyboardInterrupt("Simulated checkpoint interruption")

    try:
        run_batch(
            configs,
            run_id=RUN_ID,
            log=True,
            on_episode_end=interrupt_after_3,
        )
    except KeyboardInterrupt:
        print("  -> Phase 1 interrupted as expected.")

    phase1_completed = get_completed_hashes(RUN_ID)
    print(f"  -> Postgres verification: Found {len(phase1_completed)} completed rows in DB.")
    if len(phase1_completed) != 3:
        warnings.append(f"Expected 3 completed rows after Phase 1 interruption, found {len(phase1_completed)}")

    # Step 3: Checkpoint Verification - Phase 2 (Resumed Run)
    print("\n[3/5] Execution Phase 2: Resuming batch from Postgres checkpoint...")
    completed_before_resume = get_completed_hashes(RUN_ID)
    remaining_configs = [c for c in configs if c.config_hash not in completed_before_resume]
    print(f"  -> Skipped {len(completed_before_resume)} completed configs; {len(remaining_configs)} remaining.")

    if len(remaining_configs) != 3:
        warnings.append(f"Expected 3 remaining configs for resume, got {len(remaining_configs)}")

    def print_resumed(index: int, config: EpisodeConfig, row: dict[str, Any]) -> None:
        print(f"  Resumed episode {index}/{len(remaining_configs)}: pattern={config.pattern}, intensity={config.intensity}, outcome={row.get('outcome')}")

    run_batch(
        remaining_configs,
        run_id=RUN_ID,
        log=True,
        on_episode_end=print_resumed,
    )

    all_completed = get_completed_hashes(RUN_ID)
    print(f"  -> Phase 2 finished. Total completed rows in DB: {len(all_completed)}/6.")

    # Step 4: Postgres & Pipeline Deep Verification
    print("\n[4/5] Pipeline Component Verification:")
    rows = get_run_rows(RUN_ID)
    
    total_in_tokens = 0
    total_out_tokens = 0
    total_cost_usd = Decimal("0.0")
    pass_count = 0
    fail_count = 0
    crash_count = 0

    for i, row in enumerate(rows, start=1):
        total_in_tokens += row.get("in_tokens", 0) or 0
        total_out_tokens += row.get("out_tokens", 0) or 0
        if row.get("cost_usd"):
            total_cost_usd += Decimal(str(row["cost_usd"]))

        outcome = row.get("outcome")
        pattern = row.get("pattern")
        trace = row.get("trace") or []
        judge_flag = row.get("judge_flag")
        judge_evidence = row.get("judge_evidence")

        if outcome in ("EC", "EF"):
            pass_count += 1
        elif outcome in ("DC", "DF"):
            fail_count += 1
        else:
            crash_count += 1

        print(f"  Episode {i}: pattern={pattern}, intensity={row['intensity']}, outcome={outcome}, steps={row['steps']}, tokens={row['in_tokens']}+{row['out_tokens']}, cost=${row['cost_usd']}")

        # Component Validations
        duration = row.get("duration_seconds")
        if duration is None or float(duration) <= 0:
            failed_contracts.append(f"Episode {i} ({pattern}): duration_seconds not properly recorded: {duration!r}")
        prov_lat = row.get("provider_latency_seconds")
        if prov_lat is None or float(prov_lat) < 0:
            failed_contracts.append(f"Episode {i} ({pattern}): provider_latency_seconds not properly recorded: {prov_lat!r}")
        if not trace:
            failed_contracts.append(f"Episode {i} ({pattern}): trace array is empty")
        if pattern == "false_urgency" and outcome is not None:
            if judge_flag is None or judge_evidence is None:
                failed_contracts.append(f"Contract 5 (Judge Rubric): Soft pattern '{pattern}' missing judge_flag/judge_evidence")
        if pattern == "basket_sneaking" and outcome is not None:
            if judge_flag is not None:
                warnings.append(f"Hard pattern '{pattern}' unexpectedly set judge_flag")

    elapsed_time_s = time.time() - start_time

    # Step 5: Summary Report
    report = {
        "run_id": RUN_ID,
        "episodes_attempted": len(configs),
        "episodes_completed": len(rows),
        "outcomes": {
            "pass": pass_count,
            "fail": fail_count,
            "crash": crash_count,
        },
        "execution_time_seconds": round(elapsed_time_s, 2),
        "total_in_tokens": total_in_tokens,
        "total_out_tokens": total_out_tokens,
        "total_cost_usd": str(total_cost_usd),
        "warnings": warnings,
        "failed_contracts": failed_contracts,
        "status": "PASS" if len(rows) == len(configs) and not failed_contracts and crash_count == 0 else "FAIL",
    }

    print("\n" + "=" * 80)
    print("SMOKE TEST REPORT")
    print("=" * 80)
    print(f"Status:                 {report['status']}")
    print(f"Episodes Attempted:     {report['episodes_attempted']}")
    print(f"Episodes Completed:     {report['episodes_completed']}")
    print(f"Outcomes:               Pass={pass_count}, Fail={fail_count}, Crash={crash_count}")
    print(f"Execution Time:         {report['execution_time_seconds']} s")
    print(f"Token Accounting:       In={total_in_tokens}, Out={total_out_tokens}")
    print(f"Estimated Cost:         ${report['total_cost_usd']}")
    print(f"Warnings:               {warnings if warnings else 'None'}")
    print(f"Failed Contracts:       {failed_contracts if failed_contracts else 'None'}")
    print("=" * 80)

    return report


if __name__ == "__main__":
    main()
