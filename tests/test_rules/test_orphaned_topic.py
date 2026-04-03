"""Tests for OrphanedTopicRule."""

from __future__ import annotations

import pytest

from rosm.models import (
    ConflictSeverity,
    EndpointInfo,
    RosmTopic,
    SystemSnapshot,
)


class TestOrphanedTopicRule:
    def test_rule_name(self):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        rule = OrphanedTopicRule()
        assert rule.name == "orphaned_topic"

    def test_rule_severity_is_info(self):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        rule = OrphanedTopicRule()
        assert rule.severity == ConflictSeverity.INFO

    def test_detects_publisher_no_subscriber(self, orphaned_topic):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        rule = OrphanedTopicRule()
        snapshot = SystemSnapshot(topics=[orphaned_topic])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.INFO for c in conflicts)

    def test_detects_subscriber_no_publisher(self):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        topic = RosmTopic(
            name="/no_pub_topic",
            msg_type="std_msgs/msg/String",
            publishers=(),
            subscribers=(
                EndpointInfo(node_name="eager_sub", node_namespace="/"),
            ),
        )
        rule = OrphanedTopicRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1

    def test_excludes_rosout(self):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        topic = RosmTopic(
            name="/rosout",
            msg_type="rcl_interfaces/msg/Log",
            publishers=(EndpointInfo(node_name="any_node", node_namespace="/"),),
            subscribers=(),
        )
        rule = OrphanedTopicRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_excludes_parameter_events(self):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        topic = RosmTopic(
            name="/parameter_events",
            msg_type="rcl_interfaces/msg/ParameterEvent",
            publishers=(EndpointInfo(node_name="any_node", node_namespace="/"),),
            subscribers=(),
        )
        rule = OrphanedTopicRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_for_healthy_topic(self):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        topic = RosmTopic(
            name="/healthy_topic",
            msg_type="std_msgs/msg/String",
            publishers=(EndpointInfo(node_name="pub", node_namespace="/"),),
            subscribers=(EndpointInfo(node_name="sub", node_namespace="/"),),
        )
        rule = OrphanedTopicRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_conflict_mentions_topic_name(self, orphaned_topic):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        rule = OrphanedTopicRule()
        snapshot = SystemSnapshot(topics=[orphaned_topic])
        conflicts = rule.check(snapshot)
        assert any(
            "/dead_topic" in c.description or "/dead_topic" in str(c.affected_entities)
            for c in conflicts
        )

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        rule = OrphanedTopicRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
