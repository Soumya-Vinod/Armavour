from __future__ import annotations

import pytest
from harness.config import TASK_PROMPTS, TRANSLATIONS, EpisodeConfig, get_localized_instruction, load_task_prompt


def test_get_localized_instruction_non_identity() -> None:
    for task_id, en_prompt in TASK_PROMPTS.items():
        hi_prompt = get_localized_instruction(en_prompt, "hi")
        hinglish_prompt = get_localized_instruction(en_prompt, "hinglish")

        assert en_prompt != hi_prompt, f"Hindi prompt identical to English for {task_id}"
        assert en_prompt != hinglish_prompt, f"Hinglish prompt identical to English for {task_id}"
        assert hi_prompt != hinglish_prompt, f"Hindi prompt identical to Hinglish for {task_id}"

        # Verify fallback for unknown language or 'en'
        assert get_localized_instruction(en_prompt, "en") == en_prompt
        assert get_localized_instruction(en_prompt, "fr") == en_prompt


def test_get_localized_instruction_by_task_id() -> None:
    for task_id in TASK_PROMPTS:
        en_prompt = load_task_prompt(task_id)
        hi_prompt = get_localized_instruction(task_id, "hi")
        hinglish_prompt = get_localized_instruction(task_id, "hinglish")

        assert hi_prompt != en_prompt
        assert hinglish_prompt != en_prompt
        assert hi_prompt != hinglish_prompt


def test_episode_config_language_fields() -> None:
    config = EpisodeConfig(
        site="ticketing",
        task_id="bs_ticket",
        pattern="basket_sneaking",
        intensity="moderate",
        ui_language="hi",
        instruction_language="hi",
        agent="computeruse",
        llm="groq/llama-3.3-70b-versatile",
        seed=20,
    )
    assert config.ui_language == "hi"
    assert config.language == "hi"  # Alias
    assert config.instruction_language == "hi"
    assert config.testbed_payload()["lang"] == "hi"

    # Backward compatibility with keyword argument language="en"
    legacy_config = EpisodeConfig(
        site="ticketing",
        task_id="bs_ticket",
        pattern="basket_sneaking",
        intensity="moderate",
        language="en",
        agent="computeruse",
        llm="groq/llama-3.3-70b-versatile",
        seed=0,
    )
    assert legacy_config.ui_language == "en"
    assert legacy_config.instruction_language == "en"
