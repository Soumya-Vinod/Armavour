import sys

sys.path.insert(0, ".")

from harness.config import enumerate_configs
from harness.runner import run_batch

PATTERN_TASKS = {
    "false_urgency": "fu_best",
    "confirm_shaming": "cs_donation",
}

configs = []
for pattern, task_id in PATTERN_TASKS.items():
    configs.extend(
        enumerate_configs(
            site="ticketing",
            task_id=task_id,
            patterns=[pattern],
            intensities=["subtle", "moderate", "aggressive"],
            languages=["en"],
            agents=["computeruse"],
            llms=["groq/llama-3.3-70b-versatile"],
            repeat_count=5,
        )
    )

print(f"Generated {len(configs)} configs")
run_batch(configs, run_id="pilot-soft-01")
