"""Direct JSON lookup for exact legal document overview questions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.services.json_repository import JsonRepository

try:
    from .config import PROJECT_ROOT
    from .text_encoding import repair_mojibake
except ImportError:
    from config import PROJECT_ROOT
    from text_encoding import repair_mojibake

ARABIC_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
    "01234567890123456789",
)
CHUNKS_FILE = PROJECT_ROOT / "data" / "chunks.jsonl"
RELATED_TOPICS_HEADING = "مواضيع مقترحة من نفس النص:"
LAW_HEADING_PATTERN = re.compile(
    r"(?m)(?<!\S)([0-9\u0660-\u0669\u06f0-\u06f9]+)\.\s+"
    r"((?:قانون|قرار|تعليمات|نظام)\s+.+?)"
    r"(?=(?:\s+[0-9\u0660-\u0669\u06f0-\u06f9]+\.\s+"
    r"(?:قانون|قرار|تعليمات|نظام)\s+)|\Z)",
    re.DOTALL,
)
LAW_NUMBER_YEAR_PATTERN = re.compile(
    r"رقم\s*\(?\s*([0-9\u0660-\u0669\u06f0-\u06f9]+)\s*\)?.{0,40}?"
    r"لسنة\s*\(?\s*([0-9\u0660-\u0669\u06f0-\u06f9]{4})\s*\)?"
)
STOP_TERMS = {
    "ما",
    "هو",
    "هي",
    "عن",
    "حول",
    "اريد",
    "أريد",
    "اعطني",
    "كل",
    "معلومات",
    "تعريف",
    "عرف",
    "قانون",
    "رقم",
    "لسنة",
}


@dataclass(frozen=True)
class ExactLawMatch:
    title: str
    content: str
    document: dict[str, Any]
    source: str


def load_chunk_records() -> list[dict[str, Any]]:
    if not CHUNKS_FILE.exists():
        return []
    records = []
    with CHUNKS_FILE.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def normalize_digits(value: object) -> str:
    return repair_mojibake(str(value or "")).translate(ARABIC_DIGITS)


def normalize_text(value: object) -> str:
    text = normalize_digits(value)
    text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def query_number_year(question: str) -> tuple[str, str]:
    normalized = normalize_digits(question)
    match = LAW_NUMBER_YEAR_PATTERN.search(normalized)
    if match:
        return match.group(1), match.group(2)
    numbers = re.findall(r"[0-9]+", normalized)
    if not numbers:
        return "", ""
    year = next((number for number in numbers if len(number) == 4), "")
    law_number = next((number for number in numbers if number != year), "")
    return law_number, year


def meaningful_terms(question: str) -> set[str]:
    normalized = normalize_text(question)
    return {
        term
        for term in normalized.split()
        if len(term) > 2 and term not in STOP_TERMS and not term.isdigit()
    }


def document_content(document: dict[str, Any]) -> str:
    return repair_mojibake(
        str(
            document.get("content")
            or document.get("embedding_text")
            or document.get("summary")
            or document.get("title")
            or ""
        )
    ).strip()


def split_law_sections(text: str) -> list[tuple[str, str]]:
    sections = []
    for match in LAW_HEADING_PATTERN.finditer(text):
        section = match.group(0).strip()
        heading = match.group(2).splitlines()[0].strip(" :")
        sections.append((heading, section))
    return sections or [(text.splitlines()[0].strip() if text else "", text)]


def section_item_number(section: str) -> int | None:
    match = re.search(r"(?m)^\s*([0-9\u0660-\u0669\u06f0-\u06f9]+)\.\s+", section)
    if not match:
        return None
    return int(normalize_digits(match.group(1)))


def source_from_item_number(item_number: int | None) -> str:
    if item_number is None:
        return ""
    if 1 <= item_number <= 10:
        return "تفكيك القوانين من (١) إلى (١٠) - المبادئ الدستورية والجنائية"
    if 11 <= item_number <= 20:
        return "تفكيك القوانين من (١١) إلى (٢٠) - التشريعات القضائية والأمنية والاستثمارية"
    if 21 <= item_number <= 30:
        return "تفكيك القوانين من (٢١) إلى (٣٠) - السياسات المالية والعمالية والتموينية"
    if 31 <= item_number <= 40:
        return "تفكيك القوانين من (٣١) إلى (٤٠) - تشريعات الحوكمة الرقمية والضمان الشامل (٢٠٢٠ - ٢٠٢٦)"
    return ""


def document_source(document: dict[str, Any], section: str) -> str:
    source = repair_mojibake(
        str(
            document.get("source")
            or document.get("original_filename")
            or document.get("document_source")
            or ""
        )
    ).strip()
    group_source = source_from_item_number(section_item_number(section))
    return group_source or source


def clean_law_content(content: str) -> str:
    lines = []
    has_full_structure = "الهيكل التنظيمي:" in content
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if has_full_structure and line.startswith("التنظيمي:"):
            continue
        if line.startswith("تفكيك القوانين من"):
            continue
        if line and line not in lines:
            lines.append(line)
        elif not line and lines and lines[-1]:
            lines.append("")
    return "\n".join(lines).strip()


def format_law_content(content: str) -> str:
    lines = []
    for raw_line in clean_law_content(content).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^[0-9\u0660-\u0669\u06f0-\u06f9]+\.\s+", line):
            lines.append(line)
        elif line.startswith(("الأسباب الموجبة:", "الهيكل التنظيمي:", "أبرز المواد")):
            lines.append(f"•\t{line}")
        elif line.startswith("المادة"):
            lines.append(f"•\t{line}")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def summarize_law_content(content: str, max_lines: int = 3) -> str:
    """Return a short public summary instead of detailed Word/docx content."""

    summary_lines = []
    for raw_line in clean_law_content(content).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("Ø£Ø¨Ø±Ø² Ø§Ù„Ù…ÙˆØ§Ø¯", "أبرز المواد")):
            break
        if line.startswith(("Ø§Ù„Ù…Ø§Ø¯Ø©", "المادة")):
            continue
        if line not in summary_lines:
            summary_lines.append(line)
        if len(summary_lines) >= max_lines:
            break
    return "\n".join(summary_lines).strip() or format_law_content(content)


def related_topics_for_law(content: str) -> list[str]:
    """Return follow-up topics from facts that appear in the exact law text."""

    text = clean_law_content(content)
    topics: list[str] = []

    def add(topic: str) -> None:
        if topic not in topics:
            topics.append(topic)

    article = re.search(r"(?:المادة|Ø§Ù„Ù…Ø§Ø¯Ø©)\s*\(?\s*([0-9٠-٩]+)\s*\)?", text)
    if article:
        add(f"هل تريد معرفة مضمون المادة ({article.group(1)}) في نفس القانون؟")

    amount = re.search(r"([0-9٠-٩][0-9٠-٩.,/ ]+)\s*(دينار|دولار)", text)
    if amount:
        value, currency = [re.sub(r"\s+", " ", item).strip() for item in amount.groups()]
        add(f"أستطيع مساعدتك في توضيح تفاصيل المبلغ {value} {currency} الوارد في النص.")

    date = re.search(r"\b([0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4})\b", text)
    if date:
        add(f"هل تريد معرفة دلالة تاريخ {date.group(1)} في نفس النص؟")

    if "الأسباب الموجبة" in text or "Ø§Ù„Ø£Ø³Ø¨Ø§Ø¨ Ø§Ù„Ù…ÙˆØ¬Ø¨Ø©" in text:
        add("هل تريد معرفة خلاصة الأسباب الموجبة في نفس النص؟")
    if "الهيكل التنظيمي" in text or "Ø§Ù„Ù‡ÙŠÙƒÙ„ Ø§Ù„ØªÙ†Ø¸ÙŠÙ…ÙŠ" in text:
        add("أستطيع مساعدتك في توضيح الهيكل التنظيمي المذكور في نفس النص.")

    return (topics or [
        "هل تريد معرفة النقطة القانونية الرئيسية التي يقررها هذا النص؟",
        "أستطيع مساعدتك في تحديد العبارة الأهم المرتبطة بسؤالك من نفس النص.",
        "هل تريد أن أراجع لك الجزء الذي يحتاج إلى قراءة تفصيلية من نفس الوثيقة؟",
    ])[:3]


def append_related_topics(answer: str, content: str) -> str:
    """Append interactive related topics to exact-law answers."""

    if not answer or RELATED_TOPICS_HEADING in answer or "مواضيع مقترحة:" in answer:
        return answer
    topic_lines = "\n".join(f"- {topic}" for topic in related_topics_for_law(content))
    return f"{answer.strip()}\n\n{RELATED_TOPICS_HEADING}\n{topic_lines}"


def detail_bonus(section: str) -> int:
    score = 0
    if "الأسباب الموجبة" in section:
        score += 100
    if "الهيكل التنظيمي" in section:
        score += 80
    if "أبرز المواد" in section:
        score += 100
    score += min(section.count("المادة"), 8) * 30
    if len(section) > 500:
        score += 40
    return score


def chunk_source_label(source_file: str, section: str) -> str:
    group_source = source_from_item_number(section_item_number(section))
    if group_source:
        return group_source
    return repair_mojibake(source_file).strip()


def chunk_section_matches() -> list[tuple[str, str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in load_chunk_records():
        source_file = str(record.get("source_file") or "")
        if not source_file:
            continue
        grouped.setdefault(source_file, []).append(record)

    matches = []
    for source_file, records in grouped.items():
        records = sorted(records, key=lambda item: int(item.get("chunk_index") or 0))
        text = "\n".join(repair_mojibake(str(record.get("text") or "")) for record in records)
        for title, section in split_law_sections(text):
            if not title or not section:
                continue
            metadata = {
                "id": source_file,
                "title": title,
                "document_type": records[0].get("document_type"),
                "source": source_file,
            }
            matches.append((title, clean_law_content(section), metadata))
    return matches


def section_score(
    question_terms: set[str],
    law_number: str,
    year: str,
    title: str,
    section: str,
) -> int:
    searchable = normalize_text(f"{title}\n{section}")
    tokens = set(searchable.split())
    term_score = len(question_terms & tokens) * 5
    identifier_score = 0
    number_matches = bool(
        law_number
        and re.search(rf"رقم\s*\(?\s*{re.escape(law_number)}\s*\)?", searchable)
    )
    year_matches = bool(year and year in searchable)
    if law_number and number_matches:
        identifier_score += 80
    if year and year_matches:
        identifier_score += 60
    if law_number and year and not (number_matches and year_matches):
        return 0
    if not term_score and not identifier_score:
        return 0
    score = term_score + identifier_score
    if "قانون" in searchable:
        score += 5
    score += detail_bonus(section)
    return score


def find_exact_law(question: str) -> ExactLawMatch | None:
    """Find a requested law and return only its own section."""

    law_number, year = query_number_year(question)
    terms = meaningful_terms(question)
    if not law_number and not year and not terms:
        return None

    best: tuple[int, ExactLawMatch] | None = None
    for section_title, section, metadata in chunk_section_matches():
        score = section_score(terms, law_number, year, section_title, section)
        if score < 60:
            continue
        match = ExactLawMatch(
            title=section_title,
            content=section,
            document=metadata,
            source=chunk_source_label(str(metadata.get("source") or ""), section),
        )
        if best is None or score > best[0]:
            best = (score, match)

    for document in JsonRepository().list_documents():
        content = document_content(document)
        if not content:
            continue
        document_title = repair_mojibake(str(document.get("title") or "")).strip()
        sections = split_law_sections(content)
        for section_title, section in sections:
            title = section_title or document_title
            score = section_score(terms, law_number, year, title, section)
            doc_number = normalize_digits(document.get("number"))
            doc_year = normalize_digits(document.get("year"))
            if law_number and doc_number == law_number:
                score += 40
            if year and doc_year == year:
                score += 30
            if len(sections) == 1:
                score += 10
            if score < 60:
                continue
            match = ExactLawMatch(
                title=title,
                content=format_law_content(section),
                document=document,
                source=document_source(document, section),
            )
            if best is None or score > best[0]:
                best = (score, match)

    return best[1] if best else None


def answer_exact_law(question: str) -> dict[str, Any] | None:
    match = find_exact_law(question)
    if not match:
        return None
    title = match.title or repair_mojibake(str(match.document.get("title") or ""))
    source = match.source or title
    answer = f"{summarize_law_content(match.content)}\n\nالمصدر: {source}".strip()
    answer = append_related_topics(answer, match.content)
    return {
        "answer": answer,
        "citations": [
            {
                "source_file": source,
                "page_number": 1,
                "legal_reference": title,
            }
        ],
        "snippets": [
            {
                "rank": 1,
                "source_file": source,
                "page_number": 1,
                "document_title": title,
                "document_type": match.document.get("document_type"),
                "legal_reference": title,
                "source_type": "json",
                "text": match.content,
            }
        ],
    }
