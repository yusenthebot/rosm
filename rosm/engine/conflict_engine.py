"""ConflictEngine — runs all conflict rules against a SystemSnapshot."""

from __future__ import annotations

import logging
from typing import Protocol

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot

logger = logging.getLogger(__name__)

# Severity ordering for sorting (lower = higher priority)
_SEVERITY_ORDER: dict[ConflictSeverity, int] = {
    ConflictSeverity.ERROR: 0,
    ConflictSeverity.WARNING: 1,
    ConflictSeverity.INFO: 2,
}


class ConflictRule(Protocol):
    """Protocol that all conflict rules must satisfy."""

    name: str
    severity: ConflictSeverity

    def check(self, snapshot: SystemSnapshot) -> list[Conflict]:
        """Inspect snapshot and return any detected conflicts."""
        ...


class ConflictEngine:
    """Runs all registered ConflictRule instances against a SystemSnapshot."""

    def __init__(self) -> None:
        self._rules: list[ConflictRule] = []
        self._register_default_rules()

    def evaluate(self, snapshot: SystemSnapshot) -> list[Conflict]:
        """Run all rules, return sorted conflicts (errors first).

        Rules that raise exceptions are logged and skipped — they do not
        prevent other rules from running.
        """
        all_conflicts: list[Conflict] = []

        for rule in self._rules:
            try:
                conflicts = rule.check(snapshot)
                all_conflicts.extend(conflicts)
            except Exception as exc:
                logger.warning("Rule %r raised an exception: %s", rule.name, exc)

        all_conflicts.sort(key=lambda c: _SEVERITY_ORDER.get(c.severity, 99))
        return all_conflicts

    def _register_default_rules(self) -> None:
        """Register all 9 built-in rules."""
        from rosm.engine.rules.qos_mismatch import QoSMismatchRule
        from rosm.engine.rules.name_collision import NodeNameCollisionRule
        from rosm.engine.rules.port_conflict import PortConflictRule
        from rosm.engine.rules.zombie_process import ZombieProcessRule
        from rosm.engine.rules.orphaned_topic import OrphanedTopicRule
        from rosm.engine.rules.shm_leak import ShmLeakRule
        from rosm.engine.rules.stale_node import StaleNodeRule
        from rosm.engine.rules.multi_publisher import MultiPublisherRule
        from rosm.engine.rules.domain_isolation import DomainIsolationRule

        self._rules = [
            QoSMismatchRule(),
            NodeNameCollisionRule(),
            PortConflictRule(),
            ZombieProcessRule(),
            ShmLeakRule(),
            MultiPublisherRule(),
            OrphanedTopicRule(),
            StaleNodeRule(),
            DomainIsolationRule(),
        ]
