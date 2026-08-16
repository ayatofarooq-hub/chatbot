"""Generic document loader.

This module only reads supported files and produces structured text. It does
not classify, interpret, or extract legal meaning from documents.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from config import DEFAULT_ENCODING, SUPPORTED_EXTENSIONS
from models.document import Document, Table


WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_RTF_CONTROL_WORD = re.compile(r"\\[a-zA-Z]+-?\d* ?")
_RTF_ESCAPED_HEX = re.compile(r"\\'[0-9a-fA-F]{2}")
_MARKDOWN_MARKERS = re.compile(r"^#{1,6}\s+|[*_`>#-]+")


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self._parts.append(value)

    def get_text(self) -> str:
        return "\n".join(self._parts)


class DocumentLoader:
    """Read supported files into a generic Document object."""

    def load(self, source_path: Path) -> Document:
        extension = source_path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {extension}")

        if extension == ".docx":
            pages, paragraphs, tables, raw_text = self._load_docx(source_path)
        elif extension == ".pdf":
            pages, paragraphs, tables, raw_text = self._load_pdf(source_path)
        elif extension == ".rtf":
            pages, paragraphs, tables, raw_text = self._load_rtf(source_path)
        elif extension in {".html", ".htm"}:
            pages, paragraphs, tables, raw_text = self._load_html(source_path)
        elif extension == ".md":
            pages, paragraphs, tables, raw_text = self._load_markdown(source_path)
        else:
            pages, paragraphs, tables, raw_text = self._load_txt(source_path)

        return Document(
            filename=source_path.name,
            extension=extension,
            pages=pages,
            paragraphs=paragraphs,
            tables=tables,
            raw_text=raw_text,
        )

    def _load_txt(self, source_path: Path) -> tuple[list[str], list[str], list[Table], str]:
        raw_text = source_path.read_text(encoding=DEFAULT_ENCODING)
        paragraphs = self._paragraphs(raw_text)
        return [raw_text], paragraphs, [], raw_text

    def _load_docx(self, source_path: Path) -> tuple[list[str], list[str], list[Table], str]:
        with ZipFile(source_path) as archive:
            xml_bytes = archive.read("word/document.xml")

        root = ElementTree.fromstring(xml_bytes)
        paragraphs: list[str] = []
        tables: list[Table] = []

        for paragraph in root.iter(f"{WORD_NAMESPACE}p"):
            paragraph_text = self._word_text(paragraph)
            if paragraph_text:
                paragraphs.append(paragraph_text)

        for table in root.iter(f"{WORD_NAMESPACE}tbl"):
            rows: list[list[str]] = []
            for row in table.iter(f"{WORD_NAMESPACE}tr"):
                cells = [self._word_text(cell) for cell in row.iter(f"{WORD_NAMESPACE}tc")]
                cleaned_cells = [cell for cell in cells if cell]
                if cleaned_cells:
                    rows.append(cleaned_cells)
            if rows:
                tables.append(Table(rows=rows))

        raw_text = "\n".join(paragraphs)
        return [raw_text], paragraphs, tables, raw_text

    def _load_pdf(self, source_path: Path) -> tuple[list[str], list[str], list[Table], str]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support requires installing dependencies from requirements.txt") from exc

        reader = PdfReader(str(source_path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        raw_text = "\n\n".join(page for page in pages if page)
        return pages, self._paragraphs(raw_text), [], raw_text

    def _load_rtf(self, source_path: Path) -> tuple[list[str], list[str], list[Table], str]:
        content = source_path.read_text(encoding=DEFAULT_ENCODING, errors="ignore")
        text = _RTF_ESCAPED_HEX.sub("", content)
        text = _RTF_CONTROL_WORD.sub("", text)
        text = text.replace("{", "").replace("}", "").replace("\\", "")
        paragraphs = self._paragraphs(text)
        raw_text = "\n".join(paragraphs)
        return [raw_text], paragraphs, [], raw_text

    def _load_html(self, source_path: Path) -> tuple[list[str], list[str], list[Table], str]:
        parser = _HtmlTextParser()
        parser.feed(source_path.read_text(encoding=DEFAULT_ENCODING, errors="ignore"))
        raw_text = parser.get_text()
        paragraphs = self._paragraphs(raw_text)
        return [raw_text], paragraphs, [], raw_text

    def _load_markdown(self, source_path: Path) -> tuple[list[str], list[str], list[Table], str]:
        raw_markdown = source_path.read_text(encoding=DEFAULT_ENCODING)
        lines = [_MARKDOWN_MARKERS.sub("", line).strip() for line in raw_markdown.splitlines()]
        raw_text = "\n".join(line for line in lines if line)
        paragraphs = self._paragraphs(raw_text)
        return [raw_text], paragraphs, [], raw_text

    def _word_text(self, element: ElementTree.Element) -> str:
        return "".join(
            text_node.text
            for text_node in element.iter(f"{WORD_NAMESPACE}t")
            if text_node.text
        ).strip()

    def _paragraphs(self, text: str) -> list[str]:
        return [paragraph.strip() for paragraph in re.split(r"\n\s*\n|\n", text) if paragraph.strip()]
