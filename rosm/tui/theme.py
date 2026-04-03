"""Catppuccin Mocha theme and CSS for the rosm TUI."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Catppuccin Mocha palette
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
    "surface0": "#313244",
    "surface1": "#45475a",
    "surface2": "#585b70",
    "overlay0": "#6c7086",
    "text": "#cdd6f4",
    "subtext0": "#a6adc8",
    "subtext1": "#bac2de",
    "blue": "#89b4fa",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "red": "#f38ba8",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
    "sky": "#89dceb",
    "teal": "#94e2d5",
    "lavender": "#b4befe",
    "peach": "#fab387",
    "flamingo": "#f2cdcd",
    "rosewater": "#f5e0dc",
}

# Semantic aliases
COLOR_BG = COLORS["base"]
COLOR_SURFACE = COLORS["surface0"]
COLOR_SURFACE1 = COLORS["surface1"]
COLOR_ACCENT = COLORS["blue"]
COLOR_SUCCESS = COLORS["green"]
COLOR_WARNING = COLORS["yellow"]
COLOR_ERROR = COLORS["red"]
COLOR_INFO = COLORS["sky"]
COLOR_TEXT = COLORS["text"]
COLOR_SUBTEXT = COLORS["subtext0"]
COLOR_MAUVE = COLORS["mauve"]

# ---------------------------------------------------------------------------
# Status indicator characters
# ---------------------------------------------------------------------------

INDICATOR_HEALTHY = "[+]"
INDICATOR_WARNING = "[!]"
INDICATOR_ERROR = "[x]"
INDICATOR_INFO = "[~]"
INDICATOR_UNKNOWN = "[?]"

# ---------------------------------------------------------------------------
# Textual CSS
# ---------------------------------------------------------------------------

ROSM_CSS = f"""
Screen {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
}}

Header {{
    background: {COLORS["mantle"]};
    color: {COLOR_ACCENT};
}}

Footer {{
    background: {COLORS["mantle"]};
    color: {COLOR_SUBTEXT};
}}

Tabs {{
    background: {COLORS["mantle"]};
}}

Tab {{
    background: {COLORS["mantle"]};
    color: {COLOR_SUBTEXT};
    padding: 0 2;
}}

Tab:hover {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT};
}}

Tab.-active {{
    background: {COLOR_SURFACE};
    color: {COLOR_ACCENT};
    text-style: bold;
}}

DataTable {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
    border: round {COLORS["surface1"]};
    height: 1fr;
}}

DataTable > .datatable--header {{
    background: {COLORS["mantle"]};
    color: {COLOR_ACCENT};
    text-style: bold;
}}

DataTable > .datatable--row {{
    background: {COLOR_BG};
}}

DataTable > .datatable--row-hover {{
    background: {COLOR_SURFACE};
}}

DataTable > .datatable--cursor {{
    background: {COLORS["surface1"]};
    color: {COLOR_TEXT};
}}

DataTable > .datatable--odd-row {{
    background: {COLORS["mantle"]};
}}

/* ---- Status Cards ---- */
.status-card {{
    border: round {COLORS["surface1"]};
    background: {COLORS["mantle"]};
    padding: 0 1;
    height: 7;
    min-width: 22;
}}

.status-card.success {{
    border: round {COLOR_SUCCESS};
}}

.status-card.warning {{
    border: round {COLOR_WARNING};
}}

.status-card.error {{
    border: round {COLOR_ERROR};
}}

.status-card.info {{
    border: round {COLOR_INFO};
}}

.status-card.accent {{
    border: round {COLOR_ACCENT};
}}

.card-title {{
    color: {COLOR_ACCENT};
    text-style: bold;
    margin-bottom: 1;
}}

.card-metric {{
    color: {COLOR_TEXT};
}}

/* ---- Alert Log ---- */
.alert-log {{
    border: round {COLORS["surface1"]};
    background: {COLORS["mantle"]};
    height: 10;
    padding: 0 1;
}}

.alert-log-title {{
    color: {COLOR_ACCENT};
    text-style: bold;
}}

.alert-error {{
    color: {COLOR_ERROR};
}}

.alert-warning {{
    color: {COLOR_WARNING};
}}

.alert-info {{
    color: {COLOR_INFO};
}}

/* ---- Cards container ---- */
.cards-row {{
    height: auto;
    layout: horizontal;
    padding: 0 1;
    margin-bottom: 1;
}}

.cards-row > .status-card {{
    margin-right: 1;
}}

/* ---- Overview layout ---- */
#overview-container {{
    layout: vertical;
    padding: 1;
}}

/* ---- Conflict items ---- */
.conflict-item {{
    padding: 0 1;
    margin-bottom: 1;
    border: round {COLORS["surface1"]};
    background: {COLORS["mantle"]};
}}

.conflict-error {{
    border: round {COLOR_ERROR};
    color: {COLOR_ERROR};
}}

.conflict-warning {{
    border: round {COLOR_WARNING};
    color: {COLOR_WARNING};
}}

.conflict-info {{
    border: round {COLOR_INFO};
    color: {COLOR_INFO};
}}

/* ---- Scrollable containers ---- */
ScrollableContainer {{
    background: {COLOR_BG};
    height: 1fr;
}}

/* ---- Labels ---- */
Label {{
    color: {COLOR_TEXT};
}}

Static {{
    color: {COLOR_TEXT};
}}
"""
