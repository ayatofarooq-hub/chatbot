"""Repair common mojibake produced by reading Arabic UTF-8 as Latin text."""

from __future__ import annotations

from typing import Any

MOJIBAKE_MARKERS = ("Ã", "Â", "Ø", "Ù", "â€", "Ë", "™", "�")


def _arabic_score(value: str) -> int:
    arabic = sum(1 for char in value if "\u0600" <= char <= "\u06ff")
    markers = sum(value.count(marker) for marker in MOJIBAKE_MARKERS)
    return arabic * 3 - markers


def _mojibake_bytes(value: str) -> bytes:
    """Rebuild original bytes from a mixed latin1/cp1252-decoded string."""

    output = bytearray()
    for char in value:
        codepoint = ord(char)
        if codepoint <= 0xFF:
            output.append(codepoint)
            continue
        output.extend(char.encode("cp1252"))
    return bytes(output)


def repair_mojibake(value: str) -> str:
    """Return readable Arabic when ``value`` contains reversible mojibake."""

    if not isinstance(value, str) or not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    best = value
    best_score = _arabic_score(value)
    current = value
    for _ in range(3):
        improved = False
        candidates = []
        try:
            candidates.append(_mojibake_bytes(current).decode("utf-8"))
        except UnicodeError:
            pass
        for encoding in ("latin1", "cp1252"):
            try:
                candidates.append(current.encode(encoding).decode("utf-8"))
            except UnicodeError:
                continue
        for candidate in candidates:
            score = _arabic_score(candidate)
            if score > best_score:
                best = candidate
                best_score = score
                current = candidate
                improved = True
                break
        if not improved:
            break
    return best


def repair_json_text(value: Any) -> Any:
    """Recursively repair text values inside JSON-compatible payloads."""

    if isinstance(value, str):
        return repair_mojibake(value)
    if isinstance(value, list):
        return [repair_json_text(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_json_text(item) for key, item in value.items()}
    return value
