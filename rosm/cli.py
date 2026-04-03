"""rosm CLI — Click commands with Rich output."""

from __future__ import annotations

import os
import signal
import sys
from datetime import datetime
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from rosm._compat import has_rclpy, has_ros2_cli
from rosm.models import (
    ConflictSeverity,
    NodeHealth,
    ProcessStatus,
    SystemSnapshot,
)

console = Console()

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_STATUS_COLOR: dict[ProcessStatus, str] = {
    ProcessStatus.RUNNING: "green",
    ProcessStatus.SLEEPING: "blue",
    ProcessStatus.ZOMBIE: "red",
    ProcessStatus.DEAD: "red",
    ProcessStatus.ORPHAN: "yellow",
}

_HEALTH_COLOR: dict[NodeHealth, str] = {
    NodeHealth.HEALTHY: "green",
    NodeHealth.STALE: "yellow",
    NodeHealth.ZOMBIE: "red",
    NodeHealth.UNKNOWN: "dim",
}

_HEALTH_ICON: dict[NodeHealth, str] = {
    NodeHealth.HEALTHY: "[+]",
    NodeHealth.STALE: "[!]",
    NodeHealth.ZOMBIE: "[x]",
    NodeHealth.UNKNOWN: "[?]",
}

_SEVERITY_COLOR: dict[ConflictSeverity, str] = {
    ConflictSeverity.ERROR: "red",
    ConflictSeverity.WARNING: "yellow",
    ConflictSeverity.INFO: "cyan",
}

_SEVERITY_ICON: dict[ConflictSeverity, str] = {
    ConflictSeverity.ERROR: "[x]",
    ConflictSeverity.WARNING: "[!]",
    ConflictSeverity.INFO: "[~]",
}


def _format_uptime(create_time: datetime | None) -> str:
    if create_time is None:
        return "-"
    delta = datetime.now() - create_time
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


# ---------------------------------------------------------------------------
# Probe loading with graceful fallback
# ---------------------------------------------------------------------------

def _load_process_snapshot() -> SystemSnapshot:
    """Load process snapshot via ProcessProbe, wrapped in SystemSnapshot."""
    processes = []
    try:
        from rosm.probes.process_probe import ProcessProbe

        processes = ProcessProbe().snapshot()
    except ImportError:
        pass
    except Exception as exc:
        console.print(f"[yellow]Warning: ProcessProbe error: {exc}[/]")

    # Grab system-level info
    domain_id = None
    rmw = ""
    distro = ""
    shm_files = []
    port_bindings = []
    try:
        from rosm.probes.system_probe import SystemProbe

        sp = SystemProbe()
        domain_id = sp.get_domain_id()
        rmw = sp.get_rmw_implementation()
        distro = sp.get_ros_distro()
        shm_files = sp.get_shm_files()
        port_bindings = sp.get_port_bindings()
    except ImportError:
        domain_id = int(os.environ.get("ROS_DOMAIN_ID", "0")) if "ROS_DOMAIN_ID" in os.environ else None
        rmw = os.environ.get("RMW_IMPLEMENTATION", "")
        distro = os.environ.get("ROS_DISTRO", "")
    except Exception:
        pass

    return SystemSnapshot(
        processes=processes,
        domain_id=domain_id,
        rmw_implementation=rmw,
        ros_distro=distro,
        shm_files=shm_files,
        port_bindings=port_bindings,
    )


def _load_graph_snapshot() -> SystemSnapshot:
    """Load graph snapshot via GraphProbe, wrapped in SystemSnapshot."""
    nodes = []
    topics = []
    services = []
    try:
        from rosm.probes.graph_probe import GraphProbe

        with GraphProbe(timeout_sec=5.0).managed() as gp:
            nodes = gp.get_nodes()
            topics = gp.get_topics()
            services = gp.get_services()
    except ImportError:
        pass
    except Exception as exc:
        console.print(f"[yellow]Warning: GraphProbe error: {exc}[/]")

    return SystemSnapshot(nodes=nodes, topics=topics, services=services)


def _load_full_snapshot() -> SystemSnapshot:
    """Merge process + graph + system probes into one snapshot."""
    snap = _load_process_snapshot()

    # Merge graph data if rclpy available
    if has_rclpy():
        try:
            from rosm.probes.graph_probe import GraphProbe

            with GraphProbe(timeout_sec=5.0).managed() as gp:
                nodes = gp.get_nodes()
                topics = gp.get_topics()
                services = gp.get_services()
            snap = snap.model_copy(
                update={"nodes": nodes, "topics": topics, "services": services}
            )
        except Exception:
            pass

    return snap


