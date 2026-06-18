"""Structured source document loaders for the legal knowledge pipeline."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from .text_cleaning import clean_text
except ImportError:
    from text_cleaning import clean_text


PAGE_SEPARATOR_PATTERN = re.compile(r"^--- PAGE (\d+) ---\s*$", re.MULTILINE)
HEADING_STYLE_PATTERN = re.compile(r"^(?:heading|عنوان)\s*(\d+)?", re.IGNORECASE)
ARTICLE_PATTERN = re.compile(
    r"^\s*(?P<label>المادة|مادة)\s*"
    r"(?P<number>[\(\[]?[0-9\u0660-\u0669]+[\)\]]?)",
)
LEGAL_SECTION_PATTERN = re.compile(
    r"^\s*(?P<label>الباب|الفصل|القسم|الفرع)\s+"
    r"(?P<name>[^\n:]{1,120})",
)


@dataclass(frozen=True)
class DocumentBlock:
    """One ordered semantic block extracted from a source document."""

    text: str
    block_type: str = "paragraph"
    page_number: int = 1
    heading_level: int | None = None
    article_reference: str = ""
    section_reference: str = ""


@dataclass(frozen=True)
class LoadedDocument:
    """Normalized document content and source metadata."""

    source_file: str
    source_type: str
    title: str
    blocks: list[DocumentBlock]
    metadata: dict[str, str] = field(default_factory=dict)


def detect_legal_references(text: str) -> tuple[str, str]:
    """Return an article reference and broader legal section reference."""

    article_match = ARTICLE_PATTERN.match(text)
    section_match = LEGAL_SECTION_PATTERN.match(text)
    article = article_match.group(0).strip() if article_match else ""
    section = section_match.group(0).strip() if section_match else ""
    return article, section


def _serialize_property(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip() if value is not None else ""


class DocumentLoader(ABC):
    """Interface implemented by each supported source format."""

    extensions: tuple[str, ...] = ()

    @abstractmethod
    def load(self, path: Path) -> LoadedDocument:
        """Load one source document."""


class DocxDocumentLoader(DocumentLoader):
    """Load Word documents while preserving paragraph and table order."""

    extensions = (".docx",)

    @staticmethod
    def _iter_body_items(document: Any) -> Iterable[Any]:
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        for child in document.element.body.iterchildren():
            if child.tag.endswith("}p"):
                yield Paragraph(child, document)
            elif child.tag.endswith("}tbl"):
                yield Table(child, document)

    @staticmethod
    def _heading_level(paragraph: Any) -> int | None:
        style_name = paragraph.style.name if paragraph.style else ""
        style_match = HEADING_STYLE_PATTERN.match(style_name)
        if style_match:
            return int(style_match.group(1) or 1)

        outline = paragraph._p.xpath("./w:pPr/w:outlineLvl")
        if outline:
            value = outline[0].get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
            )
            if value is not None and value.isdigit():
                return int(value) + 1
        return None

    @staticmethod
    def _table_text(table: Any) -> str:
        rows = []
        for row in table.rows:
            cells = [clean_text(cell.text) for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        return "\n".join(rows)

    def load(self, path: Path) -> LoadedDocument:
        try:
            from docx import Document
            from docx.text.paragraph import Paragraph
        except ImportError as error:
            raise RuntimeError(
                "DOCX ingestion requires python-docx. "
                "Run: python -m pip install -r requirements.txt"
            ) from error

        document = Document(path)
        properties = document.core_properties
        metadata = {
            key: value
            for key, value in {
                "author": _serialize_property(properties.author),
                "subject": _serialize_property(properties.subject),
                "keywords": _serialize_property(properties.keywords),
                "category": _serialize_property(properties.category),
                "comments": _serialize_property(properties.comments),
                "created": _serialize_property(properties.created),
                "modified": _serialize_property(properties.modified),
                "last_modified_by": _serialize_property(
                    properties.last_modified_by
                ),
            }.items()
            if value
        }

        blocks = []
        first_heading = ""
        for item in self._iter_body_items(document):
            if isinstance(item, Paragraph):
                text = clean_text(item.text)
                if not text:
                    continue
                heading_level = self._heading_level(item)
                block_type = "heading" if heading_level else "paragraph"
                if heading_level and not first_heading:
                    first_heading = text
            else:
                text = self._table_text(item)
                if not text:
                    continue
                heading_level = None
                block_type = "table"

            article, section = detect_legal_references(text)
            blocks.append(
                DocumentBlock(
                    text=text,
                    block_type=block_type,
                    heading_level=heading_level,
                    article_reference=article,
                    section_reference=section,
                )
            )

        title = clean_text(properties.title or "") or first_heading or path.stem
        return LoadedDocument(
            source_file=path.name,
            source_type="docx",
            title=title,
            blocks=blocks,
            metadata=metadata,
        )


class TxtDocumentLoader(DocumentLoader):
    """Load UTF-8 text files, including legacy page-separated exports."""

    extensions = (".txt",)

    def load(self, path: Path) -> LoadedDocument:
        content = clean_text(path.read_text(encoding="utf-8-sig"))
        separators = list(PAGE_SEPARATOR_PATTERN.finditer(content))
        pages: list[tuple[int, str]] = []

        if separators:
            for index, separator in enumerate(separators):
                end = (
                    separators[index + 1].start()
                    if index + 1 < len(separators)
                    else len(content)
                )
                pages.append(
                    (
                        int(separator.group(1)),
                        content[separator.end() : end].strip(),
                    )
                )
        else:
            pages = [(1, content)]

        blocks = []
        for page_number, page_text in pages:
            for paragraph in re.split(r"\n\s*\n|\n(?=\s*(?:المادة|الباب|الفصل|القسم|الفرع)\b)", page_text):
                text = clean_text(paragraph)
                if not text:
                    continue
                article, section = detect_legal_references(text)
                blocks.append(
                    DocumentBlock(
                        text=text,
                        page_number=page_number,
                        article_reference=article,
                        section_reference=section,
                    )
                )

        return LoadedDocument(
            source_file=path.name,
            source_type="txt",
            title=path.stem,
            blocks=blocks,
        )


LOADERS = (DocxDocumentLoader(), TxtDocumentLoader())
LOADER_BY_EXTENSION = {
    extension: loader
    for loader in LOADERS
    for extension in loader.extensions
}


def supported_extensions() -> tuple[str, ...]:
    """Return source extensions currently supported by the registry."""

    return tuple(sorted(LOADER_BY_EXTENSION))


def load_document(path: Path) -> LoadedDocument:
    """Load one document with the registered loader for its extension."""

    loader = LOADER_BY_EXTENSION.get(path.suffix.lower())
    if loader is None:
        supported = ", ".join(supported_extensions())
        raise ValueError(
            f"Unsupported document type '{path.suffix}'. Supported: {supported}"
        )
    return loader.load(path)


def load_documents(folder: Path) -> list[LoadedDocument]:
    """Batch-load all supported documents in a folder."""

    extensions = set(supported_extensions())
    paths = sorted(
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in extensions
        and not path.name.startswith("~$")
    )
    return [load_document(path) for path in paths]
