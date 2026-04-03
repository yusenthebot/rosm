"""Tests for ZombieProcessRule."""

from __future__ import annotations

import pytest

from rosm.models import ConflictSeverity, ProcessStatus, RosmProcess, SystemSnapshot
from datetime import datetime


class TestZombieProcessRule:
    def test_rule_name(self):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        rule = ZombieProcessRule()
        assert rule.name == "zombie_process"

    def test_rule_severity_is_warning(self):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        rule = ZombieProcessRule()
        assert rule.severity == ConflictSeverity.WARNING

    def test_detects_orphan_process(self, zombie_process):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        rule = ZombieProcessRule()
        snapshot = SystemSnapshot(processes=[zombie_process])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1
        assert all(c.severity == ConflictSeverity.WARNING for c in conflicts)

    def test_detects_zombie_status(self):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        proc = RosmProcess(
            pid=11111,
            name="dead_node",
            cmdline="dead_node --ros-args",
            status=ProcessStatus.ZOMBIE,
            create_time=datetime(2026, 4, 1, 10, 0),
        )
        rule = ZombieProcessRule()
        snapshot = SystemSnapshot(processes=[proc])
        conflicts = rule.check(snapshot)
        assert len(conflicts) >= 1

    def test_no_conflict_for_running_process(self, healthy_process):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        rule = ZombieProcessRule()
        snapshot = SystemSnapshot(processes=[healthy_process])
        conflicts = rule.check(snapshot)
        assert conflicts == []

    def test_conflict_mentions_pid(self, zombie_process):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        rule = ZombieProcessRule()
        snapshot = SystemSnapshot(processes=[zombie_process])
        conflicts = rule.check(snapshot)
        assert any(
            str(zombie_process.pid) in c.description or str(zombie_process.pid) in str(c.affected_entities)
            for c in conflicts
        )

    def test_empty_snapshot_no_conflicts(self, empty_snapshot):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        rule = ZombieProcessRule()
        conflicts = rule.check(empty_snapshot)
        assert conflicts == []

    def test_multiple_zombies_multiple_conflicts(self):
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        procs = [
            RosmProcess(
                pid=i,
                name=f"zombie_{i}",
                cmdline=f"zombie_{i} --ros-args",
                status=ProcessStatus.ZOMBIE,
            )
            for i in range(1, 4)
        ]
        rule = ZombieProcessRule()
        snapshot = SystemSnapshot(processes=procs)
        conflicts = rule.check(snapshot)
        assert len(conflicts) == 3
