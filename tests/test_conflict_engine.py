"""Tests for ConflictEngine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rosm.models import Conflict, ConflictSeverity, SystemSnapshot


class TestConflictEngineInit:
    def test_engine_has_default_rules(self):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        assert len(engine._rules) == 9

    def test_default_rules_have_name_and_severity(self):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        for rule in engine._rules:
            assert hasattr(rule, "name")
            assert hasattr(rule, "severity")
            assert isinstance(rule.severity, ConflictSeverity)


class TestConflictEngineEvaluate:
    def test_evaluate_returns_conflicts(self, full_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        conflicts = engine.evaluate(full_snapshot)
        assert isinstance(conflicts, list)
        for c in conflicts:
            assert isinstance(c, Conflict)

    def test_evaluate_empty_snapshot_returns_list(self, empty_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        # domain_id is None on empty_snapshot, so domain_isolation may fire
        conflicts = engine.evaluate(empty_snapshot)
        assert isinstance(conflicts, list)

    def test_evaluate_sorts_errors_first(self, full_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        conflicts = engine.evaluate(full_snapshot)
        if len(conflicts) < 2:
            pytest.skip("Need at least 2 conflicts to test ordering")
        severities = [c.severity for c in conflicts]
        # Find first non-error
        first_non_error = next(
            (i for i, s in enumerate(severities) if s != ConflictSeverity.ERROR),
            len(severities),
        )
        # All after first non-error should not be errors
        for i in range(first_non_error + 1, len(severities)):
            assert severities[i] != ConflictSeverity.ERROR

    def test_evaluate_with_mock_rules(self, empty_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        engine._rules = []  # clear defaults

        mock_rule = MagicMock()
        mock_rule.name = "test_rule"
        mock_rule.severity = ConflictSeverity.ERROR
        mock_rule.check.return_value = [
            Conflict(
                rule_name="test_rule",
                severity=ConflictSeverity.ERROR,
                title="Test",
                description="Test conflict",
            )
        ]
        engine._rules.append(mock_rule)

        conflicts = engine.evaluate(empty_snapshot)
        assert len(conflicts) == 1
        assert conflicts[0].rule_name == "test_rule"
        mock_rule.check.assert_called_once_with(empty_snapshot)

    def test_evaluate_aggregates_from_all_rules(self, empty_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        engine._rules = []

        for i in range(3):
            mock_rule = MagicMock()
            mock_rule.name = f"rule_{i}"
            mock_rule.severity = ConflictSeverity.WARNING
            mock_rule.check.return_value = [
                Conflict(
                    rule_name=f"rule_{i}",
                    severity=ConflictSeverity.WARNING,
                    title=f"Warning {i}",
                    description=f"Desc {i}",
                )
            ]
            engine._rules.append(mock_rule)

        conflicts = engine.evaluate(empty_snapshot)
        assert len(conflicts) == 3

    def test_evaluate_sort_order_error_warning_info(self, empty_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        engine._rules = []

        for severity, name in [
            (ConflictSeverity.INFO, "info_rule"),
            (ConflictSeverity.WARNING, "warn_rule"),
            (ConflictSeverity.ERROR, "err_rule"),
        ]:
            mock_rule = MagicMock()
            mock_rule.name = name
            mock_rule.severity = severity
            mock_rule.check.return_value = [
                Conflict(
                    rule_name=name,
                    severity=severity,
                    title=name,
                    description=name,
                )
            ]
            engine._rules.append(mock_rule)

        conflicts = engine.evaluate(empty_snapshot)
        assert len(conflicts) == 3
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert conflicts[1].severity == ConflictSeverity.WARNING
        assert conflicts[2].severity == ConflictSeverity.INFO

    def test_evaluate_rule_exception_does_not_crash_engine(self, empty_snapshot):
        from rosm.engine.conflict_engine import ConflictEngine
        engine = ConflictEngine()
        engine._rules = []

        bad_rule = MagicMock()
        bad_rule.name = "bad_rule"
        bad_rule.severity = ConflictSeverity.ERROR
        bad_rule.check.side_effect = RuntimeError("boom")

        good_rule = MagicMock()
        good_rule.name = "good_rule"
        good_rule.severity = ConflictSeverity.WARNING
        good_rule.check.return_value = [
            Conflict(
                rule_name="good_rule",
                severity=ConflictSeverity.WARNING,
                title="OK",
                description="fine",
            )
        ]

        engine._rules.extend([bad_rule, good_rule])
        # Should not raise — bad rule skipped, good rule counted
        conflicts = engine.evaluate(empty_snapshot)
        assert any(c.rule_name == "good_rule" for c in conflicts)
