"""Overview tab content for the rosm dashboard."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical

from rosm.models import ConflictSeverity, NodeHealth, ProcessStatus, SystemSnapshot
from rosm.tui.widgets.alert_log import AlertLog
from rosm.tui.widgets.status_card import StatusCard


def _node_rows(snapshot: SystemSnapshot) -> list[tuple[str, str, str]]:
    total = len(snapshot.nodes)
    healthy = sum(1 for n in snapshot.nodes if n.health == NodeHealth.HEALTHY)
    stale = sum(1 for n in snapshot.nodes if n.health == NodeHealth.STALE)
    zombie = sum(1 for n in snapshot.nodes if n.health == NodeHealth.ZOMBIE)
    variant = "success" if stale == 0 and zombie == 0 else ("error" if zombie else "warning")
    rows = [
        ("total", str(total), "accent"),
        ("healthy", str(healthy), "success"),
        ("stale", str(stale), "warning" if stale else "success"),
        ("zombie", str(zombie), "error" if zombie else "success"),
    ]
    return rows, variant  # type: ignore[return-value]


def _topic_rows(snapshot: SystemSnapshot) -> list[tuple[str, str, str]]:
    total = len(snapshot.topics)
    active = sum(1 for t in snapshot.topics if t.pub_count > 0 and t.sub_count > 0)
    orphaned = total - active
    rows = [
        ("total", str(total), "accent"),
        ("active", str(active), "success"),
        ("orphaned", str(orphaned), "warning" if orphaned else "success"),
    ]
    return rows, "warning" if orphaned else "success"  # type: ignore[return-value]


def _process_rows(snapshot: SystemSnapshot) -> list[tuple[str, str, str]]:
    total = len(snapshot.processes)
    zombies = sum(1 for p in snapshot.processes if p.status == ProcessStatus.ZOMBIE)
    orphans = sum(1 for p in snapshot.processes if p.status == ProcessStatus.ORPHAN)
    variant = "error" if zombies else ("warning" if orphans else "success")
    rows = [
        ("total", str(total), "accent"),
        ("running", str(sum(1 for p in snapshot.processes if p.status == ProcessStatus.RUNNING)), "success"),
        ("zombies", str(zombies), "error" if zombies else "success"),
        ("orphans", str(orphans), "warning" if orphans else "success"),
    ]
    return rows, variant  # type: ignore[return-value]


def _conflict_rows(snapshot: SystemSnapshot) -> list[tuple[str, str, str]]:
    errors = sum(1 for c in snapshot.conflicts if c.severity == ConflictSeverity.ERROR)
    warnings = sum(1 for c in snapshot.conflicts if c.severity == ConflictSeverity.WARNING)
    infos = sum(1 for c in snapshot.conflicts if c.severity == ConflictSeverity.INFO)
    variant = "error" if errors else ("warning" if warnings else "success")
    rows = [
        ("errors", str(errors), "error" if errors else "success"),
        ("warnings", str(warnings), "warning" if warnings else "success"),
        ("info", str(infos), "info"),
    ]
    return rows, variant  # type: ignore[return-value]


def _system_rows(snapshot: SystemSnapshot) -> list[tuple[str, str, str]]:
    import psutil  # type: ignore[import-untyped]

    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    mem_gb = mem.used / (1024**3)
    shm_mb = sum(s.size_bytes for s in snapshot.shm_files) / (1024**2)
    rows = [
        ("CPU", f"{cpu:.0f}%", "success" if cpu < 70 else "warning"),
        ("MEM", f"{mem_gb:.1f}GB", "success" if mem.percent < 80 else "warning"),
        ("SHM", f"{shm_mb:.0f}MB", "warning" if shm_mb > 100 else "success"),
    ]
    return rows, "success"  # type: ignore[return-value]


def _domain_rows(snapshot: SystemSnapshot) -> list[tuple[str, str, str]]:
    domain = str(snapshot.domain_id) if snapshot.domain_id is not None else "unset"
    rmw = snapshot.rmw_implementation.replace("rmw_", "").replace("_cpp", "") or "unknown"
    distro = snapshot.ros_distro or "unknown"
    variant = "warning" if snapshot.domain_id is None else "info"
    rows = [
        ("domain ID", domain, "warning" if snapshot.domain_id is None else "info"),
        ("RMW", rmw, "info"),
        ("distro", distro, "info"),
    ]
    return rows, variant  # type: ignore[return-value]


class OverviewContent(Vertical):
    """Complete overview tab — status cards + alert log."""

    DEFAULT_CSS = """
    OverviewContent {
        padding: 1 2;
        height: 100%;
        width: 100%;
    }
    OverviewContent > Horizontal {
        height: auto;
        min-height: 7;
        width: 100%;
        margin-bottom: 1;
    }
    OverviewContent > Horizontal > StatusCard {
        width: 1fr;
    }
    OverviewContent > AlertLog {
        height: auto;
        min-height: 5;
    }
    """

    def __init__(self, snapshot: SystemSnapshot | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot or SystemSnapshot()

    def compose(self) -> ComposeResult:
        snap = self._snapshot

        node_rows, node_variant = _node_rows(snap)  # type: ignore[misc]
        topic_rows, topic_variant = _topic_rows(snap)  # type: ignore[misc]
        sys_rows, sys_variant = _system_rows(snap)  # type: ignore[misc]
        proc_rows, proc_variant = _process_rows(snap)  # type: ignore[misc]
        conflict_rows, conflict_variant = _conflict_rows(snap)  # type: ignore[misc]
        domain_rows, domain_variant = _domain_rows(snap)  # type: ignore[misc]

        with Horizontal(classes="cards-row"):
            yield StatusCard(
                "Nodes",
                rows=node_rows,
                variant=node_variant,
                id="card-nodes",
            )
            yield StatusCard(
                "Topics",
                rows=topic_rows,
                variant=topic_variant,
                id="card-topics",
            )
            yield StatusCard(
                "System",
                rows=sys_rows,
                variant=sys_variant,
                id="card-system",
            )

        with Horizontal(classes="cards-row"):
            yield StatusCard(
                "Processes",
                rows=proc_rows,
                variant=proc_variant,
                id="card-processes",
            )
            yield StatusCard(
                "Conflicts",
                rows=conflict_rows,
                variant=conflict_variant,
                id="card-conflicts",
            )
            yield StatusCard(
                "Domain",
                rows=domain_rows,
                variant=domain_variant,
                id="card-domain",
            )

        alert_log = AlertLog(id="alert-log")
        alert_log.load_conflicts(snap.conflicts)
        yield alert_log

    def refresh_snapshot(self, snapshot: SystemSnapshot) -> None:
        """Update the displayed snapshot data."""
        self._snapshot = snapshot
        self.refresh(recompose=True)
