"""Tests for DomainIsolationRule."""

from __future__ import annotations

import pytest

from rosm.models import ConflictSeverity, SystemSnapshot


class TestDomainIsolationRule:
    def test_rule_name(self):
        from rosm.engine.rules.domain_isolation import DomainIsolationRule
        rule = DomainIsolationRule()
        assert rule.name == "domain_isolation"

    def test_rule_severity_is_info(self):
        from rosm.engine.rules.domain_isolation import DomainIsolationRule
        rule = DomainIsolationRule()
        assert rule.severity == ConflictSeverity.INFO

    def test_detects_none_domain_id(self, empty_snapshot):
        from rosm.engine.rules.domain_isolation import DomainIsolationRule
        rule = DomainIsolationRule()
        assert empty_snapshot.domain_id is None
        conflicts = rule.check(empty_snapshot)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.INFO

    def test_no_conflict_when_domain_id_set(self):
        from rosm.engine.rules.domain_isolation import DomainIsolationRule
        rule = DomainIsolationRule()
        snapshot = SystemSnapshot(domain_id=0)
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_no_conflict_domain_id_nonzero(self):
        from rosm.engine.rules.domain_isolation import DomainIsolationRule
        rule = DomainIsolationRule()
        snapshot = SystemSnapshot(domain_id=42)
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_full_snapshot_has_domain_id_no_conflict(self, full_snapshot):
        from rosm.engine.rules.domain_isolation import DomainIsolationRule
        rule = DomainIsolationRule()
        assert full_snapshot.domain_id == 0
        conflicts = rule.check(full_snapshot)
        assert conflicts == []
