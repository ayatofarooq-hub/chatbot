"""Extract text from every PDF in the configured source folder."""

from pathlib import Path

import fitz  # PyMuPDF

from config import EXTRACTED_TEXT_FOLDER, PDF_FOLDER
from text_cleaning import clean_text


def extract_pdf(pdf_path: Path) -> tuple[int, int]:
    """Extract one PDF and return its page count and extracted character count."""

    output_path = EXTRACTED_TEXT_FOLDER / f"{pdf_path.stem}.txt"
    page_sections = []
    total_characters = 0

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            # Cleaning is deliberately conservative because punctuation,
            # diacritics, and exact letter forms can affect legal meaning.
            page_text = clean_text(page.get_text())
            total_characters += len(page_text)
            page_sections.append(f"--- PAGE {page_number} ---\n{page_text}")

        output_text = "\n\n".join(page_sections)
        output_path.write_text(output_text, encoding="utf-8")

        return document.page_count, total_characters


def main() -> None:
    """Extract all PDF files and print a short report."""

    EXTRACTED_TEXT_FOLDER.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(
        path for path in PDF_FOLDER.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"
    )

    if not pdf_files:
        print(f"No PDF files found in: {PDF_FOLDER}")
        return

    print("PDF extraction report")
    print("-" * 60)

    for pdf_path in pdf_files:
        page_count, character_count = extract_pdf(pdf_path)
        print(
            f"{pdf_path.name} | "
            f"pages: {page_count} | "
            f"characters: {character_count}"
        )


if __name__ == "__main__":
    main()
