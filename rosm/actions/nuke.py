"""Nuke action — kill ALL ROS2 processes + full cleanup."""

from __future__ import annotations

from rosm.models import NukeResult
from rosm.probes.process_probe import ProcessProbe
from rosm.probes.system_probe import SystemProbe


def nuke_all() -> NukeResult:
    """Kill every detected ROS2 process, wipe all SHM files, and restart the daemon.

    Returns a NukeResult summary.
    """
    proc_probe = ProcessProbe()
    sys_probe = SystemProbe()

    killed_pids = proc_probe.kill_all_ros2()
    shm_removed = sys_probe.clean_shm(dry_run=False)
    daemon_restarted = sys_probe.reset_daemon()

    return NukeResult(
        killed_pids=killed_pids,
        shm_removed=shm_removed,
        daemon_restarted=daemon_restarted,
    )
