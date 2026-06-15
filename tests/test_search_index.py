"""Tests for Arabic-aware hybrid retrieval ranking."""

import unittest

from app.search_index import (
    lexical_relevance,
    normalize_for_search,
    rerank_results,
)


class SearchIndexTests(unittest.TestCase):
    def test_normalization_unifies_arabic_letters_and_digits(self):
        self.assertEqual(
            normalize_for_search("إنتخابات ٢٠٢٠"),
            "انتخابات 2020",
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


if __name__ == "__main__":
    unittest.main()
