"""Filesystem helpers scoped to parser_app."""

from collections.abc import Iterable
from pathlib import Path


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def iter_input_files(input_dir: Path, supported_extensions: Iterable[str]) -> list[Path]:
    extensions = {extension.lower() for extension in supported_extensions}
    if not input_dir.exists():
        return []

    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    )
