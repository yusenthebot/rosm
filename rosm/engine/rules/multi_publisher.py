"""Multi-publisher detection rule for single-publisher topics."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot

# Topics that should only ever have a single authoritative publisher
_SINGLE_PUBLISHER_TOPICS = {
    "/cmd_vel",
    "/cmd_vel_nav",
    "/navigation_cmd_vel",
}


class MultiPublisherRule:
    """Detect topics that should be single-publisher but have multiple publishers."""

    name: str = "multi_publisher"
    severity: ConflictSeverity = ConflictSeverity.WARNING

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        for topic in snapshot.topics:
            if topic.name not in _SINGLE_PUBLISHER_TOPICS:
                continue

            if topic.pub_count > 1:
                publisher_names = ", ".join(
                    f"{ep.node_namespace}/{ep.node_name}" for ep in topic.publishers
                )
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Multiple publishers on {topic.name}",
                        description=(
                            f"Topic {topic.name} has {topic.pub_count} publishers "
                            f"({publisher_names}). This topic should have exactly one "
                            f"authoritative publisher to avoid conflicting velocity commands."
                        ),
                        affected_entities=(topic.name,),
                        suggested_fix=(
                            f"Ensure only one node publishes to {topic.name} at a time. "
                            "Use a velocity multiplexer (e.g. twist_mux) if multiple "
                            "sources need to share the topic."
                        ),
                    )
                )

        return conflicts
