"""Node name collision detection rule."""

from __future__ import annotations

from collections import Counter

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot


class NodeNameCollisionRule:
    """Detect duplicate (name, namespace) pairs among ROS2 nodes."""

    name: str = "name_collision"
    severity: ConflictSeverity = ConflictSeverity.ERROR

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        counts: Counter[tuple[str, str]] = Counter(
            (node.name, node.namespace) for node in snapshot.nodes
        )

        for (node_name, namespace), count in counts.items():
            if count > 1:
                full_name = (
                    f"/{node_name}" if namespace == "/" else f"{namespace}/{node_name}"
                )
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Node name collision: {full_name}",
                        description=(
                            f"Node {full_name} appears {count} times in the graph. "
                            f"Duplicate (name={node_name!r}, namespace={namespace!r})."
                        ),
                        affected_entities=(full_name,),
                        suggested_fix=(
                            "Assign unique node names via --ros-args -r __node:=<unique_name> "
                            "or use separate namespaces."
                        ),
                    )
                )

        return conflicts
