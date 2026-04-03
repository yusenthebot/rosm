"""Tests for QoSMismatchRule."""

from __future__ import annotations

import pytest

from rosm.models import (
    ConflictSeverity,
    EndpointInfo,
    QoSProfile,
    RosmTopic,
    SystemSnapshot,
)


class TestQoSMismatchRule:
    def test_detects_best_effort_publisher_reliable_subscriber(
        self, topic_with_qos_mismatch
    ):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        rule = QoSMismatchRule()
        snapshot = SystemSnapshot(topics=[topic_with_qos_mismatch])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.ERROR for c in conflicts)

    def test_rule_name_is_qos_mismatch(self):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        rule = QoSMismatchRule()
        assert rule.name == "qos_mismatch"

    def test_rule_severity_is_error(self):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        rule = QoSMismatchRule()
        assert rule.severity == ConflictSeverity.ERROR

    def test_no_conflict_when_both_reliable(self):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        topic = RosmTopic(
            name="/good_topic",
            msg_type="std_msgs/msg/String",
            publishers=(
                EndpointInfo(
                    node_name="pub",
                    node_namespace="/",
                    qos=QoSProfile(reliability="RELIABLE", durability="VOLATILE"),
                ),
            ),
            subscribers=(
                EndpointInfo(
                    node_name="sub",
                    node_namespace="/",
                    qos=QoSProfile(reliability="RELIABLE", durability="VOLATILE"),
                ),
            ),
        )
        rule = QoSMismatchRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_when_no_subscribers(self):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        topic = RosmTopic(
            name="/orphan",
            msg_type="std_msgs/msg/String",
            publishers=(
                EndpointInfo(
                    node_name="pub",
                    node_namespace="/",
                    qos=QoSProfile(reliability="BEST_EFFORT"),
                ),
            ),
            subscribers=(),
        )
        rule = QoSMismatchRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_detects_volatile_publisher_transient_local_subscriber(self):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        topic = RosmTopic(
            name="/latched_topic",
            msg_type="std_msgs/msg/String",
            publishers=(
                EndpointInfo(
                    node_name="pub",
                    node_namespace="/",
                    qos=QoSProfile(reliability="RELIABLE", durability="VOLATILE"),
                ),
            ),
            subscribers=(
                EndpointInfo(
                    node_name="sub",
                    node_namespace="/",
                    qos=QoSProfile(reliability="RELIABLE", durability="TRANSIENT_LOCAL"),
                ),
            ),
        )
        rule = QoSMismatchRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1

    def test_conflict_mentions_topic_name(self, topic_with_qos_mismatch):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        rule = QoSMismatchRule()
        snapshot = SystemSnapshot(topics=[topic_with_qos_mismatch])
        conflicts = rule.check(snapshot)
        assert any(
            "/terrain_map" in c.description or "/terrain_map" in str(c.affected_entities)
            for c in conflicts
        )

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        rule = QoSMismatchRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
