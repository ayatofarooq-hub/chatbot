from app.ministry_phrases import ministry_for_admin, welcome_phrase_for_admin


def test_welcome_phrase_matches_arabic_ministry_display_name():
    admin = {"display_name": "وزارة المالية", "username": "minister"}

    welcome = welcome_phrase_for_admin(admin)

    assert welcome is not None
    assert welcome["ministry"] == "وزارة المالية"
    assert welcome["phrase"] in ministry_for_admin(admin).phrases


def test_welcome_phrase_prefers_explicit_ministry_field():
    admin = {"display_name": "معالي الوزير", "username": "minister", "ministry": "وزارة النفط"}

    welcome = welcome_phrase_for_admin(admin)

    assert welcome is not None
    assert welcome["ministry"] == "وزارة النفط"


def test_welcome_phrase_matches_english_username_alias():
    admin = {"display_name": "Minister", "username": "defense_minister"}

    welcome = welcome_phrase_for_admin(admin)

    assert welcome is not None
    assert welcome["ministry"] == "وزارة الدفاع"


def test_welcome_phrase_is_empty_for_unknown_account():
    assert welcome_phrase_for_admin({"display_name": "Legal reviewer", "username": "reviewer"}) is None
