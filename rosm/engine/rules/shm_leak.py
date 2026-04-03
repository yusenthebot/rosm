"""Shared memory leak detection rule."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot


class ShmLeakRule:
    """Detect orphaned shared memory files in /dev/shm."""

    name: str = "shm_leak"
    severity: ConflictSeverity = ConflictSeverity.WARNING

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        for shm in snapshot.shm_files:
            if shm.is_orphaned:
                size_kb = shm.size_bytes / 1024
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Orphaned SHM file: {shm.path}",
                        description=(
                            f"Shared memory file {shm.path} ({size_kb:.1f} KB) "
                            f"has no owning process (owner_pid={shm.owner_pid}). "
                            f"It is a leftover from a crashed ROS2 process."
                        ),
                        affected_entities=(shm.path,),
                        suggested_fix=f"Remove with: rm {shm.path}",
                    )
                )

        return conflicts
