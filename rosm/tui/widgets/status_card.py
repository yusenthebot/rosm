"""Reusable status card widget showing a metric with breakdown rows."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from rosm.tui.theme import (
    COLOR_ACCENT,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUBTEXT,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_WARNING,
)

# Map variant names to Rich markup colors
_VARIANT_COLORS: dict[str, str] = {
    "success": COLOR_SUCCESS,
    "warning": COLOR_WARNING,
    "error": COLOR_ERROR,
    "info": COLOR_INFO,
    "accent": COLOR_ACCENT,
    "default": COLOR_TEXT,
}


class StatusCard(Widget):
    """A card displaying a metric title with labeled value rows.

    Parameters
    ----------
    title:
        Card header text (shown in accent color).
    rows:
        Sequence of (label, value, optional_color) tuples.
        color may be 'success', 'warning', 'error', 'info', or a hex string.
    variant:
        Border colour variant — 'success' | 'warning' | 'error' | 'info' | 'accent'.
    """

    DEFAULT_CSS = """
    StatusCard {
        border: round #45475a;
        background: #181825;
        padding: 0 1;
        height: auto;
        min-height: 5;
        min-width: 22;
        width: 1fr;
        margin-right: 1;
    }
    """

    rows: reactive[list[tuple[str, str, str]]] = reactive([], recompose=True)

    def __init__(
        self,
        title: str,
        rows: list[tuple[str, str, str]] | None = None,
        variant: str = "accent",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._variant = variant
        self.rows = rows or []

    def on_mount(self) -> None:
        border_color = _VARIANT_COLORS.get(self._variant, COLOR_ACCENT)
        self.styles.border = ("round", border_color)

    def compose(self) -> ComposeResult:
        title_markup = f"[bold {COLOR_ACCENT}]{self._title}[/]"
        yield Static(title_markup, classes="card-title")
        for label, value, color in self.rows:
            resolved = _VARIANT_COLORS.get(color, color) if color else COLOR_TEXT
            row_markup = (
                f"[{COLOR_SUBTEXT}]{label:<12}[/]"
                f"[bold {resolved}]{value:>6}[/]"
            )
            yield Static(row_markup, classes="card-metric")

    def update_rows(self, rows: list[tuple[str, str, str]]) -> None:
        """Update card data; triggers recompose."""
        self.rows = rows
