"""Scrolling alert feed widget."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.widget import Widget
from textual.widgets import Static

from rosm.models import ConflictSeverity
from rosm.tui.theme import (
    COLOR_ACCENT,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUBTEXT,
    COLOR_WARNING,
    INDICATOR_ERROR,
    INDICATOR_INFO,
    INDICATOR_WARNING,
)

_SEVERITY_COLOR: dict[ConflictSeverity, str] = {
    ConflictSeverity.ERROR: COLOR_ERROR,
    ConflictSeverity.WARNING: COLOR_WARNING,
    ConflictSeverity.INFO: COLOR_INFO,
}

_SEVERITY_ICON: dict[ConflictSeverity, str] = {
    ConflictSeverity.ERROR: INDICATOR_ERROR,
    ConflictSeverity.WARNING: INDICATOR_WARNING,
    ConflictSeverity.INFO: INDICATOR_INFO,
}


@dataclass(frozen=True)
class AlertEntry:
    """A single alert entry shown in the feed."""

    severity: ConflictSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def time_str(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")


class AlertLog(Widget):
    """A scrollable, chronological alert feed.

    New alerts are prepended (most recent at top).
    """

    DEFAULT_CSS = """
    AlertLog {
        border: round #45475a;
        background: #181825;
        height: auto;
        min-height: 5;
        max-height: 14;
        padding: 0 1;
        overflow-y: auto;
        width: 1fr;
    }
    """

    alerts: reactive[list[AlertEntry]] = reactive([], recompose=True)

    def __init__(
        self,
        max_entries: int = 50,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._max_entries = max_entries
        self.alerts = []

    def compose(self) -> ComposeResult:
        title = f"[bold {COLOR_ACCENT}]Recent Alerts[/]"
        yield Static(title, classes="alert-log-title")
        if not self.alerts:
            yield Static(
                f"[{COLOR_SUBTEXT}]No alerts[/]",
            )
            return
        for entry in self.alerts:
            color = _SEVERITY_COLOR[entry.severity]
            icon = _SEVERITY_ICON[entry.severity]
            markup = (
                f"[{COLOR_SUBTEXT}]{entry.time_str}[/] "
                f"[bold {color}]{icon}[/] "
                f"[{color}]{entry.message}[/]"
            )
            yield Static(markup)

    def push_alert(self, severity: ConflictSeverity, message: str) -> None:
        """Add a new alert to the top of the feed."""
        entry = AlertEntry(severity=severity, message=message)
        new_list = [entry, *self.alerts][: self._max_entries]
        self.alerts = new_list

    def clear(self) -> None:
        """Clear all alerts."""
        self.alerts = []

    def load_conflicts(self, conflicts: list) -> None:  # type: ignore[type-arg]
        """Populate from a list of Conflict model objects."""
        entries: list[AlertEntry] = []
        for c in conflicts:
            entries.append(
                AlertEntry(
                    severity=c.severity,
                    message=c.title,
                )
            )
        self.alerts = entries[: self._max_entries]
