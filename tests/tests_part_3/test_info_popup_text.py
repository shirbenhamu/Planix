"""Information pop-up text coverage."""

from pathlib import Path
from src.MVP.views.ui_utils import TRANSLATIONS

ROOT = Path(__file__).resolve().parents[2]

CONSTRAINT_KEYS = [
    "min_days_mandatory",
    "min_days_any",
    "max_elective_conflicts",
    "span_mandatory",
    "max_exams_per_day",
]

CALENDAR_BUTTON_KEYS = [
    "navigation",
    "sort_selector",
    "metrics",
    "refresh_feed",
    "load_more",
    "constraints",
    "edit_dates",
    "exclude",
    "undo",
    "export",
]

def test_plan_582_information_popup_translations_exist_for_both_languages():
    base_keys = [
        "info_constraints_title",
        "info_constraints_desc",
        "info_calendar_buttons_title",
        "info_calendar_buttons_desc",
    ]
    for key in base_keys:
        for lang in ("he", "en"):
            assert TRANSLATIONS[key][lang], f"missing {key}/{lang}"

    for key in CONSTRAINT_KEYS:
        for lang in ("he", "en"):
            assert TRANSLATIONS[f"info_constraint_{key}"][lang], f"missing info_constraint_{key}/{lang}"

    for key in CALENDAR_BUTTON_KEYS:
        for suffix in ("title", "desc"):
            for lang in ("he", "en"):
                text = TRANSLATIONS[f"info_button_{key}_{suffix}"][lang]
                assert text, f"missing info_button_{key}_{suffix}/{lang}"

def test_information_popup_source_renders_hebrew_with_rtl_embedding():
    source = (ROOT / "src/MVP/views/components/info_modal.py").read_text(encoding="utf-8")

    assert "PLAN-582" in source
    assert "\\u202B" in source
    assert "\\u202C" in source
    assert "info_constraints_title" in source
    assert "info_calendar_buttons_title" in source

def test_information_popup_sort_text_describes_priority_selector_not_old_secondary_dropdown():
    he = TRANSLATIONS["info_sort_desc"]["he"]
    en = TRANSLATIONS["info_sort_desc"]["en"]

    assert "עדיפות" in he
    assert "priority" in en.lower()
    assert "secondary" not in en.lower()