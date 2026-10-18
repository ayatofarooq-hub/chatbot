"""Compare installed chat models against identical retrieved legal context."""

import copy
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import api
from app.citation_registry import filter_results_to_registered, load_registry
from app.settings_store import get_settings
from legal_rag import grounded_answer

QUESTION = "ما هي الجهة الحكومية التي بادرت برفع الطلب للتعامل مع كميات الشاي الموقوفة والتالفة؟"
REPORT = ROOT / "reports" / "tea-answer-comparison.json"


def main():
    captured = {}

    def capture(question, results, **kwargs):
        captured["results"] = results
        return {"answer": "diagnostic", "sources": [], "confidence": 0.0}

    with patch.object(api, "legal_rag_answer_from_results", side_effect=capture):
        api.answer_question(QUESTION)
    results = captured["results"]
    validated, warnings = filter_results_to_registered(results, registry=load_registry())
    sources = grounded_answer.extracted_sources(validated)
    context = grounded_answer.build_document_answer_context(validated, sources)
    settings = get_settings()
    report = {
        "question": QUESTION,
        "selected_sources": [s.public_dict() for s in sources],
        "registry_warnings": warnings,
        "context": context,
        "answers": [],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Captured retrieval; registered sources:", len(sources), "context characters:", len(context), flush=True)
    for model in ("qwen2.5:1.5b", "qwen2.5:3b"):
        current = copy.deepcopy(settings)
        current["model"].update(chat_model=model, auto_select_model=False, keep_alive=0)
        print("Comparing", model, flush=True)
        started = time.perf_counter()
        try:
            with patch.object(grounded_answer, "runtime_settings", return_value=current):
                answer = grounded_answer.answer_from_results(QUESTION, validated)
            record = {"model": model, "seconds": round(time.perf_counter() - started, 2), "result": answer}
        except Exception as error:
            record = {"model": model, "error": f"{type(error).__name__}: {error}"}
        report["answers"].append(record)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Finished", model, "in", round(time.perf_counter() - started, 2), "seconds", flush=True)


if __name__ == "__main__":
    main()
