"""Run a batch of Arabic questions through the local legal chatbot."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chatbot import answer_with_qwen_3b
from app.text_encoding import repair_json_text


DEFAULT_INPUT = Path(r"C:\Users\lenovo\Downloads\questions_answers_ar.json")
DEFAULT_OUTPUT = Path("data") / "question_batch_results.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all questions in a JSON file through the chatbot."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to questions_answers_ar.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to save chatbot answers as JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of questions to run for testing. 0 means all.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from an existing output file instead of starting over.",
    )
    return parser.parse_args()


def load_questions(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload = repair_json_text(payload)
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list):
        raise ValueError("Input JSON must contain a 'questions' list.")
    return [
        item
        for item in questions
        if isinstance(item, dict) and str(item.get("question") or "").strip()
    ]


def save_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "count": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_existing_results(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    results = payload.get("results") if isinstance(payload, dict) else None
    return results if isinstance(results, list) else []


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    questions = load_questions(args.input)
    if args.limit > 0:
        questions = questions[: args.limit]

    results: list[dict] = load_existing_results(args.output) if args.resume else []
    completed_ids = {str(record.get("id")) for record in results}
    pending_questions = [
        item for item in questions if str(item.get("id", "")) not in completed_ids
    ]

    print(f"Loaded {len(questions)} questions from {args.input}", flush=True)
    if args.resume:
        print(f"Resuming after {len(results)} saved results.", flush=True)
    print(f"Saving results to {args.output}", flush=True)
    print("-" * 80, flush=True)

    for index, item in enumerate(pending_questions, start=len(results) + 1):
        question_id = item.get("id", index)
        question = str(item.get("question") or "").strip()
        expected_answer = str(item.get("answer") or "").strip()
        started_at = time.perf_counter()

        print(f"[{index}/{len(questions)}] ID {question_id}", flush=True)
        print(f"السؤال: {question}", flush=True)

        record = {
            "id": question_id,
            "question": question,
            "expected_answer": expected_answer,
            "chatbot_answer": "",
            "warnings": [],
            "status": "ok",
            "elapsed_seconds": 0.0,
        }
        try:
            answer = answer_with_qwen_3b(question)
            record["chatbot_answer"] = answer.content
            record["warnings"] = answer.warnings
            print(f"إجابة الشات بوت:\n{answer.content}", flush=True)
            if answer.warnings:
                print("تحذيرات:", flush=True)
                for warning in answer.warnings:
                    print(f"- {warning}", flush=True)
        except Exception as error:  # Keep the batch running after one failure.
            record["status"] = "error"
            record["error"] = str(error)
            print(f"خطأ: {error}", flush=True)
        finally:
            record["elapsed_seconds"] = round(time.perf_counter() - started_at, 2)
            results.append(record)
            save_results(args.output, results)
            print("-" * 80, flush=True)

    print(f"Finished {len(results)} questions.", flush=True)
    print(f"Results saved to {args.output}", flush=True)


if __name__ == "__main__":
    main()
