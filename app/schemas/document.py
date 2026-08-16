"""Document data model."""

from dataclasses import dataclass, field

from app.classifiers import ParagraphType


@dataclass
class ParagraphModel:
    text: str
    type: ParagraphType


@dataclass
class DocumentModel:
    source_file: str
    title: str
    paragraphs: list[ParagraphModel] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