def _run_conflict_engine(snapshot: SystemSnapshot) -> SystemSnapshot:
    """Run conflict detection and return snapshot with conflicts populated."""
    try:
        from rosm.engine.conflict_engine import ConflictEngine

        engine = ConflictEngine()
        conflicts = engine.evaluate(snapshot)
        return snapshot.model_copy(update={"conflicts": conflicts})
    except Exception:
        pass
    return snapshot


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="rosm")
def cli() -> None:
    """rosm -- ROS2 process, node, and topic manager."""


# ---------------------------------------------------------------------------
# rosm ps
# ---------------------------------------------------------------------------

@cli.command("ps")
@click.option("--all", "-a", "show_all", is_flag=True, help="Include non-ROS2 child processes")
def ps(show_all: bool) -> None:
    """List ROS2-related processes."""
    snapshot = _load_process_snapshot()

    table = Table(
        title="ROS2 Processes",
        show_header=True,
        header_style="bold #89b4fa",
        border_style="#45475a",
        row_styles=["", "on #181825"],
    )
    table.add_column("PID", style="dim", justify="right", width=8)
    table.add_column("Name", min_width=20)
    table.add_column("Node", min_width=20, style="cyan")
    table.add_column("CPU%", justify="right", width=7)
    table.add_column("MEM(MB)", justify="right", width=9)
    table.add_column("Status", width=10)
    table.add_column("Uptime", width=10)

    procs = snapshot.processes
    if not procs:
        console.print("[dim]No ROS2 processes found.[/]")
        return

    for proc in procs:
        color = _STATUS_COLOR.get(proc.status, "white")
        node = proc.ros2_node_name or "-"
        uptime = _format_uptime(proc.create_time)
        status_text = Text(proc.status.value, style=color)
        table.add_row(
            str(proc.pid),
            proc.name,
            node,
            f"{proc.cpu_percent:.1f}",
            f"{proc.memory_mb:.0f}",
            status_text,
            uptime,
        )

    console.print(table)
    console.print(
        f"[dim]Total: {len(procs)} process(es)[/]"
    )


# ---------------------------------------------------------------------------
# rosm kill
# ---------------------------------------------------------------------------

@cli.command("kill")
@click.argument("target")
@click.option("--force", "-f", is_flag=True, help="Use SIGKILL instead of SIGTERM")
def kill(target: str, force: bool) -> None:
    """Kill a ROS2 process by name or PID."""
    sig = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"

    # Try numeric PID first
    if target.isdigit():
        pid = int(target)
        _kill_pid(pid, sig, sig_name)
        return

    # Name-based kill: find matching processes
    snapshot = _load_process_snapshot()
    matches = [
        p for p in snapshot.processes
        if target.lower() in p.name.lower() or (p.ros2_node_name and target.lower() in p.ros2_node_name.lower())
    ]

    if not matches:
        console.print(f"[yellow]No processes matching '{target}' found.[/]")
        raise SystemExit(1)

    for proc in matches:
        _kill_pid(proc.pid, sig, sig_name)


def _kill_pid(pid: int, sig: signal.Signals, sig_name: str) -> None:
    try:
        os.kill(pid, sig)
        console.print(f"[green]Sent {sig_name} to PID {pid}[/]")
    except ProcessLookupError:
        console.print(f"[yellow]PID {pid} not found (already exited)[/]")
    except PermissionError:
        console.print(f"[red]Permission denied for PID {pid}[/]")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# rosm clean
# ---------------------------------------------------------------------------

