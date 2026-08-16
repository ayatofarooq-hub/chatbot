from app import user_management
from app import auth


def test_create_user_persists_ministry(monkeypatch):
    storage = {"admin_users": []}

    monkeypatch.setattr(user_management, "_read_list", lambda section: [dict(item) for item in storage.get(section, [])])
    monkeypatch.setattr(user_management, "_write_list", lambda section, payload: storage.__setitem__(section, payload))

    user = user_management.create_user(
        {
            "username": "oil-minister",
            "password": "Password123",
            "display_name": "معالي الوزير",
            "ministry": "وزارة النفط",
            "role": "viewer",
        }
    )

    assert user["ministry"] == "وزارة النفط"
    assert storage["admin_users"][0]["ministry"] == "وزارة النفط"


def test_update_user_persists_ministry(monkeypatch):
    storage = {
        "admin_users": [
            {
                "id": 1,
                "username": "minister",
                "display_name": "معالي الوزير",
                "email": "",
                "role": "viewer",
                "is_active": True,
                "ministry": None,
            }
        ]
    }

    monkeypatch.setattr(user_management, "_read_list", lambda section: [dict(item) for item in storage.get(section, [])])
    monkeypatch.setattr(user_management, "_write_list", lambda section, payload: storage.__setitem__(section, payload))

    user = user_management.update_user(1, {"ministry": "وزارة المالية"})

    assert user["ministry"] == "وزارة المالية"
    assert storage["admin_users"][0]["ministry"] == "وزارة المالية"


def test_admin_for_token_returns_ministry(monkeypatch):
    token = "session-token"
    token_hash = auth.hashlib.sha256(token.encode()).hexdigest()
    rows = {
        "admin_sessions": [
            {
                "admin_user_id": 1,
                "token_hash": token_hash,
                "expires_at": None,
            }
        ],
        "admin_users": [
            {
                "id": 1,
                "username": "ayat",
                "display_name": "ayat",
                "email": "",
                "role": "super_admin",
                "is_active": True,
                "ministry": "وزارة النفط",
            }
        ],
    }

    monkeypatch.setattr(auth, "_read_list", lambda section: [dict(item) for item in rows.get(section, [])])

    admin = auth.admin_for_token(token)

    assert admin["ministry"] == "وزارة النفط"


def test_next_welcome_phrase_cycles_session_phrases(monkeypatch):
    token = "session-token"
    token_hash = auth.hashlib.sha256(token.encode()).hexdigest()
    rows = {
        "admin_sessions": [
            {
                "admin_user_id": 1,
                "token_hash": token_hash,
                "expires_at": None,
            }
        ],
        "admin_users": [
            {
                "id": 1,
                "username": "ayat",
                "display_name": "ayat",
                "email": "",
                "role": "super_admin",
                "is_active": True,
                "ministry": "وزارة النفط",
            }
        ],
    }

    monkeypatch.setattr(auth, "_read_list", lambda section: [dict(item) for item in rows.get(section, [])])
    monkeypatch.setattr(auth, "_write_list", lambda section, payload: rows.__setitem__(section, payload))

    first = auth.next_welcome_phrase_for_token(token)
    second = auth.next_welcome_phrase_for_token(token)

    assert first["ministry"] == "وزارة النفط"
    assert first["phrase"] != second["phrase"]
    assert rows["admin_sessions"][0]["welcome_phrase_index"] == 1
