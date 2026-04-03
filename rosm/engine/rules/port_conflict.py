"""Port conflict detection rule."""

from __future__ import annotations

from collections import defaultdict

from rosm.models import Conflict, ConflictSeverity, PortBinding, SystemSnapshot


class PortConflictRule:
    """Detect (port, protocol) pairs bound by more than one PID."""

    name: str = "port_conflict"
    severity: ConflictSeverity = ConflictSeverity.ERROR

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        # Group bindings by (port, protocol)
        groups: dict[tuple[int, str], list[PortBinding]] = defaultdict(list)
        for binding in snapshot.port_bindings:
            groups[(binding.port, binding.protocol)].append(binding)

        for (port, protocol), bindings in groups.items():
            # Only flag when multiple *distinct* PIDs own the same port+protocol
            pids = {b.pid for b in bindings if b.pid is not None}
            if len(pids) > 1:
                pid_list = ", ".join(str(p) for p in sorted(pids))
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Port conflict: {protocol.upper()} {port}",
                        description=(
                            f"Port {port}/{protocol} is bound by multiple processes "
                            f"(PIDs: {pid_list}). This causes DDS discovery failures."
                        ),
                        affected_entities=(f"{protocol}:{port}",),
                        suggested_fix=(
                            f"Kill stale processes holding port {port} or "
                            "configure distinct DDS ports via CYCLONEDDS_URI / fastdds XML."
                        ),
                    )
                )

        return conflicts