@cli.command("clean")
@click.option("--dry-run", is_flag=True, help="Show what would be done without doing it")
def clean(dry_run: bool) -> None:
    """Kill zombies + clean SHM + reset ros2 daemon."""
    label = "[dim](dry-run)[/]" if dry_run else ""
    console.print(f"[bold #89b4fa]rosm clean {label}[/]")

    snapshot = _load_process_snapshot()

    # Kill zombie/orphan processes
    zombies = [
        p for p in snapshot.processes
        if p.status in (ProcessStatus.ZOMBIE, ProcessStatus.ORPHAN)
    ]
    if zombies:
        console.print(f"[yellow]Found {len(zombies)} zombie/orphan process(es)[/]")
        for proc in zombies:
            if dry_run:
                console.print(f"  [dim]would kill PID {proc.pid} ({proc.name})[/]")
            else:
                _kill_pid(proc.pid, signal.SIGTERM, "SIGTERM")

        # Wait briefly, then SIGKILL any survivors
        if not dry_run:
            import time
            time.sleep(1)
            for proc in zombies:
                try:
                    os.kill(proc.pid, 0)  # check if still alive
                    console.print(f"  [red]PID {proc.pid} ignored SIGTERM, sending SIGKILL[/]")
                    os.kill(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    pass
    else:
        console.print("[green][+] No zombie processes[/]")

    # Clean SHM files
    import glob as _glob

    shm_patterns = ["/dev/shm/fastrtps_*", "/dev/shm/sem.fastrtps_*"]
    shm_files: list[str] = []
    for pat in shm_patterns:
        shm_files.extend(_glob.glob(pat))

    if shm_files:
        console.print(f"[yellow]Found {len(shm_files)} orphaned SHM file(s)[/]")
        for path in shm_files:
            if dry_run:
                console.print(f"  [dim]would remove {path}[/]")
            else:
                try:
                    os.remove(path)
                    console.print(f"  [green]removed {path}[/]")
                except OSError as exc:
                    console.print(f"  [red]failed to remove {path}: {exc}[/]")
    else:
        console.print("[green][+] No orphaned SHM files[/]")

    # Reset ros2 daemon
    if has_ros2_cli():
        if dry_run:
            console.print("[dim]would run: ros2 daemon stop && ros2 daemon start[/]")
        else:
            import subprocess

            console.print("[cyan][~] Restarting ros2 daemon...[/]")
            subprocess.run(["ros2", "daemon", "stop"], capture_output=True)  # noqa: S603
            subprocess.run(["ros2", "daemon", "start"], capture_output=True)  # noqa: S603
            console.print("[green][+] ros2 daemon restarted[/]")
    else:
        console.print("[dim]ros2 CLI not available — skipping daemon reset[/]")

    if not dry_run:
        console.print("[bold green]Clean complete.[/]")


# ---------------------------------------------------------------------------
# rosm nuke
# ---------------------------------------------------------------------------

@cli.command("nuke")
@click.confirmation_option(prompt="Kill ALL ROS2 processes and clean everything?")
def nuke() -> None:
    """Nuclear option: kill everything ROS2."""
    console.print("[bold red]NUKE INITIATED[/]")

    snapshot = _load_process_snapshot()
    procs = [p for p in snapshot.processes]

    if not procs:
        console.print("[dim]No ROS2 processes found.[/]")
    else:
        console.print(f"[red]Killing {len(procs)} process(es)...[/]")
        for proc in procs:
            try:
                os.kill(proc.pid, signal.SIGKILL)
                console.print(f"  [red]killed PID {proc.pid} ({proc.name})[/]")
            except (ProcessLookupError, PermissionError):
                pass

    # Clean SHM
    import glob as _glob

    for pat in ["/dev/shm/fastrtps_*", "/dev/shm/sem.fastrtps_*"]:
        for path in _glob.glob(pat):
            try:
                os.remove(path)
            except OSError:
                pass

    # Daemon reset
    if has_ros2_cli():
        import subprocess

        subprocess.run(["ros2", "daemon", "stop"], capture_output=True)  # noqa: S603

    console.print("[bold red]NUKE COMPLETE.[/]")


# ---------------------------------------------------------------------------
# rosm nodes
# ---------------------------------------------------------------------------

@cli.command("nodes")
def nodes() -> None:
    """List ROS2 nodes with health status."""
    if not has_rclpy():
        console.print(
            Panel(
                "[yellow]rclpy not available.[/]\n"
                "Source your ROS2 installation:\n"
                "  [bold]source /opt/ros/jazzy/setup.bash[/]",
                title="[red]ROS2 Unavailable[/]",
                border_style="red",
            )
        )
        raise SystemExit(1)

    with Live(Spinner("dots", text="Discovering nodes..."), console=console, transient=True):
        snapshot = _load_graph_snapshot()

    table = Table(
        title="ROS2 Nodes",
        header_style="bold #89b4fa",
        border_style="#45475a",
        row_styles=["", "on #181825"],
    )
    table.add_column("", width=3)  # health icon
    table.add_column("Node", min_width=24)
    table.add_column("Namespace", min_width=12)
    table.add_column("Health", width=10)
    table.add_column("PID", justify="right", width=8)
    table.add_column("Pubs", justify="right", width=6)
    table.add_column("Subs", justify="right", width=6)
    table.add_column("Services", justify="right", width=9)

    if not snapshot.nodes:
        console.print("[dim]No nodes discovered.[/]")
        return

    for node in snapshot.nodes:
        color = _HEALTH_COLOR.get(node.health, "white")
        icon = _HEALTH_ICON.get(node.health, "[?]")
        pid_str = str(node.pid) if node.pid else "-"
        table.add_row(
            Text(icon, style=color),
            node.name,
            node.namespace,
            Text(node.health.value, style=color),
            pid_str,
            str(len(node.published_topics)),
            str(len(node.subscribed_topics)),
            str(len(node.services)),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# rosm topics
# ---------------------------------------------------------------------------

@cli.command("topics")
@click.option("--hz", is_flag=True, help="Measure topic Hz (slower, requires rclpy)")
def topics(hz: bool) -> None:
    """List topics with pub/sub info."""
    if not has_rclpy() and hz:
        console.print("[yellow]--hz requires rclpy. Skipping Hz measurement.[/]")
        hz = False

    with Live(Spinner("dots", text="Introspecting topics..."), console=console, transient=True):
        snapshot = _load_graph_snapshot()

    table = Table(
        title="ROS2 Topics",
        header_style="bold #89b4fa",
        border_style="#45475a",
        row_styles=["", "on #181825"],
    )
    table.add_column("Topic", min_width=30)
    table.add_column("Type", min_width=30)
    table.add_column("Pubs", justify="right", width=6)
    table.add_column("Subs", justify="right", width=6)
    if hz:
        table.add_column("Hz", justify="right", width=8)

    if not snapshot.topics:
        console.print("[dim]No topics discovered.[/]")
        return

    for topic in snapshot.topics:
        pub_style = "yellow" if topic.pub_count > 1 else ("red" if topic.pub_count == 0 else "white")
        sub_style = "dim" if topic.sub_count == 0 else "white"
        row: list[Any] = [
            topic.name,
            topic.msg_type,
            Text(str(topic.pub_count), style=pub_style),
            Text(str(topic.sub_count), style=sub_style),
        ]
        if hz:
            hz_str = f"{topic.hz:.1f}" if topic.hz is not None else "-"
            row.append(hz_str)
        table.add_row(*row)

    console.print(table)


# ---------------------------------------------------------------------------
# rosm services
# ---------------------------------------------------------------------------

@cli.command("services")
def services() -> None:
    """List ROS2 services."""
    if not has_rclpy():
        console.print("[yellow]rclpy not available. Source ROS2 first.[/]")
        raise SystemExit(1)

    with Live(Spinner("dots", text="Discovering services..."), console=console, transient=True):
        snapshot = _load_graph_snapshot()

    table = Table(
        title="ROS2 Services",
        header_style="bold #89b4fa",
        border_style="#45475a",
        row_styles=["", "on #181825"],
    )
    table.add_column("Service", min_width=30)
    table.add_column("Type", min_width=30)
    table.add_column("Node", min_width=20)
    table.add_column("Namespace", min_width=12)

    if not snapshot.services:
        console.print("[dim]No services discovered.[/]")
        return

    for svc in snapshot.services:
        table.add_row(svc.name, svc.service_type, svc.node_name, svc.node_namespace)

    console.print(table)


# ---------------------------------------------------------------------------
# rosm conflicts
# ---------------------------------------------------------------------------

@cli.command("conflicts")
def conflicts() -> None:
    """Detect and report conflicts."""
    with Live(
        Spinner("dots", text="Analyzing system..."),
        console=console,
        transient=True,
    ):
        snapshot = _load_full_snapshot()
        snapshot = _run_conflict_engine(snapshot)

    if not snapshot.conflicts:
        console.print(
            Panel(
                "[bold green][+] No conflicts detected.[/]",
                border_style="green",
            )
        )
        return

    # Group by severity
    order = {ConflictSeverity.ERROR: 0, ConflictSeverity.WARNING: 1, ConflictSeverity.INFO: 2}
    sorted_conflicts = sorted(snapshot.conflicts, key=lambda c: order[c.severity])

    for conflict in sorted_conflicts:
        color = _SEVERITY_COLOR[conflict.severity]
        icon = _SEVERITY_ICON[conflict.severity]
        entities = ", ".join(conflict.affected_entities) if conflict.affected_entities else ""

        body_lines = [conflict.description]
        if entities:
            body_lines.append(f"[dim]Affected:[/] {entities}")
        if conflict.suggested_fix:
            body_lines.append(f"[cyan]Fix:[/] {conflict.suggested_fix}")

        console.print(
            Panel(
                "\n".join(body_lines),
                title=f"[{color}]{icon} {conflict.title}[/]",
                border_style=color,
                expand=False,
            )
        )

    err_count = sum(1 for c in snapshot.conflicts if c.severity == ConflictSeverity.ERROR)
    warn_count = sum(1 for c in snapshot.conflicts if c.severity == ConflictSeverity.WARNING)
    info_count = sum(1 for c in snapshot.conflicts if c.severity == ConflictSeverity.INFO)
    console.print(
        f"\n[dim]Summary:[/] "
        f"[red]{err_count} error(s)[/]  "
        f"[yellow]{warn_count} warning(s)[/]  "
        f"[cyan]{info_count} info[/]"
    )


# ---------------------------------------------------------------------------
# rosm doctor
# ---------------------------------------------------------------------------

@cli.command("doctor")
def doctor() -> None:
    """Comprehensive health report."""
    console.print(Panel("[bold #89b4fa]rosm doctor — System Health Report[/]", border_style="#89b4fa"))

    with Live(
        Spinner("dots", text="Running diagnostics..."),
        console=console,
        transient=True,
    ):
        snapshot = _load_full_snapshot()
        snapshot = _run_conflict_engine(snapshot)

    # System info
    import psutil  # type: ignore[import-untyped]

    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    mem_used_gb = mem.used / (1024**3)
    mem_total_gb = mem.total / (1024**3)

    sys_table = Table(title="System", header_style="bold #89b4fa", border_style="#45475a")
    sys_table.add_column("Metric")
    sys_table.add_column("Value")
    sys_table.add_row("CPU usage", f"{cpu:.1f}%")
    sys_table.add_row("Memory", f"{mem_used_gb:.1f} / {mem_total_gb:.1f} GB ({mem.percent:.0f}%)")
    sys_table.add_row("ROS distro", snapshot.ros_distro or "unknown")
    sys_table.add_row("RMW", snapshot.rmw_implementation or "unknown")
    domain_str = str(snapshot.domain_id) if snapshot.domain_id is not None else "[yellow]unset[/]"
    sys_table.add_row("Domain ID", domain_str)
    sys_table.add_row("Processes", str(len(snapshot.processes)))
    sys_table.add_row("Nodes", str(len(snapshot.nodes)))
    sys_table.add_row("Topics", str(len(snapshot.topics)))
    sys_table.add_row("SHM files", str(len(snapshot.shm_files)))
    console.print(sys_table)

    # Conflicts
    if snapshot.conflicts:
        console.print()
        console.print("[bold]Conflicts:[/]")
        order = {ConflictSeverity.ERROR: 0, ConflictSeverity.WARNING: 1, ConflictSeverity.INFO: 2}
        for conflict in sorted(snapshot.conflicts, key=lambda c: order[c.severity]):
            color = _SEVERITY_COLOR[conflict.severity]
            icon = _SEVERITY_ICON[conflict.severity]
            console.print(f"  [{color}]{icon}[/] {conflict.title}")
            if conflict.suggested_fix:
                console.print(f"     [dim]{conflict.suggested_fix}[/]")
    else:
        console.print("\n[bold green][+] No conflicts detected.[/]")

    # Overall health verdict
    has_errors = any(c.severity == ConflictSeverity.ERROR for c in snapshot.conflicts)
    has_warnings = any(c.severity == ConflictSeverity.WARNING for c in snapshot.conflicts)
    if has_errors:
        console.print("\n[bold red]Health: DEGRADED — fix errors above[/]")
    elif has_warnings:
        console.print("\n[bold yellow]Health: WARNING — review warnings above[/]")
    else:
        console.print("\n[bold green]Health: OK[/]")


# ---------------------------------------------------------------------------
# rosm dashboard
# ---------------------------------------------------------------------------

@cli.command("dashboard")
def dashboard() -> None:
    """Launch real-time TUI dashboard."""
    try:
        from rosm.tui.app import run_dashboard
    except ImportError as exc:
        console.print(
            f"[red]TUI requires textual: pip install 'rosm[tui]'\n{exc}[/]"
        )
        raise SystemExit(1)

    with Live(Spinner("dots", text="Loading..."), console=console, transient=True):
        snapshot = _load_full_snapshot()

    run_dashboard(snapshot=snapshot)
