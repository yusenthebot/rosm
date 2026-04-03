"""Clean action — kill zombies + clean SHM + reset daemon."""

from __future__ import annotations

from rosm.models import CleanResult, ProcessStatus
from rosm.probes.process_probe import ProcessProbe
from rosm.probes.system_probe import SystemProbe

_UNHEALTHY_STATUSES = frozenset({ProcessStatus.ORPHAN, ProcessStatus.ZOMBIE, ProcessStatus.DEAD})


def clean_system(dry_run: bool = False) -> CleanResult:
    """Kill zombie/orphan processes, clean SHM files, and reset the daemon.

    When dry_run=True no destructive operations are performed; the result
    reflects what *would* have been done.

    Returns a CleanResult summary.
    """
    proc_probe = ProcessProbe()
    sys_probe = SystemProbe()

    # Find unhealthy processes
    processes = proc_probe.snapshot()
    unhealthy = [p for p in processes if p.status in _UNHEALTHY_STATUSES]

    killed_pids: list[int] = []
    if not dry_run:
        for proc in unhealthy:
            if proc_probe.kill_process(proc.pid):
                killed_pids.append(proc.pid)
    else:
        killed_pids = [p.pid for p in unhealthy]

    # Clean shared memory
    shm_removed = sys_probe.clean_shm(dry_run=dry_run)

    # Reset daemon (skip in dry_run)
    daemon_restarted = False
    if not dry_run:
        daemon_restarted = sys_probe.reset_daemon()

    return CleanResult(
        killed_pids=killed_pids,
        shm_removed=shm_removed,
        daemon_restarted=daemon_restarted,
        dry_run=dry_run,
    )
