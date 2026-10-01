def test_config_hash_matches_existing_e1a_row():
    """
    Pull a real config_hash from an existing E1a row in Postgres and
    re-enumerate that config with current code. Assert strings match.
    Proves backward compatibility is real, not just described.
    """
    import os
    import pytest
    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text
    from harness.config import EpisodeConfig

    from harness.runner import PRECHECK_PATTERN_TASKS
    pattern_tasks = dict(PRECHECK_PATTERN_TASKS)

    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    engine = create_engine(db_url)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT config_hash, site, pattern, intensity, language,
                   agent, llm, seed
            FROM episodes
            WHERE run_id LIKE '%e1%'
            AND outcome IS NOT NULL
            LIMIT 1
        """)).fetchone()

    assert row is not None, "No E1a rows found in DB"

    task_id = pattern_tasks.get(row.pattern, row.pattern)
    config = EpisodeConfig(
        site=row.site,
        pattern=row.pattern,
        intensity=row.intensity,
        language=row.language,
        agent=row.agent,
        llm=row.llm,
        seed=row.seed,
        task_id=task_id,
        instruction_language="en",
    )

    assert config.config_hash == row.config_hash, (
        f"Hash mismatch: DB has {row.config_hash!r}, "
        f"re-enumerated gives {config.config_hash!r}"
    )


def test_config_hash_instruction_language_en_equals_absent():
    """
    instruction_language='en' must hash identically to the field
    being absent (legacy behavior). This is the backward-compat
    invariant — if it breaks, completed_config_hashes() silently
    re-runs every E1 episode.
    """
    from harness.config import EpisodeConfig

    base_kwargs = dict(
        site="ticketing",
        pattern="basket_sneaking",
        intensity="moderate",
        language="en",
        agent="computeruse",
        llm="groq/llama-3.3-70b-versatile",
        seed=0,
        task_id="basket_sneaking_en_0",
    )

    config_with_en = EpisodeConfig(**base_kwargs, instruction_language="en")
    config_without = EpisodeConfig(**base_kwargs)  # defaults to "en"

    assert config_with_en.config_hash == config_without.config_hash, (
        "instruction_language='en' must hash identically to default"
    )