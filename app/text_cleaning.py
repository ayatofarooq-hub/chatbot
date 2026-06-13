"""Conservative text cleaning for extracted Arabic legal documents."""

import re
import unicodedata


# Legal text must remain faithful to the source. These fixes are therefore
# limited to known PDF extraction errors rather than general spelling changes.
KNOWN_EXTRACTION_FIXES = {
    # PyMuPDF extracts this as ا ا ل ئ ت ا ل ف because of glyph ordering.
    "\u0627\u0627\u0644\u0626\u062a\u0627\u0644\u0641": "الائتلاف",
    # PyMuPDF places the hamza-bearing alef after the plain alef.
    "األمر": "الأمر",
}


def normalize_arabic_presentation_forms(text: str) -> str:
    """Convert Arabic display glyphs such as ``ﻻ`` into normal letters.

    Some PDFs store connected Arabic glyphs in Unicode presentation-form
    blocks. Normalizing only those glyphs avoids changing unrelated legal
    symbols, numbers, punctuation, or ordinary Arabic letters.
    """

    normalized_characters = []

    for character in text:
        code_point = ord(character)
        is_arabic_presentation_form = (
            0xFB50 <= code_point <= 0xFDFF
            or 0xFE70 <= code_point <= 0xFEFF
        )

        if is_arabic_presentation_form:
            normalized_characters.append(
                unicodedata.normalize("NFKC", character)
            )
        else:
            normalized_characters.append(character)

    return "".join(normalized_characters)


def clean_text(text: str) -> str:
    """Clean extracted text without changing its legal meaning."""

    text = normalize_arabic_presentation_forms(text)

    # Normalize line endings first so output is consistent across platforms.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Tabs and other horizontal whitespace become one normal space. Newlines
    # are handled separately so paragraphs and page separators are preserved.
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())

    # Keep paragraph breaks, but remove large runs of empty extracted lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Apply only explicitly reviewed fixes for recurring extraction mistakes.
    # This avoids aggressive Arabic normalization that could alter legal names
    # or distinctions such as ة/ه and أ/إ/آ.
    for incorrect, corrected in KNOWN_EXTRACTION_FIXES.items():
        text = text.replace(incorrect, corrected)

    return text.strip()
