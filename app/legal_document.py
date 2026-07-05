"""Internal structured representation of a legal record."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentBlock:
    """One legal text block with its citation locator."""

    text: str
    block_type: str = "paragraph"
    page_number: int = 1
    heading_level: int | None = None
    article_reference: str = ""
    section_reference: str = ""


@dataclass(frozen=True)
class LoadedDocument:
    """One normalized legal record."""

    source_file: str
    source_type: str
    title: str
    blocks: list[DocumentBlock]
    document_type: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
