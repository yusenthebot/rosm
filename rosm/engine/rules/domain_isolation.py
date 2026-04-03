"""Domain isolation check rule."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot


class DomainIsolationRule:
    """Detect when ROS_DOMAIN_ID is not set (domain_id is None)."""

    name: str = "domain_isolation"
    severity: ConflictSeverity = ConflictSeverity.INFO

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        if snapshot.domain_id is not None:
            return []

        return [
            Conflict(
                rule_name=self.name,
                severity=self.severity,
                title="ROS_DOMAIN_ID not set",
                description=(
                    "ROS_DOMAIN_ID is not configured (domain_id=None). "
                    "All ROS2 nodes on the network share domain 0 by default, "
                    "which can cause unintended cross-robot interference."
                ),
                affected_entities=(),
                suggested_fix=(
                    "Set ROS_DOMAIN_ID to an integer (0-101) in your shell: "
                    "export ROS_DOMAIN_ID=<id>. "
                    "Use a unique ID per robot/team to isolate DDS traffic."
                ),
            )
        ]
