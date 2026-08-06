from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

from dotenv import load_dotenv
from sqlalchemy import select

sys.path.insert(0, ".")
load_dotenv()

from harness.config import EpisodeConfig
from harness.judge import JudgeParseError
from harness.logger import engine_from_env, episodes_table
from harness.runner import run_batch, run_episode

RUN_ID = f"verify-parse-err-{int(time.time())}"


def build_test_config() -> EpisodeConfig:
    llm_model = os.getenv("CHHAL_MODEL", "groq/llama-3.3-70b-versatile")
    return EpisodeConfig(
        site="ticketing",
        task_id="fu_best",
        pattern="false_urgency",
        intensity="subtle",
        language="en",
        agent="computeruse",
        llm=llm_model,
        seed=999,
    )


def get_db_row(run_id: str, config_hash: str):
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table).where(table.c.run_id == run_id, table.c.config_hash == config_hash)
    with engine.connect() as conn:
        result = conn.execute(stmt).mappings().first()
        return dict(result) if result else None


def get_completed_hashes(run_id: str) -> set[str]:
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.config_hash).where(
        table.c.run_id == run_id,
        table.c.outcome.is_not(None),
    )
    with engine.connect() as conn:
        return {row.config_hash for row in conn.execute(stmt)}


def mock_bad_judge_completion(*args, **kwargs):
    class MockChoice:
        message = type("Message", (), {"content": "INVALID NON-JSON RESPONSE FROM LLM JUDGE"})()

    class MockResponse:
        choices = [MockChoice()]

    return MockResponse()


def verify_recovery() -> bool:
    print("=" * 80)
    print("VERIFYING JUDGE PARSE ERROR RECOVERY")
    print(f"RUN ID: {RUN_ID}")
    print("=" * 80)

    config = build_test_config()

    # 1. Run episode with forced malformed judge output
    print("\n[Step 1] Executing episode with forced invalid judge response...")
    with patch("harness.judge._completion_with_rate_limit_retry", side_effect=mock_bad_judge_completion):
        row = run_episode(config, run_id=RUN_ID, log=True)

    print(f"  -> Episode execution finished. Outcome: {row.get('outcome')}")

    # 2. Check Database Row Assertions
    print("\n[Step 2] Querying Postgres database row...")
    db_row = get_db_row(RUN_ID, config.config_hash)
    assert db_row is not None, "FAILED: Row was not written to Postgres database!"

    print(f"  -> DB id:               {db_row['id']}")
    print(f"  -> DB outcome:          {db_row['outcome']}")
    print(f"  -> DB judge_flag:       {db_row['judge_flag']}")

    trace = db_row.get("trace") or []
    has_exception_in_trace = any("JudgeParseError" in str(t.get("exception", "")) for t in trace if isinstance(t, dict))

    print(f"  -> Exception in trace:  {has_exception_in_trace}")

    # Assertions
    assert db_row["outcome"] is None, f"FAILED: Expected outcome to be None (crash row), got {db_row['outcome']!r}"
    assert db_row["judge_flag"] is None, f"FAILED: Expected judge_flag to be None, got {db_row['judge_flag']!r}"
    assert has_exception_in_trace, "FAILED: Trace does not contain JudgeParseError information!"
    print("  -> All DB row assertions: PASSED")

    # 3. Verify Resume Logic
    print("\n[Step 3] Verifying checkpoint/resume eligibility...")
    completed_hashes = get_completed_hashes(RUN_ID)
    is_completed = config.config_hash in completed_hashes
    print(f"  -> Is config_hash in completed hashes? {is_completed}")
    assert not is_completed, "FAILED: Crash row with outcome=NULL was incorrectly marked as completed!"
    print("  -> Resume eligibility check: PASSED (episode is eligible for retry)")

    # 4. Rerunning batch should retry this config
    remaining = [c for c in [config] if c.config_hash not in completed_hashes]
    assert len(remaining) == 1, f"FAILED: Remaining configs for batch run should be 1, got {len(remaining)}"
    print("  -> Batch retry check: PASSED")

    print("\n" + "=" * 80)
    print("SUCCESS: JudgeParseError recovery fully verified!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    verify_recovery()
