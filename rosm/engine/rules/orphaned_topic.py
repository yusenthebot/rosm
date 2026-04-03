"""Orphaned topic detection rule."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot

# Topics that are intentionally publisher-only or subscriber-only
_EXCLUDED_TOPICS = {"/rosout", "/parameter_events"}


class OrphanedTopicRule:
    """Detect topics with publishers but no subscribers (or vice versa)."""

    name: str = "orphaned_topic"
    severity: ConflictSeverity = ConflictSeverity.INFO

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        for topic in snapshot.topics:
            if topic.name in _EXCLUDED_TOPICS:
                continue

            has_pubs = len(topic.publishers) > 0
            has_subs = len(topic.subscribers) > 0

            if has_pubs and not has_subs:
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Orphaned topic (no subscribers): {topic.name}",
                        description=(
                            f"Topic {topic.name} has {topic.pub_count} publisher(s) "
                            f"but no subscribers. Published data is discarded."
                        ),
                        affected_entities=(topic.name,),
                        suggested_fix=(
                            "Verify a subscriber node is running and connected. "
                            "Check topic name spelling and namespace."
                        ),
                    )
                )
            elif has_subs and not has_pubs:
                conflicts.append(
                    Conflict(
                        rule_name=self.name,
                        severity=self.severity,
                        title=f"Orphaned topic (no publishers): {topic.name}",
                        description=(
                            f"Topic {topic.name} has {topic.sub_count} subscriber(s) "
                            f"but no publishers. Subscribers will never receive data."
                        ),
                        affected_entities=(topic.name,),
                        suggested_fix=(
                            "Start the node that publishes this topic, or check "
                            "topic name remapping."
                        ),
                    )
                )

        return conflicts
