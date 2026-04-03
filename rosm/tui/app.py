"""Main Textual TUI application for rosm."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
)

from rosm.models import (
    ConflictSeverity,
    NodeHealth,
    ProcessStatus,
    SystemSnapshot,
)
from rosm.tui.theme import (
    COLOR_ACCENT,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUBTEXT,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_WARNING,
    INDICATOR_ERROR,
    INDICATOR_INFO,
    INDICATOR_WARNING,
    ROSM_CSS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEALTH_ICON: dict[NodeHealth, str] = {
    NodeHealth.HEALTHY: "[+]",
    NodeHealth.STALE: "[!]",
    NodeHealth.ZOMBIE: "[x]",
    NodeHealth.UNKNOWN: "[?]",
}

_STATUS_COLOR: dict[ProcessStatus, str] = {
    ProcessStatus.RUNNING: COLOR_SUCCESS,
    ProcessStatus.SLEEPING: COLOR_TEXT,
    ProcessStatus.ZOMBIE: COLOR_ERROR,
    ProcessStatus.DEAD: COLOR_ERROR,
    ProcessStatus.ORPHAN: COLOR_WARNING,
}

_SEVERITY_ICON: dict[ConflictSeverity, str] = {
    ConflictSeverity.ERROR: INDICATOR_ERROR,
    ConflictSeverity.WARNING: INDICATOR_WARNING,
    ConflictSeverity.INFO: INDICATOR_INFO,
}

_SEVERITY_COLOR: dict[ConflictSeverity, str] = {
    ConflictSeverity.ERROR: COLOR_ERROR,
    ConflictSeverity.WARNING: COLOR_WARNING,
    ConflictSeverity.INFO: COLOR_INFO,
}


def _build_subtitle(snapshot: SystemSnapshot) -> str:
    domain = f"Domain:{snapshot.domain_id}" if snapshot.domain_id is not None else "Domain:unset"
    nodes = f"Nodes:{len(snapshot.nodes)}"
    topics = f"Topics:{len(snapshot.topics)}"
    try:
        import psutil  # type: ignore[import-untyped]

        cpu = f"CPU:{psutil.cpu_percent(interval=None):.0f}%"
        mem_gb = psutil.virtual_memory().used / (1024**3)
        mem = f"MEM:{mem_gb:.1f}GB"
    except Exception:
        cpu = "CPU:??"
        mem = "MEM:??"
    return f"  {domain}  {nodes}  {topics}  {cpu}  {mem}"


def _load_snapshot_best_effort() -> SystemSnapshot:
    """Build a SystemSnapshot from available probes."""
    processes = []
    domain_id = None
    rmw = ""
    distro = ""
    shm_files = []
    port_bindings = []

    try:
        from rosm.probes.process_probe import ProcessProbe
        processes = ProcessProbe().snapshot()
    except Exception:
        pass

    try:
        from rosm.probes.system_probe import SystemProbe
        sp = SystemProbe()
        domain_id = sp.get_domain_id()
        rmw = sp.get_rmw_implementation()
        distro = sp.get_ros_distro()
        shm_files = sp.get_shm_files()
        port_bindings = sp.get_port_bindings()
    except Exception:
        domain_id = int(os.environ.get("ROS_DOMAIN_ID", "0")) if "ROS_DOMAIN_ID" in os.environ else None
        rmw = os.environ.get("RMW_IMPLEMENTATION", "")
        distro = os.environ.get("ROS_DISTRO", "")

    snap = SystemSnapshot(
        processes=processes,
        domain_id=domain_id,
        rmw_implementation=rmw,
        ros_distro=distro,
        shm_files=shm_files,
        port_bindings=port_bindings,
    )

    # Run conflict engine
    try:
        from rosm.engine.conflict_engine import ConflictEngine
        conflicts = ConflictEngine().evaluate(snap)
        snap = snap.model_copy(update={"conflicts": conflicts})
    except Exception:
        pass

    return snap


# ---------------------------------------------------------------------------
# Tab-level widgets (each composes its own content)
# ---------------------------------------------------------------------------


class NodesTab(Vertical):
    """Nodes tab content — DataTable of ROS2 nodes."""

    def __init__(self, snapshot: SystemSnapshot, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        table = DataTable(id="nodes-table", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#nodes-table", DataTable)
        table.add_columns("Health", "Node", "Namespace", "PID", "Pubs", "Subs", "Services")
        for node in self._snapshot.nodes:
            icon = _HEALTH_ICON.get(node.health, "[?]")
            pid_str = str(node.pid) if node.pid else "-"
            table.add_row(
                icon,
                node.name,
                node.namespace,
                pid_str,
                str(len(node.published_topics)),
                str(len(node.subscribed_topics)),
                str(len(node.services)),
            )


class TopicsTab(Vertical):
    """Topics tab content — DataTable of ROS2 topics."""

    def __init__(self, snapshot: SystemSnapshot, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        table = DataTable(id="topics-table", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#topics-table", DataTable)
        table.add_columns("Topic", "Type", "Pubs", "Subs", "Hz")
        for topic in self._snapshot.topics:
            hz_str = f"{topic.hz:.1f}" if topic.hz is not None else "-"
            pub_color = COLOR_WARNING if topic.pub_count > 1 else COLOR_TEXT
            table.add_row(
                topic.name,
                topic.msg_type,
                f"[{pub_color}]{topic.pub_count}[/]",
                str(topic.sub_count),
                hz_str,
            )


class ProcessesTab(Vertical):
    """Processes tab content — DataTable of OS processes."""

    def __init__(self, snapshot: SystemSnapshot, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        table = DataTable(id="procs-table", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#procs-table", DataTable)
        table.add_columns("PID", "Name", "Node", "CPU%", "MEM(MB)", "Status", "Uptime")
        for proc in self._snapshot.processes:
            color = _STATUS_COLOR.get(proc.status, COLOR_TEXT)
            node = proc.ros2_node_name or "-"
            uptime = "-"
            if proc.create_time:
                delta = datetime.now() - proc.create_time
                h, rem = divmod(int(delta.total_seconds()), 3600)
                m, s = divmod(rem, 60)
                uptime = f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"
            table.add_row(
                str(proc.pid),
                proc.name,
                node,
                f"{proc.cpu_percent:.1f}",
                f"{proc.memory_mb:.0f}",
                f"[{color}]{proc.status.value}[/]",
                uptime,
            )


class ConflictsTab(ScrollableContainer):
    """Conflicts tab content — sorted conflict list."""

    def __init__(self, snapshot: SystemSnapshot, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        if not self._snapshot.conflicts:
            yield Static(
                f"[bold {COLOR_SUCCESS}][+] No conflicts detected.[/]",
                markup=True,
            )
            return

        order = {ConflictSeverity.ERROR: 0, ConflictSeverity.WARNING: 1, ConflictSeverity.INFO: 2}
        sorted_conflicts = sorted(
            self._snapshot.conflicts, key=lambda c: order[c.severity]
        )

        for conflict in sorted_conflicts:
            color = _SEVERITY_COLOR[conflict.severity]
            icon = _SEVERITY_ICON[conflict.severity]
            entities = ", ".join(conflict.affected_entities) if conflict.affected_entities else ""
            fix = conflict.suggested_fix

            lines = [
                f"[bold {color}]{icon} {conflict.title}[/]",
                f"[{COLOR_SUBTEXT}]{conflict.description}[/]",
            ]
            if entities:
                lines.append(f"[{COLOR_SUBTEXT}]Affected: [{color}]{entities}[/][/]")
            if fix:
                lines.append(f"[{COLOR_INFO}]Fix: {fix}[/]")

            yield Static(
                "\n".join(lines),
                markup=True,
                classes=f"conflict-item conflict-{conflict.severity.value}",
            )


# ---------------------------------------------------------------------------
# Main TUI application
# ---------------------------------------------------------------------------


class RosmDashboard(App[None]):
    """rosm real-time TUI dashboard."""

    TITLE = "rosm"
    SUB_TITLE = "ROS2 Process & Node Manager"
    CSS = ROSM_CSS + """
    Header {
        dock: top;
        height: 1;
    }
    Footer {
        dock: bottom;
        height: 1;
    }
    TabbedContent {
        height: 1fr;
    }
    ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("f1", "switch_tab('overview')", "Overview", show=True),
        Binding("f2", "switch_tab('nodes')", "Nodes", show=True),
        Binding("f3", "switch_tab('topics')", "Topics", show=True),
        Binding("f4", "switch_tab('processes')", "Processes", show=True),
        Binding("f5", "switch_tab('conflicts')", "Conflicts", show=True),
        Binding("k", "kill_selected", "Kill", show=True),
        Binding("c", "clean_system", "Clean", show=True),
        Binding("r", "refresh_data", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, initial_snapshot: SystemSnapshot | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._initial_snapshot = initial_snapshot or _load_snapshot_best_effort()

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        snap = self._initial_snapshot

        yield Header(show_clock=True)
        with TabbedContent(initial="overview"):
            with TabPane("Overview [F1]", id="overview"):
                from rosm.tui.screens.overview import OverviewContent

                yield OverviewContent(snapshot=snap, id="overview-content")
            with TabPane("Nodes [F2]", id="nodes"):
                yield NodesTab(snapshot=snap, id="nodes-tab")
            with TabPane("Topics [F3]", id="topics"):
                yield TopicsTab(snapshot=snap, id="topics-tab")
            with TabPane("Processes [F4]", id="processes"):
                yield ProcessesTab(snapshot=snap, id="processes-tab")
            with TabPane("Conflicts [F5]", id="conflicts"):
                yield ConflictsTab(snapshot=snap, id="conflicts-tab")
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.sub_title = _build_subtitle(self._initial_snapshot)
        self.set_interval(2.0, self._auto_refresh)

    async def _auto_refresh(self) -> None:
        try:
            new_snap = _load_snapshot_best_effort()
            self._initial_snapshot = new_snap
            self.sub_title = _build_subtitle(new_snap)
            try:
                from rosm.tui.screens.overview import OverviewContent

                overview = self.query_one("#overview-content", OverviewContent)
                overview.refresh_snapshot(new_snap)
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_switch_tab(self, tab_id: str) -> None:
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = tab_id
        except Exception:
            pass

    def action_kill_selected(self) -> None:
        """Kill the currently selected process."""
        try:
            table = self.query_one("#procs-table", DataTable)
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row = table.get_row(row_key)
            pid_str = str(row[0])
            self._do_kill(int(pid_str))
        except Exception:
            pass

    def _do_kill(self, pid: int) -> None:
        import signal

        try:
            os.kill(pid, signal.SIGTERM)
            self.notify(f"Sent SIGTERM to PID {pid}", severity="information")
        except ProcessLookupError:
            self.notify(f"PID {pid} not found", severity="warning")
        except PermissionError:
            self.notify(f"Permission denied for PID {pid}", severity="error")

    def action_clean_system(self) -> None:
        try:
            from rosm.actions.clean import clean_system  # type: ignore[import-not-found]

            result = clean_system(dry_run=False)
            self.notify(f"Clean done: {result}", severity="information")
        except ImportError:
            self.notify("Clean action not yet available", severity="warning")
        except Exception as exc:
            self.notify(f"Clean failed: {exc}", severity="error")

    def action_refresh_data(self) -> None:
        self.call_after_refresh(self._auto_refresh)
        self.notify("Refreshing...", severity="information")


def run_dashboard(snapshot: SystemSnapshot | None = None) -> None:
    """Entry point used by CLI `rosm dashboard`."""
    app = RosmDashboard(initial_snapshot=snapshot)
    app.run()
