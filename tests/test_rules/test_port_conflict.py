"""Tests for PortConflictRule."""

from __future__ import annotations

import pytest

from rosm.models import ConflictSeverity, PortBinding, SystemSnapshot


class TestPortConflictRule:
    def test_rule_name(self):
        from rosm.engine.rules.port_conflict import PortConflictRule
        rule = PortConflictRule()
        assert rule.name == "port_conflict"

    def test_rule_severity_is_error(self):
        from rosm.engine.rules.port_conflict import PortConflictRule
        rule = PortConflictRule()
        assert rule.severity == ConflictSeverity.ERROR

    def test_detects_port_conflict(self, port_conflict_bindings):
        from rosm.engine.rules.port_conflict import PortConflictRule
        rule = PortConflictRule()
        snapshot = SystemSnapshot(port_bindings=port_conflict_bindings)
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.ERROR for c in conflicts)

    def test_no_conflict_different_ports(self):
        from rosm.engine.rules.port_conflict import PortConflictRule
        bindings = [
            PortBinding(port=10000, protocol="tcp", pid=111, process_name="nodeA"),
            PortBinding(port=10001, protocol="tcp", pid=222, process_name="nodeB"),
        ]
        rule = PortConflictRule()
        snapshot = SystemSnapshot(port_bindings=bindings)
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_different_protocols(self):
        from rosm.engine.rules.port_conflict import PortConflictRule
        bindings = [
            PortBinding(port=10000, protocol="tcp", pid=111, process_name="nodeA"),
            PortBinding(port=10000, protocol="udp", pid=222, process_name="nodeB"),
        ]
        rule = PortConflictRule()
        snapshot = SystemSnapshot(port_bindings=bindings)
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_same_pid(self):
        """Same PID binding same port twice — not a conflict."""
        from rosm.engine.rules.port_conflict import PortConflictRule
        bindings = [
            PortBinding(port=10000, protocol="tcp", pid=111, process_name="nodeA"),
            PortBinding(port=10000, protocol="tcp", pid=111, process_name="nodeA"),
        ]
        rule = PortConflictRule()
        snapshot = SystemSnapshot(port_bindings=bindings)
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_conflict_mentions_port(self, port_conflict_bindings):
        from rosm.engine.rules.port_conflict import PortConflictRule
        rule = PortConflictRule()
        snapshot = SystemSnapshot(port_bindings=port_conflict_bindings)
        conflicts = rule.check(snapshot)
        assert any(
            "10000" in c.description or "10000" in str(c.affected_entities)
            for c in conflicts
        )

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.port_conflict import PortConflictRule
        rule = PortConflictRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
