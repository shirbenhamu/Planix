"""theme-token compliance checks for Sprint 3 UI components."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

SPRINT3_COMPONENTS = [
    ROOT / "src/MVP/views/components/constraints_modal.py",
    ROOT / "src/MVP/views/components/metrics_panel.py",
    ROOT / "src/MVP/views/components/sort_criteria_modal.py",
    ROOT / "src/MVP/views/components/ranking_bar.py",
    ROOT / "src/MVP/views/components/top_toolbar.py",
    ROOT / "src/MVP/views/components/ui_components.py",
]

STYLE_LITERAL_PATTERNS = {
    "hex color": re.compile(r"#[0-9A-Fa-f]{6}"),
    "literal white text color": re.compile(r'text_color\s*=\s*["\']white["\']'),
    "literal transparent fg color": re.compile(r'fg_color\s*=\s*["\']transparent["\']'),
    "bootstrap font literal": re.compile(r'family\s*=\s*["\']bootstrap-icons["\']'),
    "arial font literal": re.compile(r'family\s*=\s*["\']Arial["\']'),
    "literal font size": re.compile(r'size\s*=\s*\d+'),
    "literal widget width": re.compile(r'width\s*=\s*\d+'),
    "literal widget height": re.compile(r'height\s*=\s*\d+'),
    "literal corner radius": re.compile(r'corner_radius\s*=\s*\d+'),
    "literal border width": re.compile(r'border_width\s*=\s*\d+'),
    "literal pack/grid padx": re.compile(r'padx\s*=\s*\d+'),
    "literal pack/grid pady": re.compile(r'pady\s*=\s*\d+'),
}

def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def test_sprint3_components_do_not_define_local_style_literals():
    violations = []
    for path in SPRINT3_COMPONENTS:
        source = _source(path)
        for label, pattern in STYLE_LITERAL_PATTERNS.items():
            if pattern.search(source):
                violations.append(f"{path.relative_to(ROOT)} contains {label}")

    assert violations == []

def test_theme_exposes_tokens_needed_by_sprint3_components():
    theme_source = _source(ROOT / "src/MVP/views/theme.py")
    required_tokens = [
        "TEXT_ON_ACCENT",
        "ACCENT_HOVER",
        "TOOLTIP_BG",
        "FONT_BOOTSTRAP_ICONS",
        "FONT_SIZE_MODAL_TITLE",
        "CONTROL_HEIGHT_ACTION",
        "CONTROL_WIDTH_REFRESH",
        "SORT_SELECTOR_ROW_HEIGHT",
        "CONSTRAINTS_MODAL_GEOMETRY",
        "SORT_SELECTOR_MODAL_GEOMETRY",
        "EMPTY_VALUE_TEXT",
    ]

    missing = [token for token in required_tokens if f"{token} =" not in theme_source]
    assert missing == []

def test_design_document_records_theme_compliance_update():
    design_doc = ROOT / "docs/theme_compliance_plan_422.md"
    assert design_doc.exists()
    text = design_doc.read_text(encoding="utf-8")

    assert "PLAN-422" in text
    assert "theme.py" in text
    assert "Refresh-feed" in text or "refresh-feed" in text