"""Tests for Arabic-aware hybrid retrieval ranking."""

import unittest

from app.search_index import (
    candidate_search_text,
    detect_query_intents,
    document_dedupe_key,
    expand_question_for_retrieval,
    extract_strong_signals,
    is_summary_only_chunk_text,
    legacy_record_text,
    lexical_relevance,
    lexical_search_candidates,
    merge_candidate_results,
    metadata_filter_candidates,
    needs_multiple_documents,
    normalize_for_search,
    query_intent_score,
    rerank_results,
    strong_signal_score,
    tokenize_for_search,
)


class SearchIndexTests(unittest.TestCase):
    def test_normalization_unifies_arabic_letters_and_digits(self):
        self.assertEqual(
            normalize_for_search("إنتخابات ٢٠٢٠"),
            "انتخابات 2020",
        )

    def test_arabic_search_normalization_is_search_only_friendly(self):
        normalized = normalize_for_search(
            "\u0642\u0640\u064e\u0631\u0627\u0631 \u0625\u0644\u0649 \u0645\u062c\u0644\u0633 44/2024"
        )

        self.assertEqual(normalized, "\u0642\u0631\u0627\u0631 \u0627\u0644\u064a \u0645\u062c\u0644\u0633 44/2024")
        self.assertIn("44/2024", tokenize_for_search(normalized))

    def test_arabic_tokenization_matches_definite_article_variants(self):
        query_tokens = tokenize_for_search("\u0627\u0644\u063a\u0627\u0632")
        document_tokens = tokenize_for_search("\u0645\u0646\u062a\u0648\u062c \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632")

        self.assertIn("\u063a\u0627\u0632", query_tokens)
        self.assertIn("\u063a\u0627\u0632", document_tokens)

    def test_arabic_lexical_relevance_handles_cabinet_decision_variants(self):
        question = "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621"
        exact = "\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 \u0627\u0644\u0639\u0631\u0627\u0642\u064a"
        unrelated = "\u0642\u0627\u0646\u0648\u0646 \u0627\u0644\u0639\u0645\u0644"

        self.assertGreater(
            lexical_relevance(question, exact),
            lexical_relevance(question, unrelated),
        )

    def test_extract_strong_signals_keeps_legal_identifiers(self):
        signals = extract_strong_signals(
            "\u0643\u062a\u0627\u0628 123/45 \u0641\u064a 30/10/2024 \u0645\u0646 \u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u0646\u0641\u0637 \u0628\u0634\u0623\u0646 \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632"
        )

        self.assertIn("123/45", signals)
        self.assertIn("30/10/2024", signals)
        self.assertTrue(any("\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u0646\u0641\u0637" in signal for signal in signals))
        self.assertTrue(any("\u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632" in signal for signal in signals))

    def test_strong_signal_score_weights_specific_values(self):
        question = "\u0645\u0627 \u0647\u0648 \u0642\u0631\u0627\u0631 400 \u0644\u0633\u0646\u0629 2024\u061f"
        matching = "\u0642\u0631\u0627\u0631 \u0631\u0642\u0645 400 \u0644\u0633\u0646\u0629 2024"
        unrelated = "\u0642\u0631\u0627\u0631 \u0639\u0627\u0645 \u0644\u0633\u0646\u0629 2023"

        self.assertGreater(
            strong_signal_score(question, matching),
            strong_signal_score(question, unrelated),
        )

    def test_query_expansion_detects_source_book_intent(self):
        question = "\u0634\u0646\u0648 \u0627\u0644\u0643\u062a\u0627\u0628 \u0627\u0644\u064a \u0627\u0639\u062a\u0645\u062f \u0639\u0644\u064a\u0647 \u0627\u0644\u0642\u0631\u0627\u0631\u061f"
        expanded = expand_question_for_retrieval(question)

        self.assertIn("source_book", detect_query_intents(question))
        self.assertIn("\u0627\u0644\u0645\u0631\u0642\u0645 \u0628\u0627\u0644\u0639\u062f\u062f", expanded)
        self.assertIn("\u0627\u0644\u0645\u0624\u0631\u062e \u0641\u064a", expanded)

    def test_query_intent_score_rewards_answer_shape(self):
        question = "\u0645\u0627 \u0631\u0642\u0645 \u0648\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0643\u062a\u0627\u0628\u061f"
        matching = "\u0643\u062a\u0627\u0628 \u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u0646\u0641\u0637 \u0627\u0644\u0645\u0631\u0642\u0645 \u0628\u0627\u0644\u0639\u062f\u062f (123/45) \u0627\u0644\u0645\u0624\u0631\u062e \u0641\u064a 30/10/2024"
        unrelated = "\u0646\u0635 \u0639\u0627\u0645 \u0639\u0646 \u0627\u062c\u062a\u0645\u0627\u0639 \u0648\u0627\u062d\u062f"

        self.assertGreater(
            query_intent_score(question, matching),
            query_intent_score(question, unrelated),
        )

    def test_lexical_relevance_prioritizes_exact_law_number_and_year(self):
        question = "قانون رقم 13 لسنة 2005"
        exact = "قانون مكافحة الإرهاب رقم ١٣ لسنة ٢٠٠٥"
        unrelated = "قانون الانتخابات رقم 9 لسنة 2020"

        self.assertGreater(
            lexical_relevance(question, exact),
            lexical_relevance(question, unrelated),
        )

    def test_lexical_relevance_handles_reversed_rtl_pdf_numbers(self):
        question = "قانون مكافحة الإرهاب رقم 13 لسنة 2005"
        reversed_extraction = "قانون مكافحة الإرهاب رقم ٣١ لسنة ٥٠٠٢"
        unrelated = "قانون الاتجار بالبشر رقم 28 لسنة 2012"

        self.assertGreater(
            lexical_relevance(question, reversed_extraction),
            lexical_relevance(question, unrelated),
        )

    def test_reranking_can_promote_exact_match_over_closer_vector(self):
        results = {
            "_question": "قانون رقم 13 لسنة 2005",
            "documents": [[
                "نص عام عن قانون الانتخابات رقم 9 لسنة 2020",
                "قانون مكافحة الإرهاب رقم ١٣ لسنة ٢٠٠٥",
            ]],
            "metadatas": [[
                {"source_file": "a.txt", "page_number": 1},
                {"source_file": "b.txt", "page_number": 2},
            ]],
            "distances": [[0.05, 0.15]],
        }

        reranked = rerank_results(results, result_count=2)

        self.assertEqual(
            reranked["metadatas"][0][0]["source_file"],
            "b.txt",
        )

    def test_reranking_suppresses_near_duplicate_chunks(self):
        duplicate = "قانون العمل ينظم حقوق العامل وواجبات صاحب العمل"
        results = {
            "_question": "حقوق العامل",
            "documents": [[
                duplicate,
                duplicate + " فقط",
                "تحدد هذه المادة ساعات العمل والإجازات",
            ]],
            "metadatas": [[
                {"source_file": "law.txt", "page_number": 1},
                {"source_file": "law.txt", "page_number": 1},
                {"source_file": "law.txt", "page_number": 2},
            ]],
            "distances": [[0.1, 0.11, 0.2]],
        }

        reranked = rerank_results(results, result_count=2)

        self.assertIn(
            "تحدد هذه المادة ساعات العمل والإجازات",
            reranked["documents"][0],
        )

    def test_reranking_uses_question_intent_for_source_book_questions(self):
        question = "\u0634\u0646\u0648 \u0627\u0644\u0643\u062a\u0627\u0628 \u0627\u0644\u064a \u0627\u0639\u062a\u0645\u062f \u0639\u0644\u064a\u0647 \u0627\u0644\u0642\u0631\u0627\u0631\u061f"
        results = {
            "_question": question,
            "documents": [[
                "\u0642\u0631\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629 \u0639\u0644\u0649 \u0627\u0644\u0637\u0644\u0628",
                "\u0628\u0646\u0627\u0621 \u0639\u0644\u0649 \u0643\u062a\u0627\u0628 \u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u0646\u0641\u0637 \u0627\u0644\u0645\u0631\u0642\u0645 \u0628\u0627\u0644\u0639\u062f\u062f (123/45) \u0627\u0644\u0645\u0624\u0631\u062e \u0641\u064a 30/10/2024",
            ]],
            "metadatas": [[
                {"source_file": "decision.docx", "section": "body"},
                {"source_file": "decision.docx", "section": "body"},
            ]],
            "distances": [[0.05, 0.25]],
        }

        reranked = rerank_results(results, result_count=2)

        self.assertIn("(123/45)", reranked["documents"][0][0])
        self.assertGreater(reranked["intent_scores"][0][0], 0)

    def test_aggregate_query_keeps_best_result_per_document(self):
        question = "\u0645\u0627 \u0627\u0644\u0642\u0631\u0627\u0631\u0627\u062a \u0627\u0644\u062a\u064a \u0639\u062f\u0644\u062a \u0623\u0633\u0639\u0627\u0631 \u0627\u0644\u0645\u0646\u062a\u062c\u0627\u062a \u0627\u0644\u0646\u0641\u0637\u064a\u0629 \u062e\u0644\u0627\u0644 2024\u061f"
        results = {
            "_question": question,
            "documents": [[
                "\u062a\u0639\u062f\u064a\u0644 \u0633\u0639\u0631 \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632 2024",
                "\u062a\u0639\u062f\u064a\u0644 \u0633\u0639\u0631 \u0632\u064a\u062a \u0627\u0644\u0648\u0642\u0648\u062f 2024",
                "\u062a\u0639\u062f\u064a\u0644 \u0623\u062c\u0648\u0631 \u0627\u0644\u0646\u0642\u0644 2024",
            ]],
            "metadatas": [[
                {"document_id": "doc-a", "source_file": "a.docx", "document_title": "oil price decision"},
                {"document_id": "doc-a", "source_file": "a.docx", "document_title": "oil price decision"},
                {"document_id": "doc-b", "source_file": "b.docx", "document_title": "transport decision"},
            ]],
            "distances": [[0.1, 0.2, 0.15]],
        }

        reranked = rerank_results(results, result_count=5)

        self.assertTrue(needs_multiple_documents(question))
        self.assertEqual(len(reranked["documents"][0]), 2)
        document_ids = [metadata["document_id"] for metadata in reranked["metadatas"][0]]
        self.assertCountEqual(document_ids, ["doc-a", "doc-b"])
        self.assertEqual(len(document_ids), len(set(document_ids)))
        self.assertGreaterEqual(
            reranked["relevance_scores"][0][0],
            reranked["relevance_scores"][0][1],
        )

    def test_non_aggregate_query_can_return_multiple_chunks_from_same_document(self):
        question = "\u0643\u0645 \u0623\u0635\u0628\u062d \u0633\u0639\u0631 \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632\u061f"
        results = {
            "_question": question,
            "documents": [["price first paragraph", "price second paragraph"]],
            "metadatas": [[
                {"document_id": "doc-a", "source_file": "a.docx"},
                {"document_id": "doc-a", "source_file": "a.docx"},
            ]],
            "distances": [[0.1, 0.2]],
        }

        reranked = rerank_results(results, result_count=2)

        self.assertFalse(needs_multiple_documents(question))
        self.assertEqual(len(reranked["documents"][0]), 2)
        self.assertEqual(document_dedupe_key(reranked["metadatas"][0][0]), "doc-a")

    def test_reranking_searches_metadata_without_filename_dependency(self):
        results = {
            "_question": "400",
            "documents": [[
                "general cabinet routing text",
                "the product became 400 dinars per liter",
            ]],
            "metadatas": [[
                {
                    "source_file": "400-filename.docx",
                    "document_title": "unrelated title",
                    "reference_numbers": "",
                },
                {
                    "source_file": "opaque-upload-123.docx",
                    "document_title": "fuel oil and diesel adjustment",
                    "reference_numbers": "400",
                    "legal_reference": "energy pricing recommendation",
                },
            ]],
            "distances": [[0.01, 0.2]],
        }

        reranked = rerank_results(results, result_count=2)

        self.assertEqual(
            reranked["metadatas"][0][0]["source_file"],
            "opaque-upload-123.docx",
        )
        self.assertNotIn(
            "400-filename.docx",
            candidate_search_text("", results["metadatas"][0][0]),
        )

    def test_metadata_filter_candidates_is_layer_one(self):
        records = [
            {
                "id": "a",
                "text": "routing",
                "source_file": "a.docx",
                "document_title": "other",
                "year": "2023",
            },
            {
                "id": "b",
                "text": "routing",
                "source_file": "b.docx",
                "document_title": "\u062a\u0639\u062f\u064a\u0644 \u0633\u0639\u0631 \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632",
                "year": "2024",
                "document_type": "\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
            },
        ]

        results = metadata_filter_candidates(
            "\u0643\u0645 \u0623\u0635\u0628\u062d \u0633\u0639\u0631 \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632 \u0633\u0646\u0629 2024\u061f",
            records,
            limit=2,
        )

        self.assertEqual(results["metadatas"][0][0]["chunk_id"], "b")
        self.assertEqual(results["metadatas"][0][0]["retrieval_layer"], "metadata")

    def test_lexical_search_candidates_is_layer_two(self):
        records = [
            {"id": "a", "text": "\u0646\u0635 \u0639\u0627\u0645", "source_file": "a.docx"},
            {
                "id": "b",
                "text": "\u0623\u0635\u0628\u062d \u0633\u0639\u0631 \u0645\u0646\u062a\u0648\u062c \u0632\u064a\u062a \u0627\u0644\u063a\u0627\u0632 400",
                "source_file": "b.docx",
            },
        ]

        results = lexical_search_candidates("\u0633\u0639\u0631 \u0627\u0644\u063a\u0627\u0632 400", records, limit=2)

        self.assertEqual(results["metadatas"][0][0]["chunk_id"], "b")
        self.assertEqual(results["metadatas"][0][0]["retrieval_layer"], "lexical")

    def test_merge_candidate_results_preserves_retrieval_layers(self):
        metadata_results = {
            "documents": [["text"]],
            "metadatas": [[{"chunk_id": "same", "retrieval_layer": "metadata"}]],
            "distances": [[0.4]],
        }
        semantic_results = {
            "documents": [["text"]],
            "metadatas": [[{"chunk_id": "same", "retrieval_layer": "semantic"}]],
            "distances": [[0.2]],
        }

        merged = merge_candidate_results(metadata_results, semantic_results, question="q")

        self.assertEqual(len(merged["documents"][0]), 1)
        self.assertEqual(merged["distances"][0][0], 0.2)
        self.assertEqual(merged["metadatas"][0][0]["retrieval_layers"], "metadata|semantic")

    def test_merge_candidate_results_prefers_non_empty_legacy_text(self):
        lexical_results = {
            "documents": [["recovered legal text"]],
            "metadatas": [[{"chunk_id": "same", "retrieval_layer": "lexical"}]],
            "distances": [[0.4]],
        }
        semantic_results = {
            "documents": [[""]],
            "metadatas": [[{"chunk_id": "same", "retrieval_layer": "semantic"}]],
            "distances": [[0.1]],
        }

        merged = merge_candidate_results(semantic_results, lexical_results, question="q")

        self.assertEqual(merged["documents"][0][0], "recovered legal text")
        self.assertEqual(merged["metadatas"][0][0]["retrieval_layers"], "lexical|semantic")

    def test_legacy_record_text_recovers_nested_document_text(self):
        record = {
            "text": "",
            "document_document": {
                "text": "",
                "raw_payload": {"content": "legacy content"},
            },
        }

        self.assertEqual(legacy_record_text(record), "legacy content")

    def test_summary_only_chunks_are_detected(self):
        summary_text = (
            "\u0627\u0644\u0639\u0646\u0648\u0627\u0646: \u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633\n"
            "\u0627\u0644\u0634\u0631\u062d \u0627\u0644\u062a\u0641\u0635\u064a\u0644\u064a: \u0647\u0630\u0627 \u0648\u0635\u0641 \u0645\u0648\u0644\u062f \u0648\u0644\u064a\u0633 \u0646\u0635\u0627 \u0623\u0635\u0644\u064a\u0627."
        )
        source_text = (
            "\u0642\u0631\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 "
            "\u0641\u064a \u062c\u0644\u0633\u062a\u0647 \u0627\u0644\u0645\u0646\u0639\u0642\u062f\u0629 \u0641\u064a 29/10/2024 "
            "\u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629 \u0639\u0644\u0649 \u0627\u0644\u0637\u0644\u0628."
        )

        self.assertTrue(is_summary_only_chunk_text(summary_text))
        self.assertFalse(is_summary_only_chunk_text(source_text))


if __name__ == "__main__":
    unittest.main()
