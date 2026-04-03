"""QoS mismatch detection rule."""

from __future__ import annotations

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot


# Incompatible combinations: (publisher_reliability, subscriber_reliability)
# or (publisher_durability, subscriber_durability)
_RELIABILITY_INCOMPATIBLE = {("BEST_EFFORT", "RELIABLE")}
_DURABILITY_INCOMPATIBLE = {("VOLATILE", "TRANSIENT_LOCAL")}


class QoSMismatchRule:
    """Detect QoS incompatibilities between publishers and subscribers."""

    name: str = "qos_mismatch"
    severity: ConflictSeverity = ConflictSeverity.ERROR

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        conflicts: list[Conflict] = []

        for topic in snapshot.topics:
            if not topic.publishers or not topic.subscribers:
                continue

            for pub in topic.publishers:
                for sub in topic.subscribers:
                    reasons: list[str] = []

                    rel_pair = (pub.qos.reliability, sub.qos.reliability)
                    if rel_pair in _RELIABILITY_INCOMPATIBLE:
                        reasons.append(
                            f"reliability: publisher={pub.qos.reliability}, "
                            f"subscriber={sub.qos.reliability}"
                        )

                    dur_pair = (pub.qos.durability, sub.qos.durability)
                    if dur_pair in _DURABILITY_INCOMPATIBLE:
                        reasons.append(
                            f"durability: publisher={pub.qos.durability}, "
                            f"subscriber={sub.qos.durability}"
                        )

                    if reasons:
                        conflicts.append(
                            Conflict(
                                rule_name=self.name,
                                severity=self.severity,
                                title=f"QoS mismatch on {topic.name}",
                                description=(
                                    f"Topic {topic.name}: QoS incompatibility between "
                                    f"{pub.node_namespace}/{pub.node_name} (pub) and "
                                    f"{sub.node_namespace}/{sub.node_name} (sub). "
                                    + "; ".join(reasons)
                                ),
                                affected_entities=(topic.name,),
                                suggested_fix=(
                                    "Align QoS profiles: use RELIABLE durability on both sides "
                                    "or ensure publisher offers at least what subscriber requires."
                                ),
                            )
                        )

        return conflicts
