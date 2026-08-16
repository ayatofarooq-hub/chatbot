from detectors.iraqi_government_detector import IraqiGovernmentDocumentDetector
from models.document import CleanedDocument, DocumentTypeDetection


def cleaned_document(text: str) -> CleanedDocument:
    return CleanedDocument(
        filename="document1.txt",
        extension=".txt",
        pages=[text],
        paragraphs=[text],
        tables=[],
        raw_text=text,
    )


def test_detector_classifies_cabinet_decision_by_rules():
    detection = IraqiGovernmentDocumentDetector().detect(
        cleaned_document("قرر مجلس الوزراء الموافقة على الطلب")
    )

    assert detection.document_type == "Cabinet Decision"
    assert detection.method == "rule"


def test_detector_handles_tatweel_in_cabinet_decision_terms():
    detection = IraqiGovernmentDocumentDetector().detect(
        cleaned_document("قـــــرار\nمجلــس الــــوزراء\nقــرّر مجلــس الــوزراء")
    )

    assert detection.document_type == "Cabinet Decision"
    assert detection.method == "rule"


def test_detector_uses_llm_only_when_rules_are_uncertain():
    class FakeClassifier:
        def classify(self, document):
            return DocumentTypeDetection("Ministerial Order", 0.9, "llm", [])

    detection = IraqiGovernmentDocumentDetector(FakeClassifier()).detect(
        cleaned_document("نص غير واضح")
    )

    assert detection.document_type == "Ministerial Order"
    assert detection.method == "llm"


def test_detector_classifies_requested_taxonomy_by_rules():
    detector = IraqiGovernmentDocumentDetector()

    samples = {
        "Law": "قانون رقم ١ لسنة ٢٠٢٦ باسم الشعب صوت مجلس النواب",
        "Regulation": "نظام رقم ٢ لسنة ٢٠٢٦",
        "Cabinet Recommendation": "إقرار توصية المجلس الوزاري للطاقة",
        "Ministerial Order": "أمر وزاري رقم ٣ لسنة ٢٠٢٦",
        "Official Letter": "وزارة الصحة العدد التاريخ الموضوع إلى",
        "Circular": "إعمام إلى كافة الوزارات",
        "Instruction": "تعليمات رقم ٤ لسنة ٢٠٢٦",
        "Council Resolution": "قرار مجلس المحافظة رقم ٥",
    }

    for expected_type, text in samples.items():
        assert detector.detect(cleaned_document(text)).document_type == expected_type
