"""Read DOCX files from the input folder and save JSON."""

import json
from pathlib import Path
import sys
from xml.etree import ElementTree
from zipfile import ZipFile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import (
    ALLOWED_BATCH_SIZES,
    DEFAULT_BATCH_SIZE,
    INPUT_FOLDER,
    OUTPUT_FOLDER,
    create_data_directories,
)
from app.classifiers import classify_paragraph
from app.chunking import build_chunks_from_output_json, load_output_chunks
from app.chatbot import answer_with_qwen_3b
from app.embeddings import create_chunk_embeddings
from app.extractors import (
    DocumentInfo,
    RegexMetadata,
    extract_document_info_with_qwen,
    extract_regex_metadata,
)
from app.json_builder import build_document_json, save_document_json
from app.schemas import DocumentModel, ParagraphModel
from app.utils import setup_pipeline_logging, validate_document_json


logger = setup_pipeline_logging()


def list_docx_files() -> list[Path]:
    """Return DOCX files from the input folder."""

    return sorted(INPUT_FOLDER.glob("*.docx"))


def list_unsupported_word_files() -> list[Path]:
    """Return Word files that are not supported by the DOCX-only reader."""

    return sorted(INPUT_FOLDER.glob("*.doc"))


def validate_batch_size(batch_size: int) -> None:
    """Validate supported DOCX batch sizes."""

    if batch_size not in ALLOWED_BATCH_SIZES:
        allowed_sizes = ", ".join(str(size) for size in ALLOWED_BATCH_SIZES)
        raise ValueError(f"Unsupported batch size: {batch_size}. Use one of: {allowed_sizes}")


def batch_docx_files(files: list[Path], batch_size: int = DEFAULT_BATCH_SIZE) -> list[list[Path]]:
    """Split DOCX files into batches."""

    validate_batch_size(batch_size)
    return [files[index : index + batch_size] for index in range(0, len(files), batch_size)]


def read_docx_xml(docx_file: Path) -> ElementTree.Element:
    """Read the main XML document from a DOCX file."""
    with ZipFile(docx_file) as archive:
        document_xml = archive.read("word/document.xml")

    return ElementTree.fromstring(document_xml)


def collect_text(element: ElementTree.Element) -> str:
    """Collect text from a Word XML element in document order."""

    namespace_uri = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    parts: list[str] = []

    for node in element.iter():
        if node.tag == f"{{{namespace_uri}}}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{{{namespace_uri}}}tab":
            parts.append("\t")
        elif node.tag == f"{{{namespace_uri}}}br":
            parts.append("\n")

    return "".join(parts)


def read_docx_document(docx_file: Path) -> DocumentModel:
    """Read a DOCX file into the document model."""

    root = read_docx_xml(docx_file)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraph_texts: list[str] = []
    tables: list[list[list[str]]] = []

    for paragraph in root.findall(".//w:p", namespace):
        paragraph_texts.append(collect_text(paragraph))

    for table in root.findall(".//w:tbl", namespace):
        rows: list[list[str]] = []
        for row in table.findall("./w:tr", namespace):
            rows.append([collect_text(cell) for cell in row.findall("./w:tc", namespace)])
        tables.append(rows)

    title = next((paragraph for paragraph in paragraph_texts if paragraph.strip()), "")
    paragraphs = [
        ParagraphModel(text=paragraph, type=classify_paragraph(paragraph))
        for paragraph in paragraph_texts
    ]

    return DocumentModel(
        source_file=docx_file.name,
        title=title,
        paragraphs=paragraphs,
        tables=tables,
        sections=[],
    )


def read_docx_text(docx_file: Path) -> str:
    """Read text from a DOCX file while preserving paragraph order."""

    document = read_docx_document(docx_file)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def print_docx_texts() -> None:
    """Print only the text content of DOCX files."""

    for docx_file in list_docx_files():
        text = read_docx_text(docx_file)
        if text:
            print(text)


def read_docx_metadata(docx_file: Path) -> RegexMetadata:
    """Extract simple regex metadata from a DOCX file."""

    document = read_docx_document(docx_file)
    return extract_regex_metadata(document)


def read_docx_document_info(docx_file: Path) -> DocumentInfo:
    """Extract title, document type, and two-line summary with Qwen 1.5B."""

    text = read_docx_text(docx_file)
    return extract_document_info_with_qwen(text)


def build_docx_json(docx_file: Path) -> dict:
    """Build final JSON for one DOCX file."""

    logger.info("Read File: %s", docx_file.name)
    document = read_docx_document(docx_file)
    logger.info("Extract: %s", docx_file.name)
    regex_metadata = extract_regex_metadata(document)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    logger.info("LLM: %s", docx_file.name)
    qwen_info = extract_document_info_with_qwen(text)
    payload = build_document_json(document, regex_metadata, qwen_info)
    validate_document_json(payload)
    return payload


def print_docx_json() -> None:
    """Print one JSON payload for each DOCX input file."""

    for docx_file in list_docx_files():
        payload = build_docx_json(docx_file)
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def write_docx_json_files(batch_size: int = DEFAULT_BATCH_SIZE) -> None:
    """Save JSON payloads inside data/output using batch processing."""

    logger.info("Start")
    for unsupported_file in list_unsupported_word_files():
        logger.warning("Warning: unsupported Word format .doc: %s", unsupported_file.name)
    batches = batch_docx_files(list_docx_files(), batch_size)
    for batch_number, batch in enumerate(batches, start=1):
        logger.info("Batch: %s files=%s", batch_number, len(batch))
        for docx_file in batch:
            payload = build_docx_json(docx_file)
            output_file = OUTPUT_FOLDER / f"{docx_file.stem}.json"
            logger.info("Save JSON: %s", output_file.name)
            save_document_json(payload, output_file)
    logger.info("Finished")


def list_output_json_files() -> list[Path]:
    """Return generated JSON files from data/output."""

    return sorted(OUTPUT_FOLDER.glob("*.json"))


def index_output_json_files() -> int:
    """Index generated JSON files in ChromaDB and write citation_registry.json."""

    json_files = list_output_json_files()
    if not json_files:
        logger.info("ChromaDB: no JSON files")
        return 0

    logger.info("Chunking: %s files", len(json_files))
    chunks = load_output_chunks(json_files)
    if not chunks:
        logger.info("ChromaDB: no chunks")
        return 0

    logger.info("Embedding: %s chunks", len(chunks))
    embeddings = create_chunk_embeddings(chunks)
    logger.info("ChromaDB: %s chunks", len(chunks))
    import chromadb

    from app.build_index import add_chunks, reset_collection
    from app.citation_registry import save_registry
    from app.config import CHROMA_FOLDER

    CHROMA_FOLDER.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
    collection = reset_collection(client)
    add_chunks(collection, chunks, embeddings)
    save_registry(chunks)
    logger.info("citation_registry.json")
    return len(chunks)


def process_pipeline() -> None:
    """Run DOCX extraction, JSON save, ChromaDB indexing, and citation registry."""

    write_docx_json_files()
    index_output_json_files()
    logger.info("Qwen 3B Chatbot: ready")


def main() -> None:
    """Prepare local folders and save JSON from DOCX inputs."""

    create_data_directories()
    process_pipeline()


if __name__ == "__main__":
    main()
