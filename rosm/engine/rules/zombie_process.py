"""Zombie/orphan process detection rule."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, ProcessStatus, SystemSnapshot


_ZOMBIE_STATUSES = {ProcessStatus.ZOMBIE, ProcessStatus.ORPHAN}


class ZombieProcessRule:
    """Detect zombie or orphaned ROS2 processes."""

    name: str = "zombie_process"
    severity: ConflictSeverity = ConflictSeverity.WARNING

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        for proc in snapshot.processes:
            if proc.status in _ZOMBIE_STATUSES:
                node_info = (
                    f" (node: {proc.ros2_node_name})" if proc.ros2_node_name else ""
                )
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Zombie/orphan process: {proc.name} (PID {proc.pid})",
                        description=(
                            f"Process {proc.name}{node_info} with PID {proc.pid} has "
                            f"status={proc.status.value}. It may be holding ROS2 resources."
                        ),
                        affected_entities=(str(proc.pid),),
                        suggested_fix=(
                            f"Kill process: kill -9 {proc.pid}. "
                            "Then restart the affected launch file."
                        ),
                    )
                )

        return conflicts
