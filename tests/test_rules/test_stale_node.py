"""Tests for StaleNodeRule."""

from __future__ import annotations

import pytest

from rosm.models import ConflictSeverity, NodeHealth, RosmNode, SystemSnapshot


class TestStaleNodeRule:
    def test_rule_name(self):
        from rosm.engine.rules.stale_node import StaleNodeRule
        rule = StaleNodeRule()
        assert rule.name == "stale_node"

    def test_rule_severity_is_info(self):
        from rosm.engine.rules.stale_node import StaleNodeRule
        rule = StaleNodeRule()
        assert rule.severity == ConflictSeverity.INFO

    def test_detects_stale_node(self, stale_node):
        from rosm.engine.rules.stale_node import StaleNodeRule
        rule = StaleNodeRule()
        snapshot = SystemSnapshot(nodes=[stale_node])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.INFO for c in conflicts)

    def test_no_conflict_healthy_node(self, healthy_node):
        from rosm.engine.rules.stale_node import StaleNodeRule
        rule = StaleNodeRule()
        snapshot = SystemSnapshot(nodes=[healthy_node])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_unknown_health(self):
        from rosm.engine.rules.stale_node import StaleNodeRule
        node = RosmNode(
            name="unknown_node",
            namespace="/",
            full_name="/unknown_node",
            health=NodeHealth.UNKNOWN,
        )
        rule = StaleNodeRule()
        snapshot = SystemSnapshot(nodes=[node])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_conflict_mentions_node_name(self, stale_node):
        from rosm.engine.rules.stale_node import StaleNodeRule
        rule = StaleNodeRule()
        snapshot = SystemSnapshot(nodes=[stale_node])
        conflicts = rule.check(snapshot)
        assert any(
            "far_planner" in c.description or "far_planner" in str(c.affected_entities)
            for c in conflicts
        )

    def test_multiple_stale_nodes_multiple_conflicts(self):
        from rosm.engine.rules.stale_node import StaleNodeRule
        nodes = [
            RosmNode(
                name=f"stale_{i}",
                namespace="/",
                full_name=f"/stale_{i}",
                health=NodeHealth.STALE,
            )
            for i in range(3)
        ]
        rule = StaleNodeRule()
        snapshot = SystemSnapshot(nodes=nodes)
        conflicts = rule.check(snapshot)
        assert len(conflicts) == 3

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.stale_node import StaleNodeRule
        rule = StaleNodeRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
