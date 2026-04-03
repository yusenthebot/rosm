"""Kill action — kill by PID or name pattern."""

from __future__ import annotations

from rosm.probes.process_probe import ProcessProbe


def kill_target(target: str, force: bool = False) -> list[int]:
    """Kill by PID (if *target* is numeric) or by name pattern.

    Returns list of killed PIDs.
    """
    probe = ProcessProbe()

    # Numeric string → kill by PID
    if target.isdigit():
        pid = int(target)
        if probe.kill_process(pid, force=force):
            return [pid]
        return []

    # Otherwise treat as name pattern
    return probe.kill_by_name(target, force=force)
