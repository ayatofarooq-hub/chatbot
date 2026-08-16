"""JSON validation component for the standalone parser pipeline."""

from models.document import ParserJson
from models.standard_schema import (
    STANDARD_SCHEMA_VERSION,
    STANDARD_TOP_LEVEL_KEYS,
    find_banned_keys,
)


class JsonValidator:
    """Validate a ParserJson object before it is exported."""

    def validate(self, document: ParserJson) -> ParserJson:
        if not document.schema_version:
            raise ValueError("schema_version cannot be empty")

        if document.schema_version != STANDARD_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {STANDARD_SCHEMA_VERSION}")

        if not document.created_at:
            raise ValueError("created_at cannot be empty")

        if not document.metadata.source_name:
            raise ValueError("metadata.source_name cannot be empty")

        if not document.document_type.document_type:
            raise ValueError("document_type.type cannot be empty")

        if not 0 <= document.document_type.confidence <= 1:
            raise ValueError("document_type.confidence must be between 0 and 1")

        if not document.legal_content.body:
            raise ValueError("legal_content.body cannot be empty")

        if not document.legal_content.paragraphs:
            raise ValueError("legal_content.paragraphs cannot be empty")

        if not isinstance(document.legal_content.items, list):
            raise ValueError("legal_content.items must be a list")

        if len(document.legal_content.items) != len(document.legal_content.paragraphs):
            raise ValueError("legal_content.items must preserve every paragraph")

        for index, item in enumerate(document.legal_content.items, start=1):
            if not isinstance(item, dict):
                raise ValueError("legal_content.items entries must be objects")
            if item.get("id") != index:
                raise ValueError("legal_content.items ids must be sequential")
            if item.get("text") != document.legal_content.paragraphs[index - 1]:
                raise ValueError("legal_content.items text must equal the complete source paragraph")
            if item.get("summary") is not None:
                raise ValueError("legal_content.items summary must be null")

        if not isinstance(document.legal_content.section_items, list):
            raise ValueError("legal_content.section_items must be a list")

        for index, item in enumerate(document.legal_content.section_items, start=1):
            if not isinstance(item, dict):
                raise ValueError("legal_content.section_items entries must be objects")
            if item.get("id") != index:
                raise ValueError("legal_content.section_items ids must be sequential")
            if not isinstance(item.get("text"), str) or not item["text"]:
                raise ValueError("legal_content.section_items text must be a non-empty string")
            for key in ("entities", "money", "dates", "references"):
                if not isinstance(item.get(key), list):
                    raise ValueError(f"legal_content.section_items {key} must be a list")

        section_paragraphs: list[str] = []
        for item in document.legal_content.section_items:
            section_paragraphs.extend(item["text"].split("\n"))
        if section_paragraphs != document.legal_content.paragraphs:
            raise ValueError("legal_content.section_items must contain every paragraph exactly once and in order")

        required_entity_keys = (
            "ministries",
            "companies",
            "committees",
            "authorities",
            "government_offices",
            "people",
            "projects",
            "councils",
        )
        if not isinstance(document.legal_content.legal_entities, dict):
            raise ValueError("legal_content.legal_entities must be a dictionary")
        for key in required_entity_keys:
            if not isinstance(document.legal_content.legal_entities.get(key), list):
                raise ValueError(f"legal_content.legal_entities.{key} must be a list")

        required_reference_keys = (
            "decision_numbers",
            "book_numbers",
            "law_numbers",
            "article_numbers",
            "recommendation_numbers",
        )
        if not isinstance(document.legal_content.references, dict):
            raise ValueError("legal_content.references must be a dictionary")
        for key in required_reference_keys:
            if not isinstance(document.legal_content.references.get(key), list):
                raise ValueError(f"legal_content.references.{key} must be a list")

        required_extracted_field_keys = (
            "money",
            "percentages",
            "years",
            "durations",
            "pipe_lengths",
            "diameters",
            "thickness",
            "quantities",
        )
        if not isinstance(document.legal_content.extracted_fields, dict):
            raise ValueError("legal_content.extracted_fields must be a dictionary")
        for key in required_extracted_field_keys:
            if not isinstance(document.legal_content.extracted_fields.get(key), list):
                raise ValueError(f"legal_content.extracted_fields.{key} must be a list")

        if not isinstance(document.legal_content.legal_references, list):
            raise ValueError("legal_content.legal_references must be a list")

        if not isinstance(document.legal_content.implementation_responsibilities, list):
            raise ValueError("legal_content.implementation_responsibilities must be a list")

        if not isinstance(document.legal_content.affected_entities, list):
            raise ValueError("legal_content.affected_entities must be a list")

        if not isinstance(document.legal_content.extraction_sources, dict):
            raise ValueError("legal_content.extraction_sources must be a dictionary")

        if document.llm_analysis is not None:
            if not isinstance(document.llm_analysis.legal_entities, list):
                raise ValueError("llm_analysis.legal_entities must be a list")
            if not isinstance(document.llm_analysis.structured_fields, dict):
                raise ValueError("llm_analysis.structured_fields must be a dictionary")

        document_dict = document.to_dict()
        if tuple(document_dict.keys()) != STANDARD_TOP_LEVEL_KEYS:
            raise ValueError("standard JSON top-level schema keys changed")

        banned_keys = find_banned_keys(document_dict)
        if banned_keys:
            raise ValueError(f"standard JSON contains banned retrieval/vector fields: {banned_keys}")

        return document
