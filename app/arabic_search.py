"""Arabic normalization helpers used only for search and ranking."""

from __future__ import annotations

import re
import unicodedata


ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
ARABIC_INDIC_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
    "01234567890123456789",
)
TOKEN_PATTERN = re.compile(r"[\u0600-\u06ff]+|[0-9]+(?:[/-][0-9]+)*(?:\.[0-9]+)*")
NON_SEARCH_CHARS_PATTERN = re.compile(r"[^\w\u0600-\u06ff./-]+", re.UNICODE)


STOP_WORDS = {
    "اجابه",
    "اريد",
    "او",
    "الى",
    "عن",
    "على",
    "في",
    "ما",
    "ماهي",
    "من",
    "هل",
    "هو",
    "هي",
    "و",
}


def normalize_arabic_for_search(text: object) -> str:
    """Normalize Arabic spelling for search without changing source text."""

    value = unicodedata.normalize("NFKC", str(text or "")).translate(ARABIC_INDIC_DIGITS)
    value = ARABIC_DIACRITICS_PATTERN.sub("", value)
    value = value.replace("\u0640", "")
    value = re.sub(r"[\u0623\u0625\u0622\u0671]", "\u0627", value)
    value = value.replace("\u0649", "\u064a")
    value = value.replace("\u0624", "\u0648").replace("\u0626", "\u064a")
    value = NON_SEARCH_CHARS_PATTERN.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def _token_variants(token: str) -> set[str]:
    variants = {token}
    if token.startswith("ال") and len(token) > 3:
        variants.add(token[2:])
    if token.startswith("و") and len(token) > 3:
        variants.add(token[1:])
        if token.startswith("وال") and len(token) > 4:
            variants.add(token[3:])
    if token.isdigit() and len(token) > 1:
        variants.add(token[::-1])
    return {variant for variant in variants if variant and variant not in STOP_WORDS}


def tokenize_arabic_search(text: object) -> list[str]:
    """Return normalized Arabic/numeric tokens with lightweight variants."""

    normalized = normalize_arabic_for_search(text)
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(normalized):
        if token in STOP_WORDS or (not token.isdigit() and len(token) <= 1):
            continue
        tokens.extend(sorted(_token_variants(token)))
    return tokens


def normalized_search_blob(text: object) -> str:
    """Return normalized text plus token variants for internal search fields."""

    normalized = normalize_arabic_for_search(text)
    variants = " ".join(dict.fromkeys(tokenize_arabic_search(normalized)))
    return "\n".join(value for value in (normalized, variants) if value).strip()
