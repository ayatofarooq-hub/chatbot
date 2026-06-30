"""Tests for persistent citation registry behavior."""

import tempfile
import unittest
from pathlib import Path

from app.citation_registry import (
    build_registry,
    filter_results_to_registered,
    replace_source_citations,
)


class CitationRegistryTests(unittest.TestCase):
    def test_build_registry_maps_chunk_to_law_article(self):
        registry = build_registry(
            [
                {
                    "id": "abc123",
                    "document_title": "penal law",
                    "article_reference": "article 405",
                    "document_type": "law",
                    "source_file": "penal_code.docx",
                }
            ],
            ingest_date="2026-06-11",
        )

        citation = registry["by_chunk_id"]["abc123"]
        self.assertEqual(citation["law"], "penal law")
        self.assertEqual(citation["article"], "article 405")
        self.assertEqual(citation["document_type"], "law")
        self.assertEqual(citation["source_file"], "penal_code.docx")
        self.assertEqual(citation["ingest_date"], "2026-06-11")
        self.assertEqual(
            registry["by_law_article"]["penal law"]["article 405"],
            ["abc123"],
        )

    def test_replace_source_citations_removes_old_chunks_for_same_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "citation_registry.json"
            replace_source_citations(
                "law.docx",
                [{"id": "old", "source_file": "law.docx"}],
                registry_path=registry_path,
            )
            registry = replace_source_citations(
                "law.docx",
                [{"id": "new", "source_file": "law.docx"}],
                registry_path=registry_path,
            )

        self.assertNotIn("old", registry["by_chunk_id"])
        self.assertIn("new", registry["by_chunk_id"])

    def test_filter_results_to_registered_drops_unregistered_chunks(self):
        results = {
            "documents": [["valid", "invalid"]],
            "metadatas": [[{"chunk_id": "ok"}, {"chunk_id": "missing"}]],
            "distances": [[0.1, 0.2]],
        }
        registry = {
            "by_chunk_id": {
                "ok": {
                    "law": "law",
                    "article": "article",
                    "law_number": "111",
                    "law_year": "1969",
                    "article_number": "405",
                    "law_name": "Penal Code",
                    "source_file": "law.docx",
                    "ingest_date": "2026-06-11",
                    "chunk_id": "ok",
                }
            }
        }

        filtered, warnings = filter_results_to_registered(results, registry=registry)

        self.assertEqual(filtered["documents"], [["valid"]])
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
