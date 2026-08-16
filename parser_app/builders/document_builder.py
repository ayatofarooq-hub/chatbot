"""JSON building component for the standalone parser pipeline."""

from datetime import datetime, timezone

from models.standard_schema import STANDARD_SCHEMA_VERSION
from models.document import (
    DocumentMetadata,
    DocumentTypeDetection,
    LegalContent,
    LlmLegalAnalysis,
    ParserJson,
)


class JsonBuilder:
    """Build the final parser JSON object from extracted components."""

    def build(
        self,
        metadata: DocumentMetadata,
        document_type: DocumentTypeDetection,
        legal_content: LegalContent,
        llm_analysis: LlmLegalAnalysis | None = None,
    ) -> ParserJson:
        return ParserJson(
            schema_version=STANDARD_SCHEMA_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
            document_type=document_type,
            legal_content=legal_content,
            llm_analysis=llm_analysis,
        )
