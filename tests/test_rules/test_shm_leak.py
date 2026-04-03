"""Tests for ShmLeakRule."""

from __future__ import annotations

import pytest

from rosm.models import ConflictSeverity, ShmFile, SystemSnapshot


class TestShmLeakRule:
    def test_rule_name(self):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        rule = ShmLeakRule()
        assert rule.name == "shm_leak"

    def test_rule_severity_is_warning(self):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        rule = ShmLeakRule()
        assert rule.severity == ConflictSeverity.WARNING

    def test_detects_orphaned_shm(self, orphaned_shm_files):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        rule = ShmLeakRule()
        snapshot = SystemSnapshot(shm_files=orphaned_shm_files)
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.WARNING for c in conflicts)

    def test_orphaned_shm_each_gets_conflict(self, orphaned_shm_files):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        rule = ShmLeakRule()
        snapshot = SystemSnapshot(shm_files=orphaned_shm_files)
        conflicts = rule.check(snapshot)
        assert len(conflicts) == len(orphaned_shm_files)

    def test_no_conflict_for_active_shm(self):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        shm = ShmFile(
            path="/dev/shm/fastrtps_port7413",
            size_bytes=4096,
            owner_pid=12345,
            is_orphaned=False,
        )
        rule = ShmLeakRule()
        snapshot = SystemSnapshot(shm_files=[shm])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_conflict_mentions_path(self, orphaned_shm_files):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        rule = ShmLeakRule()
        snapshot = SystemSnapshot(shm_files=orphaned_shm_files)
        conflicts = rule.check(snapshot)
        paths = {f.path for f in orphaned_shm_files}
        found = set()
        for c in conflicts:
            for path in paths:
                if path in c.description or path in str(c.affected_entities):
                    found.add(path)
        assert len(found) > 0

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.shm_leak import ShmLeakRule
        rule = ShmLeakRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []
