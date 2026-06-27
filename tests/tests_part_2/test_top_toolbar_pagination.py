"""Regression tests for the page-jump box on the calendar toolbar.

Two bugs are guarded here:

1. While the engine kept generating, `_load_snapshot_schedules` polled every
   500ms and each poll rewrote the page box, wiping whatever jump target the
   user was typing — a specific jump could never be entered, only prev/next.

2. The first fix keyed off widget focus, which froze the counter during plain
   prev/next browsing (the arrow buttons don't steal focus from the box). The
   guard must therefore track real *keystrokes*, not focus: browsing with no
   typing keeps the counter in sync, while typing a jump target is preserved.

The logic is exercised directly with a stubbed widget so the tests run without
a display.
"""

from unittest.mock import MagicMock

from src.MVP.views.components.top_toolbar import TopToolbar


def _make_toolbar_stub(box_text: str = "1") -> TopToolbar:
    tb = object.__new__(TopToolbar)
    tb._box_text = box_text

    entry = MagicMock()
    entry.get.side_effect = lambda: tb._box_text

    def _insert(_index, value):
        tb._box_text = str(value)
    entry.insert.side_effect = _insert
    entry.delete.side_effect = lambda *a, **k: None

    tb.page_entry = entry
    tb.out_of_lbl = MagicMock()
    tb._page_entry_dirty = False
    tb._page_current = 1
    tb._page_total = 1
    return tb


def _type(tb: TopToolbar, text: str) -> None:
    """Simulate the user typing `text` into the box (a real edit keystroke)."""
    tb._box_text = text
    tb._on_page_entry_key(type("E", (), {"keysym": "5"})())


def test_set_pagination_writes_box_when_not_typing():
    tb = _make_toolbar_stub()

    tb.set_pagination(3, 10)

    assert tb._box_text == "3"
    tb.out_of_lbl.configure.assert_called_once_with(text=" / 10")


def test_browsing_keeps_counter_in_sync_without_typing():
    # No keystrokes at all — pure prev/next browsing must move the counter.
    tb = _make_toolbar_stub()

    tb.set_pagination(2, 76032)
    assert tb._box_text == "2"
    tb.set_pagination(3, 76032)
    assert tb._box_text == "3"


def test_typed_jump_target_survives_background_refresh():
    tb = _make_toolbar_stub()
    _type(tb, "5000")  # user is composing a jump while the engine generates

    tb.set_pagination(3, 76040)  # background poll fires

    assert tb._box_text == "5000"  # input preserved
    tb.out_of_lbl.configure.assert_called_with(text=" / 76040")  # label still updates


def test_submitting_jump_clears_guard_and_resyncs():
    tb = _make_toolbar_stub()
    on_jump = MagicMock()
    tb.on_page_jump = on_jump
    _type(tb, "5000")

    tb._on_page_entry_return()

    on_jump.assert_called_once_with(5000)
    assert tb._page_entry_dirty is False
    # After the jump the counter tracks the displayed page again.
    tb.set_pagination(5001, 76040)
    assert tb._box_text == "5001"


def test_focus_out_discards_half_typed_value():
    tb = _make_toolbar_stub()
    tb.set_pagination(7, 100)
    _type(tb, "999")

    tb._on_page_entry_focus_out()

    assert tb._page_entry_dirty is False
    assert tb._box_text == "7"


def test_return_with_invalid_input_restores_current_page():
    tb = _make_toolbar_stub()
    tb.on_page_jump = MagicMock()
    tb.set_pagination(4, 50)
    _type(tb, "")  # cleared the box, then hit Return

    tb._on_page_entry_return()

    tb.on_page_jump.assert_not_called()
    assert tb._box_text == "4"
