"""Rename existing ministry logins using documented institutional identifiers."""

from collections import Counter
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.json_storage import update_json


# See docs/ministry-usernames.md for the naming choices and public sources.
USERNAME_RENAMES = {
    "minister.oil": "MOO",
    "minister.electricity": "MOELC",
    "minister.agriculture": "MOA",
    "minister.industry": "MIM",
    "minister.education": "MOEDU",
    "minister.water": "MOWR",
    "minister.transport": "MOTRANS",
    "minister.foreign": "MOFA",
    "minister.finance": "MOF",
    "minister.communications": "MOC",
    "minister.health": "MOH",
    "minister.environment": "MOEN",
    "minister.justice": "MOJ",
    "minister.trade": "MOT",
    "acting.construction": "MOCH",
    "acting.planning": "MOP",
    "acting.interior": "MOI",
    "acting.higher.education": "MOHESR",
    "acting.youth": "MOYS",
    "acting.defense": "MOD",
    "acting.labor": "MOLSA",
    "acting.culture": "MOCUL",
    "acting.migration": "MOMD",
}


def rename_ministry_usernames(metadata: dict) -> dict:
    """Validate all names before changing any account; safe to run again."""
    users = metadata.get("admin_users", [])
    proposed = [USERNAME_RENAMES.get(user["username"], user["username"]) for user in users]
    duplicates = [name for name, count in Counter(name.casefold() for name in proposed).items() if count > 1]
    if duplicates:
        raise ValueError("Username collision: " + ", ".join(sorted(duplicates)))
    for user, username in zip(users, proposed):
        user["username"] = username
    return metadata


def main() -> None:
    path = PROJECT_ROOT / "data" / "metadata.json"
    if not path.is_file():
        raise SystemExit("No existing data/metadata.json found.")
    update_json(path, {}, rename_ministry_usernames)
    print("Ministry usernames updated. See docs/ministry-usernames.md for the login names.")


if __name__ == "__main__":
    main()
