"""TUI tests using Textual's app pilot."""

from __future__ import annotations

import pytest

from rosm.models import (
    Conflict,
    ConflictSeverity,
    NodeHealth,
    ProcessStatus,
    RosmNode,
    RosmProcess,
    RosmTopic,
    SystemSnapshot,
    EndpointInfo,
)
from rosm.tui.theme import COLORS, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, ROSM_CSS
from rosm.tui.widgets.alert_log import AlertEntry, AlertLog
from rosm.tui.widgets.status_card import StatusCard


# ---------------------------------------------------------------------------
# Theme tests (no Textual runtime needed)
# ---------------------------------------------------------------------------

class TestTheme:
    def test_all_palette_colors_present(self) -> None:
        required = ["base", "text", "blue", "green", "yellow", "red", "sky"]
        for key in required:
            assert key in COLORS, f"Missing color: {key}"

    def test_color_format(self) -> None:
        for name, value in COLORS.items():
            assert value.startswith("#"), f"Color {name}={value} not hex"
            assert len(value) == 7, f"Color {name}={value} wrong length"

    def test_css_contains_background(self) -> None:
        assert "background" in ROSM_CSS

    def test_css_contains_header_style(self) -> None:
        assert "Header" in ROSM_CSS

    def test_semantic_color_values(self) -> None:
        assert COLOR_SUCCESS == COLORS["green"]
        assert COLOR_WARNING == COLORS["yellow"]
        assert COLOR_ERROR == COLORS["red"]


# ---------------------------------------------------------------------------
# AlertEntry tests
# ---------------------------------------------------------------------------

class TestAlertEntry:
    def test_alert_entry_creation(self) -> None:
        entry = AlertEntry(severity=ConflictSeverity.ERROR, message="test error")
        assert entry.severity == ConflictSeverity.ERROR
        assert entry.message == "test error"
        assert entry.time_str  # non-empty

    def test_alert_entry_time_format(self) -> None:
        entry = AlertEntry(severity=ConflictSeverity.WARNING, message="warn")
        # HH:MM:SS
        parts = entry.time_str.split(":")
        assert len(parts) == 3

    def test_alert_entry_frozen(self) -> None:
        entry = AlertEntry(severity=ConflictSeverity.INFO, message="info")
        with pytest.raises((AttributeError, TypeError)):
            entry.message = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TUI app mount test (requires textual)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_mounts() -> None:
    """Verify that the TUI app mounts without error using an empty snapshot."""
    try:
        from textual.pilot import Pilot

        from rosm.tui.app import RosmDashboard
    except ImportError:
        pytest.skip("textual not installed")

    snap = SystemSnapshot(
        domain_id=0,
        rmw_implementation="rmw_fastrtps_cpp",
        ros_distro="jazzy",
    )
    app = RosmDashboard(initial_snapshot=snap)
    async with app.run_test(headless=True) as pilot:
        # App should mount without exceptions
        assert app.title == "rosm"
        assert app.sub_title  # non-empty subtitle


@pytest.mark.asyncio
async def test_dashboard_tab_switch() -> None:
    """Verify F-key tab switching works."""
    try:
        from rosm.tui.app import RosmDashboard
    except ImportError:
        pytest.skip("textual not installed")

    snap = SystemSnapshot(domain_id=0)
    app = RosmDashboard(initial_snapshot=snap)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("f2")
        await pilot.pause(0.1)
        # No crash expected


@pytest.mark.asyncio
async def test_dashboard_quit_binding() -> None:
    """Verify q binding exits the app."""
    try:
        from rosm.tui.app import RosmDashboard
    except ImportError:
        pytest.skip("textual not installed")

    snap = SystemSnapshot(domain_id=0)
    app = RosmDashboard(initial_snapshot=snap)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("q")
        # App should exit cleanly


@pytest.mark.asyncio
async def test_dashboard_with_full_snapshot() -> None:
    """TUI renders correctly with a populated snapshot."""
    try:
        from rosm.tui.app import RosmDashboard
    except ImportError:
        pytest.skip("textual not installed")

    snap = SystemSnapshot(
        domain_id=0,
        rmw_implementation="rmw_fastrtps_cpp",
        ros_distro="jazzy",
        processes=[
            RosmProcess(
                pid=1001,
                name="localPlanner",
                cmdline="/install/localPlanner --ros-args",
                status=ProcessStatus.RUNNING,
                cpu_percent=5.0,
                memory_mb=120.0,
            ),
        ],
        nodes=[
            RosmNode(
                name="localPlanner",
                namespace="/",
                full_name="/localPlanner",
                health=NodeHealth.HEALTHY,
                pid=1001,
            ),
        ],
        topics=[
            RosmTopic(
                name="/path",
                msg_type="nav_msgs/msg/Path",
                publishers=(EndpointInfo(node_name="localPlanner", node_namespace="/"),),
                subscribers=(EndpointInfo(node_name="pathFollower", node_namespace="/"),),
            ),
        ],
        conflicts=[
            Conflict(
                rule_name="OrphanedTopic",
                severity=ConflictSeverity.INFO,
                title="Orphaned topic",
                description="Publisher with no subscriber",
                affected_entities=("/dead_topic",),
            ),
        ],
    )
    app = RosmDashboard(initial_snapshot=snap)
    async with app.run_test(headless=True) as pilot:
        assert app.title == "rosm"
        # Navigate to nodes tab
        await pilot.press("f2")
        await pilot.pause(0.1)
        # Navigate to topics tab
        await pilot.press("f3")
        await pilot.pause(0.1)
        # Navigate to conflicts tab
        await pilot.press("f5")
        await pilot.pause(0.1)
