"""Watch data/legal_documents and rebuild the legal RAG index on file drops."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

try:
    from app.config import LEGAL_DOCUMENTS_FOLDER, PROJECT_ROOT
    from app.document_loaders import supported_extensions
except ImportError:
    from config import LEGAL_DOCUMENTS_FOLDER, PROJECT_ROOT
    from document_loaders import supported_extensions


DEBOUNCE_SECONDS = 10
POLL_SECONDS = 5


def run_ingest() -> int:
    """Run the existing ingestion entry point as a subprocess."""

    command = [sys.executable, str(PROJECT_ROOT / "ingest_legal_documents.py")]
    completed = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
    return completed.returncode


def stable_file(path: Path, wait_seconds: int = 2) -> bool:
    """Return true when a dropped file has stopped changing size."""

    try:
        first_size = path.stat().st_size
        time.sleep(wait_seconds)
        second_size = path.stat().st_size
    except FileNotFoundError:
        return False
    return first_size == second_size and second_size > 0


def should_watch(path: Path) -> bool:
    """Return whether this path is a supported legal source document."""

    return (
        path.is_file()
        and path.suffix.lower() in supported_extensions()
        and not path.name.startswith("~$")
    )


def snapshot(folder: Path) -> dict[Path, float]:
    """Return supported files and their last modification times."""

    folder.mkdir(parents=True, exist_ok=True)
    return {
        path: path.stat().st_mtime
        for path in folder.iterdir()
        if should_watch(path)
    }


def poll(folder: Path, once: bool = False) -> None:
    """Portable polling watcher for Windows Task Scheduler or terminals."""

    known = snapshot(folder)
    print(f"Watching {folder} for {', '.join(supported_extensions())} files.")

    while True:
        time.sleep(POLL_SECONDS)
        current = snapshot(folder)
        changed = [
            path
            for path, modified_at in current.items()
            if path not in known or known[path] != modified_at
        ]
        known = current

        ready = [path for path in changed if stable_file(path)]
        if ready:
            print("Detected legal document changes:")
            for path in ready:
                print(f"- {path.name}")
            time.sleep(DEBOUNCE_SECONDS)
            exit_code = run_ingest()
            print(f"Ingestion finished with exit code {exit_code}.")
            if once:
                return

        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch legal document drops and rebuild the RAG index.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit. Useful for Windows Task Scheduler.",
    )
    args = parser.parse_args()
    poll(LEGAL_DOCUMENTS_FOLDER, once=args.once)


if __name__ == "__main__":
    main()
