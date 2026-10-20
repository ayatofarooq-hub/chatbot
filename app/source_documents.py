"""Read original Word files for registered legal sources without changing them."""

from html import escape
from pathlib import Path, PureWindowsPath
import re
from urllib.parse import quote
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

try:
    from .config import PROJECT_ROOT
except ImportError:
    from config import PROJECT_ROOT


WORD_ROOTS = (
    PROJECT_ROOT / "legal_document_parser" / "input" / "docx",
    PROJECT_ROOT / "data" / "raw_DOCs",
)
UPLOAD_ROOT = PROJECT_ROOT / "data" / "legal_documents" / "uploads"
WORD_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def original_word_file(filename: str, registry: dict) -> Path:
    """Resolve only registered filenames inside the original-document folders."""
    windows_path = PureWindowsPath(filename)
    if (
        not filename
        or windows_path.name != filename
        or windows_path.drive
        or "/" in filename
        or "\\" in filename
        or ":" in filename
        or windows_path.suffix.lower() != ".docx"
    ):
        raise LookupError("Original Word document not found.")
    registered = any(
        str(entry.get("source_file") or "") == filename
        for entry in registry.get("by_chunk_id", {}).values()
        if isinstance(entry, dict)
    )
    if not registered:
        raise LookupError("Original Word document not found.")

    candidates = [(root, root / filename) for root in WORD_ROOTS]
    upload_match = re.fullmatch(r"uploaded_([0-9a-f]{16})_.+\.docx", filename, flags=re.IGNORECASE)
    if upload_match:
        candidates.append((UPLOAD_ROOT, UPLOAD_ROOT / f"{upload_match.group(1)}.docx"))
    matches = set()
    for root, candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(root.resolve()) and resolved.is_file():
            matches.add(resolved)
    # Never guess which original is intended when separate files share a name.
    if len(matches) != 1:
        raise LookupError("Original Word document not found or ambiguous.")
    return matches.pop()


def word_document_links(filename: str) -> dict:
    base = f"/api/source-documents/{quote(filename, safe='')}"
    return {"filename": filename, "preview_url": f"{base}/preview", "download_url": f"{base}/download"}


def word_preview_html(path: Path, filename: str) -> str:
    """Produce an escaped text/table preview; the downloadable original is intact."""
    try:
        document = Document(path)
    except (BadZipFile, PackageNotFoundError) as error:
        raise ValueError("Unreadable Word document.") from error
    blocks = []
    for element in document.element.body:
        if element.tag == qn("w:p"):
            paragraph = Paragraph(element, document)
            if paragraph.text.strip():
                blocks.append(f"<p>{escape(paragraph.text)}</p>")
        elif element.tag == qn("w:tbl"):
            table = Table(element, document)
            rows = [
                "<tr>" + "".join(f"<td>{escape(cell.text)}</td>" for cell in row.cells) + "</tr>"
                for row in table.rows
            ]
            blocks.append("<table>" + "".join(rows) + "</table>")
    content = "\n".join(blocks) or "<p>لا يوجد نص قابل للمعاينة. يمكنك تحميل الملف الأصلي.</p>"
    return (
        '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(filename)}</title>"
        "<style>body{font-family:Tahoma,Arial,sans-serif;margin:24px;color:#17211b;line-height:1.9}"
        "h1{font-size:17px;overflow-wrap:anywhere}p,td{white-space:pre-wrap}"
        "table{border-collapse:collapse;width:100%;margin:16px 0}"
        "td{border:1px solid #ccd6ce;padding:8px}</style></head>"
        f"<body><h1>{escape(filename)}</h1>{content}</body></html>"
    )
