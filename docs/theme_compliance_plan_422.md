# PLAN-422 — Theme compliance for Sprint 3 components

## Scope

This note covers the new Sprint 3 UI surfaces:

- Constraints settings modal (`constraints_modal.py`)
- Metrics display panel (`metrics_panel.py`)
- Sort criteria priority selector (`sort_criteria_modal.py`)
- Ranking bar updates for metrics/sort controls (`ranking_bar.py`)
- Refresh-feed button in the results toolbar (`top_toolbar.py`)
- Shared component helpers used by those surfaces (`ui_components.py`)

## Rule

New widgets must not introduce local color, font, radius, spacing, or sizing literals. Styling must be resolved through `src/MVP/views/theme.py` so the application keeps one visual language across light/dark modes and across calendar views.

## Theme tokens added

`theme.py` now includes shared tokens for:

- foreground/background colors, accent hover color, tooltip background, and accent text color;
- border widths and radius values;
- spacing scale;
- font families, icon font family, font sizes, and bold weight;
- common control sizes such as toolbar buttons, modal inputs, sort-selector rows, and modal minimum sizes;
- tooltip timing constants and the shared empty-value symbol.

## Compliance changes

The Sprint 3 components now reference theme tokens for their CTk arguments:

- `fg_color`, `hover_color`, `text_color`, `border_color`
- `font`, `dropdown_font`, icon font family
- `width`, `height`, `wraplength`
- `corner_radius`, `border_width`
- `padx`, `pady`
- modal geometry/min-size

The refresh-feed button remains visually distinct through `theme.TEXT_ACCENT` and `theme.ACCENT_HOVER`, but it no longer defines local hex constants.

## Regression check

A source-level regression test verifies that Sprint 3 component files do not contain hard-coded hex colors, direct `"white"` text colors, raw `"transparent"` values, direct font family literals, or literal style dimensions for common CTk style arguments.
