"""Load supported source files without accessing retrieval or model state."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.iraqi_government.loader import load_document as load_government_document


@dataclass(frozen=True)
class LoadedDocument:
    source_file: str
    filename: str
    extension: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    blocks: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "document": self.title,
            "source_file": self.source_file,
            "long_text": self.text,
            "paragraphs": [block for block in self.blocks if block["type"] != "table"],
            "tables": [block for block in self.blocks if block["type"] == "table"],
        }


class _StructuredHTMLParser(HTMLParser):
    """Retain block order, list items, and table cells from source HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._hidden_depth += 1
        if self._hidden_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "table", "tr", "td", "th"}:
            self._stack.append({"tag": tag, "parts": [], "items": [], "rows": [], "cells": []})
        elif tag == "br":
            self.handle_data("\n")

    def handle_data(self, data):
        if not self._hidden_depth:
            for node in self._stack:
                node["parts"].append(data)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)
            return
        if self._hidden_depth or not self._stack or self._stack[-1]["tag"] != tag:
            return
        node = self._stack.pop()
        text = " ".join("".join(node["parts"]).split())
        if tag in {"td", "th"}:
            if self._stack:
                self._stack[-1]["cells"].append(text)
            return
        if tag == "tr":
            if self._stack:
                self._stack[-1]["rows"].append(node["cells"])
            return
        if tag == "li":
            if self._stack:
                self._stack[-1]["items"].append(text)
            return
        if tag in {"ul", "ol"}:
            block = {"type": "list", "text": "\n".join(node["items"]), "items": node["items"]}
        elif tag == "table":
            block = {"type": "table", "text": "\n".join("\t".join(row) for row in node["rows"]), "rows": node["rows"]}
        elif tag.startswith("h"):
            block = {"type": "heading", "text": text, "level": int(tag[1])}
        else:
            block = {"type": "paragraph", "text": text}
        if block["text"]:
            self.blocks.append(block)


def load_document(path: str | Path) -> LoadedDocument:
    source_path = Path(path)
    loaded = load_government_document(source_path)
    blocks = [{"type": "paragraph", "text": text} for text in loaded.text.splitlines() if text.strip()]
    if loaded.extension in {".html", ".htm"}:
        parser = _StructuredHTMLParser()
        parser.feed(source_path.read_text(encoding="utf-8"))
        parser.close()
        blocks = parser.blocks or blocks
    title = next((block["text"] for block in blocks if block["type"] == "heading"), source_path.stem)
    return LoadedDocument(
        source_file=loaded.source_file,
        filename=loaded.filename,
        extension=loaded.extension,
        text=loaded.text,
        metadata=loaded.loader_metadata,
        title=title,
        blocks=blocks,
    )
