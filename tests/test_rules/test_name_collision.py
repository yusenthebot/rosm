"""Tests for NodeNameCollisionRule."""

from __future__ import annotations

import pytest

from rosm.models import ConflictSeverity, NodeHealth, RosmNode, SystemSnapshot


class TestNodeNameCollisionRule:
    def test_rule_name(self):
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        rule = NodeNameCollisionRule()
        assert rule.name == "name_collision"

    def test_rule_severity_is_error(self):
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        rule = NodeNameCollisionRule()
        assert rule.severity == ConflictSeverity.ERROR

    def test_no_collision_in_different_namespaces(self, sample_nodes):
        """sample_nodes has localPlanner in / and /sim — NOT a collision."""
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        rule = NodeNameCollisionRule()
        snapshot = SystemSnapshot(nodes=sample_nodes)
        conflicts = rule.check(snapshot)
        # localPlanner in / vs /sim is not a collision — different full_name
        assert conflicts == []

    def test_detects_true_collision(self):
        """Two nodes with same name AND namespace = collision."""
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        nodes = [
            RosmNode(
                name="controller",
                namespace="/",
                full_name="/controller",
                health=NodeHealth.HEALTHY,
            ),
            RosmNode(
                name="controller",
                namespace="/",
                full_name="/controller",
                health=NodeHealth.HEALTHY,
                pid=99999,
            ),
        ]
        rule = NodeNameCollisionRule()
        snapshot = SystemSnapshot(nodes=nodes)
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.ERROR for c in conflicts)

    def test_collision_conflict_mentions_node_name(self):
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        nodes = [
            RosmNode(
                name="duplicate_node",
                namespace="/",
                full_name="/duplicate_node",
                health=NodeHealth.HEALTHY,
            ),
            RosmNode(
                name="duplicate_node",
                namespace="/",
                full_name="/duplicate_node",
                health=NodeHealth.HEALTHY,
            ),
        ]
        rule = NodeNameCollisionRule()
        snapshot = SystemSnapshot(nodes=nodes)
        conflicts = rule.check(snapshot)
        assert any(
            "duplicate_node" in c.description or "duplicate_node" in str(c.affected_entities)
            for c in conflicts
        )

    def test_no_collision_unique_nodes(self):
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        nodes = [
            RosmNode(name="nodeA", namespace="/", full_name="/nodeA", health=NodeHealth.HEALTHY),
            RosmNode(name="nodeB", namespace="/", full_name="/nodeB", health=NodeHealth.HEALTHY),
            RosmNode(name="nodeA", namespace="/sim", full_name="/sim/nodeA", health=NodeHealth.HEALTHY),
        ]
        rule = NodeNameCollisionRule()
        snapshot = SystemSnapshot(nodes=nodes)
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        rule = NodeNameCollisionRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
