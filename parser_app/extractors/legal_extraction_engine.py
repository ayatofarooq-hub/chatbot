"""Rule-first legal extraction engine."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from models.document import (
    CleanedDocument,
    DocumentMetadata,
    DocumentTypeDetection,
    LegalContent,
    LlmLegalAnalysis,
)


_LEGAL_REFERENCE = re.compile(
    r"(?:\u0642\u0627\u0646\u0648\u0646|\u0642\u0631\u0627\u0631|\u0646\u0638\u0627\u0645|\u062a\u0639\u0644\u064a\u0645\u0627\u062a|\u0627\u0645\u0631|\u0623\u0645\u0631)\s+"
    r"(?:\u0645\u062c\u0644\u0633\s+\u0627\u0644\u0648\u0632\u0631\u0627\u0621\s+)?"
    r"(?:[\u0621-\u064a\s]{0,80}?)?"
    r"(?:\u0631\u0642\u0645\s*)?\(?\s*[\d\u0660-\u0669]+(?:\s+\u0644\u0633\u0646\u0629\s+[\d\u0660-\u0669]+)?\s*\)?"
)
_RESPONSIBILITY_MARKERS = (
    "\u062a\u062a\u062d\u0645\u0644",
    "\u062a\u0644\u062a\u0632\u0645",
    "\u0644\u0623\u062e\u0630 \u0645\u0627 \u064a\u0642\u062a\u0636\u064a",
    "\u0644\u0627\u062e\u0630 \u0645\u0627 \u064a\u0642\u062a\u0636\u064a",
    "\u0644\u0644\u062a\u0623\u0634\u064a\u0631 \u0648\u0627\u0644\u0645\u062a\u0627\u0628\u0639\u0629",
)
_OUTCOME_MARKERS = (
    "\u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629",
    "\u0627\u0633\u062a\u062b\u0646\u0627\u0621",
    "\u0625\u0642\u0631\u0627\u0631",
    "\u0627\u0642\u0631\u0627\u0631",
    "\u0642\u0631\u0631",
    "\u0642\u0631\u0651\u0631",
)
_ENTITY_PATTERN = re.compile(
    r"(?:\u0648\u0632\u0627\u0631\u0629|"
    r"\u0627\u0644\u0623\u0645\u0627\u0646\u0629\s+\u0627\u0644\u0639\u0627\u0645\u0629|"
    r"\u0627\u0644\u0627\u0645\u0627\u0646\u0629\s+\u0627\u0644\u0639\u0627\u0645\u0629|"
    r"\u0645\u062c\u0644\u0633|"
    r"\u0647\u064a\u0626\u0629|"
    r"\u0634\u0631\u0643\u0629|"
    r"\u062f\u064a\u0648\u0627\u0646)\s+[^/،.\n]{2,80}"
)
_DATE_VALUE = re.compile(r"[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}")
_MONEY_VALUE = re.compile(
    r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)*\s*\)?\s*"
    r"(?:\u062f\u064a\u0646\u0627\u0631|\u062f\u0648\u0644\u0627\u0631|\u0633\u0646\u062a|USD|\$)"
)
_PERCENTAGE_VALUE = re.compile(r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)?\s*%\s*\)?")
_YEAR_VALUE = re.compile(r"(?<![/\d\u0660-\u0669])[\d\u0660-\u0669]{4}(?![/\d\u0660-\u0669])")
_DURATION_VALUE = re.compile(
    r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)*\s*\)?\s*"
    r"(?:\u064a\u0648\u0645|\u064a\u0648\u0645\u0627|\u064a\u0648\u0645\u064b\u0627|\u064a\u0648\u0645\u0627\u064b|\u0634\u0647\u0631|\u0634\u0647\u0631\u0627|\u0634\u0647\u0631\u064b\u0627|\u0633\u0646\u0629|\u0633\u0646\u0648\u0627\u062a)"
)
_PIPE_LENGTH_VALUE = re.compile(
    r"(?:\u0628\u0637\u0648\u0644|\u0637\u0648\u0644(?:\u0647\u0627|\u0647)?)\s*"
    r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)*\s*\)?\s*"
    r"(?:\u0643\u0645|\u0645\u062a\u0631|\u0645)"
)
_DIAMETER_VALUE = re.compile(
    r"(?:\u0628\u0642\u0637\u0631|\u0642\u0637\u0631(?:\u0647\u0627|\u0647)?)\s*"
    r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)*\s*\)?\s*"
    r"(?:\u0645\u0644\u0645|\u0633\u0645|\u0645\u062a\u0631|\u0627\u0646\u062c|\u0625\u0646\u062c)"
)
_THICKNESS_VALUE = re.compile(
    r"(?:\u0628\u0633\u0645\u0643|\u0633\u0645\u0643(?:\u0647\u0627|\u0647)?)\s*"
    r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)*\s*\)?\s*"
    r"(?:\u0645\u0644\u0645|\u0633\u0645|\u0645\u062a\u0631|\u0627\u0646\u062c|\u0625\u0646\u062c)"
)
_QUANTITY_VALUE = re.compile(
    r"(?:\u0628\u0639\u062f\u062f|\u0639\u062f\u062f|\u0643\u0645\u064a\u0629)\s*"
    r"\(?\s*[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)*\s*\)?\s*"
    r"(?:[\u0621-\u064aA-Za-z]{2,30})?"
)
_NUMBERED_ITEM = re.compile(
    r"^\s*(?:"
    r"[\d\u0660-\u0669]+\s*[\).:-]|"
    r"\u0627\u0644\u0645\u0627\u062f\u0629\s*\(?\s*[\d\u0660-\u0669]+|"
    r"\u0627\u0648\u0644\u0627|\u0627\u0648\u0644\u064b\u0627|\u0627\u0648\u0644\u0627\u064b|"
    r"\u062b\u0627\u0646\u064a\u0627|\u062b\u0627\u0646\u064a\u064b\u0627|\u062b\u0627\u0646\u064a\u0627\u064b|"
    r"\u062b\u0627\u0644\u062b\u0627|\u062b\u0627\u0644\u062b\u064b\u0627|\u062b\u0627\u0644\u062b\u0627\u064b|"
    r"\u0631\u0627\u0628\u0639\u0627|\u0631\u0627\u0628\u0639\u064b\u0627|\u0631\u0627\u0628\u0639\u0627\u064b|"
    r"\u062e\u0627\u0645\u0633\u0627|\u062e\u0627\u0645\u0633\u064b\u0627|\u062e\u0627\u0645\u0633\u0627\u064b|"
    r"\u0633\u0627\u062f\u0633\u0627|\u0633\u0627\u062f\u0633\u064b\u0627|\u0633\u0627\u062f\u0633\u0627\u064b|"
    r"\u0633\u0627\u0628\u0639\u0627|\u0633\u0627\u0628\u0639\u064b\u0627|\u0633\u0627\u0628\u0639\u0627\u064b|"
    r"\u062b\u0627\u0645\u0646\u0627|\u062b\u0627\u0645\u0646\u064b\u0627|\u062b\u0627\u0645\u0646\u0627\u064b|"
    r"\u062a\u0627\u0633\u0639\u0627|\u062a\u0627\u0633\u0639\u064b\u0627|\u062a\u0627\u0633\u0639\u0627\u064b|"
    r"\u0639\u0627\u0634\u0631\u0627|\u0639\u0627\u0634\u0631\u064b\u0627|\u0639\u0627\u0634\u0631\u0627\u064b"
    r")"
)
_ENTITY_STOP = r"(?=\s+(?:و)?(?:وزارة|شركة|لجنة|اللجنة|هيئة|مجلس|مكتب|ديوان|مشروع)|[/،,.\n()]|$)"
_ENTITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "ministries": re.compile(r"\u0648\u0632\u0627\u0631\u0629\s+[\u0621-\u064a\s]{2,80}?" + _ENTITY_STOP),
    "companies": re.compile(r"\u0634\u0631\u0643\u0629\s+[^/،,.\n]{2,100}?" + _ENTITY_STOP),
    "committees": re.compile(r"(?:\u0627\u0644\u0644\u062c\u0646\u0629|\u0644\u062c\u0646\u0629)\s+[\u0621-\u064a\s]{2,100}?" + _ENTITY_STOP),
    "authorities": re.compile(r"\u0647\u064a\u0626\u0629\s+[\u0621-\u064a\s]{2,100}?" + _ENTITY_STOP),
    "government_offices": re.compile(
        r"(?:\u0645\u0643\u062a\u0628|\u062f\u064a\u0648\u0627\u0646|\u0627\u0644\u0623\u0645\u0627\u0646\u0629\s+\u0627\u0644\u0639\u0627\u0645\u0629|\u0627\u0644\u0627\u0645\u0627\u0646\u0629\s+\u0627\u0644\u0639\u0627\u0645\u0629)\s+[^/،,.\n]{2,100}?"
        + _ENTITY_STOP
    ),
    "people": re.compile(r"(?:\u062f\.|\u062f\u0643\u062a\u0648\u0631|\u0627\u0644\u062f\u0643\u062a\u0648\u0631|\u0627\u0644\u0633\u064a\u062f|\u0627\u0644\u0633\u064a\u062f\u0629)\s+[^/،,.\n-]{2,80}"),
    "projects": re.compile(r"\u0645\u0634\u0631\u0648\u0639\s+[^/،,.\n]{2,120}?" + _ENTITY_STOP),
    "councils": re.compile(r"(?:\u0645\u062c\u0644\u0633|\u0627\u0644\u0645\u062c\u0644\u0633)\s+[\u0621-\u064a\s]{2,100}?" + _ENTITY_STOP),
}
_LEGAL_ENTITY_KEYS = (
    "ministries",
    "companies",
    "committees",
    "authorities",
    "government_offices",
    "people",
    "projects",
    "councils",
)
_REFERENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "decision_numbers": re.compile(
        r"\u0642\u0631\u0627\u0631(?:\s+\u0645\u062c\u0644\u0633\s+\u0627\u0644\u0648\u0632\u0631\u0627\u0621)?"
        r"(?:\s+\u0631\u0642\u0645)?\s*\(?\s*[\d\u0660-\u0669]+"
        r"(?:\s+\u0644\u0633\u0646\u0629\s+[\d\u0660-\u0669]+)?\s*\)?"
    ),
    "book_numbers": re.compile(
        r"(?:\u0643\u062a\u0627\u0628(?:\u0647\u0627|\u0647|\u0643\u0645|\u0646\u0627)?"
        r"(?:\s+[\u0621-\u064a]+){0,8}?\s+)?"
        r"(?:\u0627\u0644\u0645\u0631\u0642\u0645(?:\u0629)?\s+\u0628\u0627\u0644\u0639\u062f\u062f|\u0628\u0627\u0644\u0639\u062f\u062f|\u0627\u0644\u0639\u062f\u062f)"
        r"\s*\(?\s*[^)\n]{1,50}\)"
    ),
    "law_numbers": re.compile(
        r"\u0642\u0627\u0646\u0648\u0646\s+(?:\u0631\u0642\u0645\s*)?\(?\s*[\d\u0660-\u0669]+"
        r"(?:\s+\u0644\u0633\u0646\u0629\s+[\d\u0660-\u0669]+)?\s*\)?"
    ),
    "article_numbers": re.compile(
        r"\u0627\u0644\u0645\u0627\u062f\u0629\s*\(\s*[^)]{1,60}\)"
    ),
    "recommendation_numbers": re.compile(
        r"\u062a\u0648\u0635\u064a\u0629(?:\s+[\u0621-\u064a]+){0,10}?\s*"
        r"\(\s*[^)]*[\d\u0660-\u0669][^)]*\)\s*"
        r"(?:\u0644\u0633\u0646\u0629\s+[\d\u0660-\u0669]+)?"
    ),
}
_REFERENCE_KEYS = (
    "decision_numbers",
    "book_numbers",
    "law_numbers",
    "article_numbers",
    "recommendation_numbers",
)
_EXTRACTED_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "money": _MONEY_VALUE,
    "percentages": _PERCENTAGE_VALUE,
    "years": _YEAR_VALUE,
    "durations": _DURATION_VALUE,
    "pipe_lengths": _PIPE_LENGTH_VALUE,
    "diameters": _DIAMETER_VALUE,
    "thickness": _THICKNESS_VALUE,
    "quantities": _QUANTITY_VALUE,
}
_EXTRACTED_FIELD_KEYS = (
    "money",
    "percentages",
    "years",
    "durations",
    "pipe_lengths",
    "diameters",
    "thickness",
    "quantities",
)


class LegalExtractionEngine:
    """Combine rules, metadata, and optional LLM fills for legal fields."""

    LLM_FILL_FIELDS = (
        "legal_objective",
        "executive_summary",
        "implementation_responsibilities",
        "decision_outcome",
        "legal_references",
        "affected_entities",
    )

    def extract(
        self,
        document: CleanedDocument,
        metadata: DocumentMetadata,
        document_type: DocumentTypeDetection,
        llm_analysis: LlmLegalAnalysis | None = None,
        original_body: str | None = None,
        original_paragraphs: list[str] | None = None,
    ) -> LegalContent:
        output_paragraphs = original_paragraphs if original_paragraphs is not None else document.paragraphs
        output_body = original_body if original_body is not None else document.raw_text
        title = output_paragraphs[0] if output_paragraphs else metadata.stem
        extraction_sources: dict[str, str] = {}

        legal_objective = metadata.subject
        if legal_objective:
            extraction_sources["legal_objective"] = "metadata"

        legal_references = self._legal_references(output_body)
        if legal_references:
            extraction_sources["legal_references"] = "rules"

        responsibilities = self._implementation_responsibilities(output_paragraphs)
        if responsibilities:
            extraction_sources["implementation_responsibilities"] = "rules"

        decision_outcome = self._decision_outcome(output_paragraphs)
        if decision_outcome:
            extraction_sources["decision_outcome"] = "rules"

        affected_entities = self._affected_entities(output_body, metadata)
        if affected_entities:
            extraction_sources["affected_entities"] = "rules+metadata"

        content = LegalContent(
            title=title,
            body=output_body,
            paragraphs=output_paragraphs,
            items=self._legal_items(output_paragraphs),
            section_items=self._section_items(output_paragraphs),
            legal_entities=self._legal_entities(output_body, metadata),
            references=self._references(output_body),
            extracted_fields=self._extracted_fields(output_body),
            legal_references=legal_references,
            legal_objective=legal_objective,
            executive_summary=None,
            implementation_responsibilities=responsibilities,
            decision_outcome=decision_outcome,
            affected_entities=affected_entities,
            extraction_sources=extraction_sources,
        )

        if llm_analysis is not None:
            content = self._fill_from_llm(content, llm_analysis)

        return content

    def missing_llm_fields(self, content: LegalContent) -> list[str]:
        missing: list[str] = []
        for field_name in self.LLM_FILL_FIELDS:
            value = getattr(content, field_name)
            if value is None or value == []:
                missing.append(field_name)
        return missing

    def _fill_from_llm(self, content: LegalContent, analysis: LlmLegalAnalysis) -> LegalContent:
        structured_fields = analysis.structured_fields
        updates: dict[str, Any] = {}
        sources = dict(content.extraction_sources)

        self._fill_string(updates, sources, "legal_objective", content.legal_objective, structured_fields.get("legal_objective") or analysis.legal_meaning)
        self._fill_string(updates, sources, "executive_summary", content.executive_summary, structured_fields.get("executive_summary") or analysis.summary)
        self._fill_string(updates, sources, "decision_outcome", content.decision_outcome, structured_fields.get("decision_outcome"))
        self._fill_list(updates, sources, "implementation_responsibilities", content.implementation_responsibilities, structured_fields.get("implementation_responsibilities") or structured_fields.get("obligations"))
        self._fill_list(updates, sources, "legal_references", content.legal_references, structured_fields.get("legal_references") or structured_fields.get("referenced_laws") or structured_fields.get("referenced_decisions"))
        self._fill_list(updates, sources, "affected_entities", content.affected_entities, structured_fields.get("affected_entities") or [entity.get("name") for entity in analysis.legal_entities if isinstance(entity.get("name"), str)])

        if updates:
            updates["extraction_sources"] = sources
            return replace(content, **updates)
        return content

    def _fill_string(
        self,
        updates: dict[str, Any],
        sources: dict[str, str],
        field_name: str,
        current_value: str | None,
        llm_value: Any,
    ) -> None:
        if current_value:
            return
        if isinstance(llm_value, str) and llm_value.strip():
            updates[field_name] = llm_value.strip()
            sources[field_name] = "llm"

    def _fill_list(
        self,
        updates: dict[str, Any],
        sources: dict[str, str],
        field_name: str,
        current_value: list[str],
        llm_value: Any,
    ) -> None:
        if current_value:
            return
        values = self._string_list(llm_value)
        if values:
            updates[field_name] = values
            sources[field_name] = "llm"

    def _legal_references(self, text: str) -> list[str]:
        return sorted({self._clean_reference_value(match) for match in _LEGAL_REFERENCE.findall(text) if self._clean_reference_value(match)})

    def _implementation_responsibilities(self, paragraphs: list[str]) -> list[str]:
        responsibilities: list[str] = []
        for paragraph in paragraphs:
            normalized = self._normalize_arabic(paragraph)
            if any(marker in normalized for marker in _RESPONSIBILITY_MARKERS):
                responsibilities.append(paragraph)
        return self._unique(responsibilities)

    def _decision_outcome(self, paragraphs: list[str]) -> str | None:
        operative_matches: list[str] = []
        fallback_matches: list[str] = []
        for paragraph in paragraphs:
            normalized = self._normalize_arabic(paragraph)
            if normalized.startswith("الموضوع"):
                continue
            if "قرر" in normalized:
                operative_matches.append(paragraph)
            elif any(marker in normalized for marker in _OUTCOME_MARKERS):
                fallback_matches.append(paragraph)
        if operative_matches:
            return operative_matches[0]
        if fallback_matches:
            return fallback_matches[0]
        return None

    def _affected_entities(self, text: str, metadata: DocumentMetadata) -> list[str]:
        entities = []
        if metadata.ministry:
            entities.append(metadata.ministry)
        entities.extend(metadata.distribution_list)
        entities.extend(self._clean_value(match) for match in _ENTITY_PATTERN.findall(text))
        return self._unique(value for value in entities if value)

    def _legal_items(self, paragraphs: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "id": index,
                "type": self._paragraph_type(paragraph),
                "text": paragraph,
                "summary": None,
            }
            for index, paragraph in enumerate(paragraphs, start=1)
        ]

    def _paragraph_type(self, paragraph: str) -> str:
        normalized = self._normalize_arabic(paragraph)
        if any(marker in normalized for marker in ("\u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629", "\u064a\u0648\u0627\u0641\u0642")):
            return "Approval"
        if any(marker in normalized for marker in ("\u0627\u0633\u062a\u062b\u0646\u0627\u0621", "\u064a\u0633\u062a\u062b\u0646\u0649")):
            return "Exception"
        if any(marker in normalized for marker in ("\u0627\u0642\u0631\u0627\u0631", "\u0625\u0642\u0631\u0627\u0631")):
            return "Ratification"
        if any(marker in normalized for marker in ("\u0642\u0631\u0631", "\u0642\u0631\u0651\u0631")):
            return "Decision"
        if any(marker in normalized for marker in ("\u062a\u062a\u062d\u0645\u0644", "\u062a\u0644\u062a\u0632\u0645", "\u0644\u0627\u062e\u0630 \u0645\u0627 \u064a\u0642\u062a\u0636\u064a")):
            return "Implementation"
        if _LEGAL_REFERENCE.search(paragraph):
            return "Legal Reference"
        return "Paragraph"

    def _section_items(self, paragraphs: list[str]) -> list[dict[str, Any]]:
        sections: list[list[str]] = []
        current: list[str] | None = None

        for paragraph in paragraphs:
            if self._is_numbered_item(paragraph):
                if current:
                    sections.append(current)
                current = [paragraph]
            elif current is not None:
                current.append(paragraph)
            else:
                sections.append([paragraph])

        if current:
            sections.append(current)

        items: list[dict[str, Any]] = []
        for index, section in enumerate(sections, start=1):
            text = "\n".join(section)
            items.append(
                {
                    "id": index,
                    "text": text,
                    "entities": self._entities_in_text(text),
                    "money": self._money_values(text),
                    "dates": self._date_values(text),
                    "references": self._legal_references(text),
                }
            )
        return items

    def _is_numbered_item(self, paragraph: str) -> bool:
        return bool(_NUMBERED_ITEM.match(self._normalize_arabic(paragraph)))

    def _entities_in_text(self, text: str) -> list[str]:
        return self._unique(self._clean_value(match) for match in _ENTITY_PATTERN.findall(text) if self._clean_value(match))

    def _money_values(self, text: str) -> list[str]:
        return self._unique(self._clean_reference_value(match) for match in _MONEY_VALUE.findall(text) if self._clean_reference_value(match))

    def _date_values(self, text: str) -> list[str]:
        return self._unique(self._clean_value(match) for match in _DATE_VALUE.findall(text) if self._clean_value(match))

    def _legal_entities(self, text: str, metadata: DocumentMetadata) -> dict[str, list[str]]:
        entities = {key: [] for key in _LEGAL_ENTITY_KEYS}
        for key, pattern in _ENTITY_PATTERNS.items():
            entities[key].extend(
                self._clean_entity_value(match)
                for match in pattern.findall(text)
                if self._clean_entity_value(match)
            )

        if metadata.ministry:
            entities["ministries"].append(metadata.ministry)
        if metadata.department:
            entities["government_offices"].append(metadata.department)
        if metadata.sender:
            self._append_sender_entities(entities, metadata.sender)
        if metadata.recipient:
            self._append_sender_entities(entities, metadata.recipient)
        if metadata.signature:
            person = metadata.signature.split(" - ", 1)[0].strip()
            if person:
                entities["people"].append(person)

        return {key: self._unique(value for value in values if value) for key, values in entities.items()}

    def _references(self, text: str) -> dict[str, list[str]]:
        return {
            key: self._unique(
                self._clean_reference_value(match)
                for match in pattern.findall(text)
                if self._clean_reference_value(match)
            )
            for key, pattern in _REFERENCE_PATTERNS.items()
        }

    def _extracted_fields(self, text: str) -> dict[str, list[str]]:
        return {
            key: self._unique(
                self._clean_reference_value(match)
                for match in pattern.findall(text)
                if self._clean_reference_value(match)
            )
            for key, pattern in _EXTRACTED_FIELD_PATTERNS.items()
        }

    def _append_sender_entities(self, entities: dict[str, list[str]], value: str) -> None:
        for part in (part.strip() for part in value.split("/") if part.strip()):
            normalized = self._normalize_arabic(part)
            if normalized.startswith("\u0648\u0632\u0627\u0631\u0629"):
                entities["ministries"].append(part)
            elif normalized.startswith("\u0645\u062c\u0644\u0633") or normalized.startswith("\u0627\u0644\u0645\u062c\u0644\u0633"):
                entities["councils"].append(part)
            elif normalized.startswith("\u0647\u064a\u0626\u0629"):
                entities["authorities"].append(part)
            elif normalized.startswith(("\u0645\u0643\u062a\u0628", "\u062f\u064a\u0648\u0627\u0646", "\u0627\u0644\u0627\u0645\u0627\u0646\u0629 \u0627\u0644\u0639\u0627\u0645\u0629")):
                entities["government_offices"].append(part)

    def _clean_entity_value(self, value: str | None) -> str | None:
        cleaned = self._clean_reference_value(value)
        if not cleaned:
            return None
        cleaned = re.sub(r"\s+(?:\u0641\u064a|\u0628\u0634\u0623\u0646|\u0639\u0646|\u0627\u0644\u0649|\u0625\u0644\u0649)$", "", cleaned)
        return cleaned.strip() or None

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return self._unique(item.strip() for item in value if isinstance(item, str) and item.strip())

    def _unique(self, values: Any) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = self._normalize_arabic(value)
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _clean_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n:-/،.()")
        return cleaned or None

    def _clean_reference_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n:-/،.")
        return cleaned or None

    def _normalize_arabic(self, value: str) -> str:
        normalized = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
        normalized = normalized.replace("\u0623", "\u0627")
        normalized = normalized.replace("\u0625", "\u0627")
        normalized = normalized.replace("\u0622", "\u0627")
        normalized = normalized.replace("\u0649", "\u064a")
        return normalized
