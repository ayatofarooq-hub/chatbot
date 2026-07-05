from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "legal_documents"
OUTPUT_ROOT = ROOT / "dataset"

ARABIC_DIGITS = {
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
}

STOP_WORDS = {
    "و",
    "في",
    "من",
    "على",
    "إلى",
    "عن",
    "ال",
    "إلى",
    "هذا",
    "هذه",
    "ذلك",
    "أن",
    "ل",
    "لها",
    "له",
    "ب",
    "ت",
    "ثم",
    "ما",
    "لم",
    "لن",
    "لا",
    "كان",
    "على",
    "بأنه",
    "أي",
    "كل",
    "كما",
    "منذ",
    "بعد",
    "قبل",
    "أو",
    "وقد",
    "يتم",
    "تم",
    "لأن",
    "فإن",
    "قد",
    "بين",
    "أجل",
    "أحد",
    "بشكل",
}


def normalize_digits(text: str) -> str:
    return "".join(ARABIC_DIGITS.get(ch, ch) for ch in text)


def normalize_text(text: str) -> str:
    text = text.replace("\u200f", "").replace("\u200e", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_paragraph(text: str) -> str:
    text = normalize_text(text)
    return text.replace("•", "").strip()


def is_entry_heading(text: str) -> bool:
    cleaned = clean_paragraph(text)
    if not cleaned:
        return False
    if cleaned.startswith(("أولاً", "ثانياً", "ثالثاً", "رابعاً", "خامساً", "سادساً")):
        return False
    if re.match(r"^(\d+|[٠-٩]+)\.", cleaned):
        if re.search(r"\b(قانون|دستور|قرار|أمر|تنظيم|تعليمات|تعديل|مؤسسة|قانون|الأمر)\b", cleaned):
            return True
    return False


def split_blocks(paragraphs: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for paragraph in paragraphs:
        text = clean_paragraph(paragraph)
        if not text:
            continue
        if is_entry_heading(text):
            if current:
                blocks.append(current)
            current = [text]
        else:
            if current:
                current.append(text)
            else:
                current = [text]
    if current:
        blocks.append(current)
    return blocks


def extract_number(text: str) -> Optional[int]:
    matches = re.findall(r"(?:رقم|number)\s*(?:\(|\s)?([٠-٩0-9]+)", text)
    if matches:
        return int(normalize_digits(matches[0]))
    matches = re.findall(r"\b([٠-٩0-9]{1,4})\b", text)
    if matches:
        for candidate in matches:
            value = int(normalize_digits(candidate))
            if 1 <= value <= 9999:
                return value
    return None


def extract_year(text: str) -> Optional[int]:
    matches = re.findall(r"(?:لسنة|سنة|\()([١٢٣٤٥٦٧٨٩٠0-9]{4})(?:\)|\s|$)", text)
    if matches:
        return int(normalize_digits(matches[0]))
    return None


def infer_authority(text: str) -> str:
    lowered = text
    if "سلطة الائتلاف المؤقتة" in lowered:
        return "سلطة الائتلاف المؤقتة"
    if "مجلس الحكم" in lowered:
        return "مجلس الحكم"
    if "مجلس الوزراء" in lowered:
        return "مجلس الوزراء"
    if "مجلس النواب" in lowered:
        return "مجلس النواب"
    if "وزارة" in lowered:
        return "وزارة"
    if "محكمة" in lowered:
        return "محكمة"
    if "رئاسة" in lowered:
        return "رئاسة"
    if "المفوضية" in lowered:
        return "المفوضية"
    return ""


def infer_document_type(title: str, text: str) -> str:
    combined = f"{title} {text}".strip()
    if re.search(r"\bدستور\b", combined):
        return "constitution"
    if re.search(r"\bتعديل\b", combined):
        return "amendment"
    if re.search(r"\bأمر\b", combined):
        return "order"
    if re.search(r"\bقرار\b", combined):
        return "decision"
    if re.search(r"\bتعليمات\b", combined):
        return "instruction"
    if re.search(r"\bتنظيم\b", combined):
        return "regulation"
    if re.search(r"\bقانون\b", combined):
        return "law"
    return "law"


def infer_subtype(authority: str) -> str:
    if authority == "سلطة الائتلاف المؤقتة":
        return "CPA"
    if authority == "مجلس الحكم":
        return "Council"
    if authority == "مجلس الوزراء":
        return "Cabinet"
    if authority == "مجلس النواب":
        return "Parliament"
    if authority.startswith("وزارة"):
        return "Ministry"
    if authority.startswith("محكمة"):
        return "Court"
    if authority.startswith("رئاسة"):
        return "Presidency"
    if authority.startswith("المفوضية"):
        return "Independent Commission"
    return ""


def infer_categories(title: str, text: str) -> list[str]:
    combined = f"{title} {text}".lower()
    categories: list[str] = []
    if "دستور" in combined or "دستوري" in combined:
        categories.append("دستوري")
    if any(term in combined for term in ["إرهاب", "جريمة", "عقوبة", "جنائي", "قضائي"]):
        categories.extend(["أمن", "جنائي"])
    if any(term in combined for term in ["استثمار", "اقتصاد", "مستثمر", "ضريبة", "مصرف"]):
        categories.extend(["استثمار", "مالية"])
    if any(term in combined for term in ["أمن", "عسكري", "قوات", "جيش"]):
        categories.append("أمن")
    if any(term in combined for term in ["تعليم", "صحة", "شهادة", "رعاية", "حقوق"]):
        categories.append("إداري")
    if any(term in combined for term in ["انتخاب", "انتخابات", "برلماني"]):
        categories.append("انتخابات")
    if not categories:
        categories.append("إداري")
    return list(dict.fromkeys(categories))


def extract_keywords(title: str, text: str) -> list[str]:
    combined = f"{title} {text}"
    words = re.findall(r"[\u0600-\u06FF]+", combined)
    tokens = []
    for word in words:
        cleaned = word.strip(" :؛،.()[]{}")
        if len(cleaned) < 2:
            continue
        if cleaned in STOP_WORDS:
            continue
        if cleaned.startswith(("قانون", "قرار", "أمر", "تنظيم", "تعليمات", "تعديل", "الدستور", "دستور")):
            tokens.append(cleaned)
            continue
        tokens.append(cleaned)
    unique: list[str] = []
    for token in tokens:
        if token not in unique and token not in STOP_WORDS:
            unique.append(token)
    if len(unique) < 5:
        unique.extend(["قانون", "عراق", "تشريعي", "حقوق", "تنظيم"])
    return unique[:12]


def make_summary(title: str, paragraphs: list[str]) -> str:
    body_text = " ".join(paragraphs)
    body_text = re.sub(r"^(العنوان|الشرح التفصيلي|الأسباب الموجبة|الهيكل التنظيمي|أبرز المواد والفقرات التفصيلية|المادة)\s*[:：]\s*", "", body_text)
    body_text = re.sub(r"^\d+\.?\s*", "", body_text)
    sentences = re.split(r"(?<=[.؟!])\s+", body_text)
    first = next((s.strip() for s in sentences if s.strip()), body_text.strip())
    if len(first) > 280:
        first = first[:277].rstrip() + "..."
    return first or title


def build_citation(document_type: str, title: str, authority: str, number: Optional[int], year: Optional[int]) -> str:
    if document_type == "constitution":
        return "دستور العراق"
    if document_type == "law":
        if number and year:
            return f"قانون رقم {number} لسنة {year}"
        return title
    if document_type == "decision":
        if number and year:
            authority_text = authority or "مجلس الوزراء"
            return f"قرار {authority_text} رقم {number} لسنة {year}"
        return title
    if document_type == "order":
        if number and year:
            authority_text = authority or "سلطة الائتلاف المؤقتة"
            return f"أمر {authority_text} رقم {number} لسنة {year}"
        return title
    if document_type == "regulation":
        if number and year:
            return f"تنظيم رقم {number} لسنة {year}"
        return title
    if document_type == "instruction":
        if number and year:
            return f"تعليمات رقم {number} لسنة {year}"
        return title
    if document_type == "amendment":
        if number and year:
            return f"تعديل قانون رقم {number} لسنة {year}"
        return title
    return title


def make_id(document_type: str, authority: str, number: Optional[int], year: Optional[int]) -> str:
    if document_type == "constitution":
        return f"CONST-{year or '0000'}"
    if document_type == "law":
        return f"LAW-{number or '0'}-{year or '0000'}"
    if document_type == "order" and "سلطة الائتلاف" in authority:
        return f"CPA-{number or '0'}-{year or '0000'}"
    if document_type == "decision" and authority in {"مجلس الوزراء", "مجلس الحكم"}:
        return f"CM-{number or '0'}-{year or '0000'}"
    if document_type == "amendment":
        return f"AMD-{number or '0'}-{year or '0000'}"
    return f"{document_type.upper()[:3]}-{number or '0'}-{year or '0000'}"


def parse_entry(block: list[str], source_name: str) -> dict:
    first_line = block[0]
    title = first_line
    title = re.sub(r"^\s*(\d+|[٠-٩]+)\.\s*", "", title)
    title = title.split(":", 1)[0].strip()
    title = re.sub(r"^العنوان\s*[:：]\s*", "", title)

    if block[1:]:
        for candidate in block[1:]:
            if candidate.startswith("العنوان") or re.search(r"\bالعنوان\b", candidate):
                title_candidate = candidate.replace("العنوان", "", 1).strip().strip(":")
                if title_candidate:
                    title = title_candidate
                    break

    combined_text = "\n".join(block)
    authority = infer_authority(combined_text)
    document_type = infer_document_type(title, combined_text)
    subtype = infer_subtype(authority)
    number = extract_number(combined_text)
    year = extract_year(combined_text)
    if not title or title.startswith(("قانون", "قرار", "أمر", "تنظيم", "تعليمات", "تعديل")) and len(block) == 1:
        title = title or first_line

    summary = make_summary(title, block[1:] or block)
    content = "\n\n".join(block)
    categories = infer_categories(title, content)
    keywords = extract_keywords(title, content)

    record = {
        "id": make_id(document_type, authority, number, year),
        "document_type": document_type,
        "document_subtype": subtype,
        "title": title,
        "number": number,
        "year": year,
        "issuing_authority": authority or "",
        "country": "Iraq",
        "language": "Arabic",
        "status": "نافذ",
        "category": categories,
        "keywords": keywords,
        "summary": summary,
        "content": content,
        "references": [],
        "related_documents": [],
        "citation": build_citation(document_type, title, authority, number, year),
        "embedding_text": f"{title}\n{summary}\n{content}",
    }
    record["source_file"] = source_name
    return record


def load_documents() -> list[tuple[Path, list[dict]]]:
    documents: list[tuple[Path, list[dict]]] = []
    for path in sorted(SOURCE_DIR.glob("*.docx")):
        doc = Document(path)
        paragraphs = [clean_paragraph(p.text) for p in doc.paragraphs if clean_paragraph(p.text)]
        blocks = split_blocks(paragraphs)
        records = [parse_entry(block, path.name) for block in blocks]
        documents.append((path, records))
    return documents


def save_records(records: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        record_type = record["document_type"]
        if record_type == "law":
            folder = output_dir / "laws"
        elif record_type == "decision":
            folder = output_dir / "decisions"
        elif record_type == "order":
            folder = output_dir / "orders"
        elif record_type == "instruction":
            folder = output_dir / "instructions"
        elif record_type == "regulation":
            folder = output_dir / "regulations"
        elif record_type == "constitution":
            folder = output_dir / "constitution"
        elif record_type == "amendment":
            folder = output_dir / "amendments"
        else:
            folder = output_dir / "orders"
        folder.mkdir(parents=True, exist_ok=True)
        number = record.get("number") or "0"
        year = record.get("year") or "0000"
        stem = f"{record_type}_{number}_{year}".replace(" ", "_")
        file_path = folder / f"{stem}.json"
        with file_path.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for subfolder in ["laws", "decisions", "orders", "regulations", "instructions", "amendments", "constitution"]:
        (OUTPUT_ROOT / subfolder).mkdir(parents=True, exist_ok=True)
    documents = load_documents()
    for _, records in documents:
        save_records(records, OUTPUT_ROOT)
    print(f"Processed {len(documents)} Word documents and wrote {sum(len(records) for _, records in documents)} JSON files.")


if __name__ == "__main__":
    main()
