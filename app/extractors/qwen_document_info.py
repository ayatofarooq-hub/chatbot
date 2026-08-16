"""Extract limited document information with Qwen 1.5B."""

from dataclasses import dataclass, field
import json
import re

from app.config import DOCUMENT_INFO_MODEL, OLLAMA_KEEP_ALIVE


@dataclass
class DocumentInfo:
    title: str = ""
    document_type: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    mentioned_laws: list[str] = field(default_factory=list)
    mentioned_decisions: list[str] = field(default_factory=list)
    constitution: list[str] = field(default_factory=list)
    legal_references: list[str] = field(default_factory=list)


def build_document_info_prompt(text: str) -> str:
    """Build the only prompt sent to Qwen for document information."""

    return "\n".join(
        [
            "استخرج المعلومات التالية فقط، وأعد النتيجة بصيغة JSON فقط:",
            "",
            '- "title": عنوان الوثيقة',
            '- "document_type": نوع الوثيقة',
            '- "summary": ملخص من سطرين',
            "- keywords",
            "- entities: وزارة، مجلس الوزراء، هيئة، محكمة فقط",
            '- "mentioned_laws": القوانين المذكورة',
            '- "mentioned_decisions": القرارات المذكورة',
            '- "constitution": الدستور',
            '- "legal_references": الإحالات القانونية',
            "",
            "لا تستخرج الأرقام.",
            "",
            "النص:",
            text,
        ]
    )


def as_list(value: object) -> list[str]:
    """Normalize parsed Qwen values into a list of strings."""

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,،\n]", value) if item.strip()]
    return []


def parse_document_info_response(content: str) -> DocumentInfo:
    """Parse Qwen output into structured document information."""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    return DocumentInfo(
        title=str(payload.get("title", "")).strip(),
        document_type=str(payload.get("document_type", "")).strip(),
        summary=str(payload.get("summary", "")).strip(),
        keywords=as_list(payload.get("keywords", [])),
        entities=as_list(payload.get("entities", [])),
        mentioned_laws=as_list(payload.get("mentioned_laws", [])),
        mentioned_decisions=as_list(payload.get("mentioned_decisions", [])),
        constitution=as_list(payload.get("constitution", [])),
        legal_references=as_list(payload.get("legal_references", [])),
    )


def extract_document_info_with_qwen(text: str) -> DocumentInfo:
    """Ask Qwen 1.5B for limited document info only."""

    from app.ollama_client import client

    response = client.chat(
        model=DOCUMENT_INFO_MODEL,
        messages=[
            {
                "role": "user",
                "content": build_document_info_prompt(text),
            }
        ],
        stream=False,
        keep_alive=OLLAMA_KEEP_ALIVE,
        options={
            "temperature": 0,
            "num_predict": 420,
        },
    )

    return parse_document_info_response(response["message"]["content"].strip())
