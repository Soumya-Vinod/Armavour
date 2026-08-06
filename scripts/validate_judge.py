from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv()

from harness.judge import JudgeParseError, judge

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "judge_validation_samples.json"


def evaluate_dataset(dataset_path: Path) -> dict[str, Any]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Validation dataset not found at {dataset_path}")

    samples = json.loads(dataset_path.read_text(encoding="utf-8"))

    tp = 0  # Actual Pos, Predicted Pos
    fn = 0  # Actual Pos, Predicted Neg
    fp = 0  # Actual Neg, Predicted Pos
    tn = 0  # Actual Neg, Predicted Neg
    parse_errors = 0

    incorrect_cases: list[dict[str, Any]] = []

    print(f"Evaluating {len(samples)} validation cases through judge pipeline...")

    for i, sample in enumerate(samples, start=1):
        sample_id = sample.get("id", f"sample_{i}")
        pattern = sample["pattern"]
        trace = sample.get("trace", [])
        task_prompt = sample.get("task_prompt", "")
        oracle_result = sample.get("oracle_result", {})
        extracted_elements = sample.get("extracted_elements", [])
        expected_flag = bool(sample["expected_judge_flag"])

        print(f"  [{i}/{len(samples)}] Testing {sample_id} ({pattern})...", end="", flush=True)

        try:
            res = judge(
                pattern=pattern,
                trace=trace,
                final_screen=b"",
                task_prompt=task_prompt,
                oracle_result=oracle_result,
                extracted_elements=extracted_elements,
            )
            predicted_flag = bool(res["judge_flag"])
            evidence = str(res.get("judge_evidence", ""))

            if expected_flag and predicted_flag:
                tp += 1
                print(" OK")
            elif not expected_flag and not predicted_flag:
                tn += 1
                print(" OK")
            elif not expected_flag and predicted_flag:
                fp += 1
                print(" INCORRECT (False Positive)")
                incorrect_cases.append(
                    {
                        "id": sample_id,
                        "pattern": pattern,
                        "expected": expected_flag,
                        "predicted": predicted_flag,
                        "evidence": evidence,
                        "reason": "False Positive: Judge flagged pattern influence when expected safe.",
                    }
                )
            else:
                fn += 1
                print(" INCORRECT (False Negative)")
                incorrect_cases.append(
                    {
                        "id": sample_id,
                        "pattern": pattern,
                        "expected": expected_flag,
                        "predicted": predicted_flag,
                        "evidence": evidence,
                        "reason": "False Negative: Judge missed pattern influence when expected flagged.",
                    }
                )
        except JudgeParseError as err:
            parse_errors += 1
            print(" PARSE ERROR")
            incorrect_cases.append(
                {
                    "id": sample_id,
                    "pattern": pattern,
                    "expected": expected_flag,
                    "predicted": "ERROR",
                    "evidence": str(err),
                    "reason": f"JudgeParseError: {err}",
                }
            )

    total = len(samples)
    correct = tp + tn
    incorrect = fp + fn + parse_errors
    accuracy = (correct / total * 100.0) if total > 0 else 0.0

    # Note on Methodology:
    # Overall Accuracy is evaluated over ALL attempted cases (where parse errors count as unparseable/incorrect).
    # Precision, Recall, and F1 Score are classification metrics computed over successfully parsed predictions in the confusion matrix.
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "parse_errors": parse_errors,
        "accuracy": round(accuracy, 2),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "tn": tn,
        "incorrect_cases": incorrect_cases,
    }


def print_report(metrics: dict[str, Any]) -> None:
    print("\n" + "-" * 48)
    print(f"Cases: {metrics['total']}")
    print()
    print(f"Correct:      {metrics['correct']}")
    print(f"Incorrect:    {metrics['incorrect']}")
    print(f"Parse Errors: {metrics['parse_errors']}")
    print()
    print(f"Accuracy:     {metrics['accuracy']:.1f}%  (Overall across all {metrics['total']} cases)")
    print(f"Precision:    {metrics['precision']:.4f}  (On valid parsed predictions)")
    print(f"Recall:       {metrics['recall']:.4f}  (On valid parsed predictions)")
    print(f"F1 Score:     {metrics['f1_score']:.4f}  (On valid parsed predictions)")
    print()
    print(f"False Positives: {metrics['fp']}")
    print(f"False Negatives: {metrics['fn']}")
    print()
    print("Confusion Matrix (Valid Parsed Predictions)")
    print(f"{'':15} {'Predicted Pos':15} {'Predicted Neg':15}")
    print(f"{'Actual Pos':15} {metrics['tp']:<15} {metrics['fn']:<15}")
    print(f"{'Actual Neg':15} {metrics['fp']:<15} {metrics['tn']:<15}")
    print("-" * 48)

    if metrics["incorrect_cases"]:
        print("\nIncorrect cases:")
        for case in metrics["incorrect_cases"]:
            print(f"- [{case['id']}] Expected flag={case['expected']}, got {case['predicted']}")
            print(f"  Reason: {case['reason']}")
            print(f"  Evidence: {case['evidence']}")
    print("-" * 48)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Armavour Judge LLM pipeline accuracy.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to JSON validation dataset.",
    )
    args = parser.parse_args()

    metrics = evaluate_dataset(args.dataset)
    print_report(metrics)


if __name__ == "__main__":
    main()
