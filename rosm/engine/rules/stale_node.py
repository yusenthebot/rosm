"""Stale node detection rule."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, NodeHealth, SystemSnapshot


class StaleNodeRule:
    """Detect nodes with STALE health status."""

    name: str = "stale_node"
    severity: ConflictSeverity = ConflictSeverity.INFO

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        for node in snapshot.nodes:
            if node.health == NodeHealth.STALE:
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Stale node: {node.full_name}",
                        description=(
                            f"Node {node.full_name} (PID {node.pid}) has health=STALE. "
                            f"It may have stopped publishing heartbeats or lifecycle "
                            f"transitions have stalled."
                        ),
                        affected_entities=(node.full_name,),
                        suggested_fix=(
                            "Check node logs: ros2 node info " + node.full_name + ". "
                            "Restart node or reinitiate lifecycle transition."
                        ),
                    )
                )

        return conflicts
