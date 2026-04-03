"""Tests for MultiPublisherRule."""

from __future__ import annotations

import pytest

from rosm.models import (
    ConflictSeverity,
    EndpointInfo,
    RosmTopic,
    SystemSnapshot,
)


class TestMultiPublisherRule:
    def test_rule_name(self):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        rule = MultiPublisherRule()
        assert rule.name == "multi_publisher"

    def test_rule_severity_is_warning(self):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        rule = MultiPublisherRule()
        assert rule.severity == ConflictSeverity.WARNING

    def test_detects_multi_pub_on_cmd_vel(self, multi_pub_topic):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        rule = MultiPublisherRule()
        snapshot = SystemSnapshot(topics=[multi_pub_topic])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.WARNING for c in conflicts)

    def test_no_conflict_single_publisher(self):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        topic = RosmTopic(
            name="/cmd_vel",
            msg_type="geometry_msgs/msg/TwistStamped",
            publishers=(EndpointInfo(node_name="pathFollower", node_namespace="/"),),
            subscribers=(EndpointInfo(node_name="robot", node_namespace="/"),),
        )
        rule = MultiPublisherRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_multi_pub_non_single_pub_topic(self):
        """A topic not in the single-publisher list with multi-pub is OK."""
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        topic = RosmTopic(
            name="/sensor_data",
            msg_type="sensor_msgs/msg/LaserScan",
            publishers=(
                EndpointInfo(node_name="sensor1", node_namespace="/"),
                EndpointInfo(node_name="sensor2", node_namespace="/"),
            ),
            subscribers=(EndpointInfo(node_name="fusion", node_namespace="/"),),
        )
        rule = MultiPublisherRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_detects_cmd_vel_nav(self):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        topic = RosmTopic(
            name="/cmd_vel_nav",
            msg_type="geometry_msgs/msg/TwistStamped",
            publishers=(
                EndpointInfo(node_name="planner", node_namespace="/"),
                EndpointInfo(node_name="override", node_namespace="/"),
            ),
            subscribers=(EndpointInfo(node_name="robot", node_namespace="/"),),
        )
        rule = MultiPublisherRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1

    def test_detects_navigation_cmd_vel(self):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        topic = RosmTopic(
            name="/navigation_cmd_vel",
            msg_type="geometry_msgs/msg/TwistStamped",
            publishers=(
                EndpointInfo(node_name="nav", node_namespace="/"),
                EndpointInfo(node_name="override", node_namespace="/"),
            ),
            subscribers=(EndpointInfo(node_name="robot", node_namespace="/"),),
        )
        rule = MultiPublisherRule()
        snapshot = SystemSnapshot(topics=[topic])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1

    def test_conflict_mentions_topic_name(self, multi_pub_topic):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        rule = MultiPublisherRule()
        snapshot = SystemSnapshot(topics=[multi_pub_topic])
        conflicts = rule.check(snapshot)
        assert any(
            "/cmd_vel" in c.description or "/cmd_vel" in str(c.affected_entities)
            for c in conflicts
        )

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        rule = MultiPublisherRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
