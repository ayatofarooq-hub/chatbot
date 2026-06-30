"""Create or reset the initial administrator account."""

from getpass import getpass
from pathlib import Path
import sys

# Direct script execution places ``scripts`` rather than the repository root
# on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import create_admin


def main() -> None:
    username = input("Administrator username: ").strip()
    if not username:
        raise SystemExit("Administrator username cannot be empty.")

    while True:
        password = getpass("Administrator password: ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match. Try again.")
            continue
        try:
            create_admin(username, password)
        except ValueError as exc:
            print(f"{exc} Try again.")
            continue
        break

    print(f"Administrator '{username}' is ready.")


if __name__ == "__main__":
    main()
