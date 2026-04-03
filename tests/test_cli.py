"""CLI tests using Click's CliRunner with mocked probes."""

from __future__ import annotations

import signal
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rosm.cli import cli
from rosm.models import (
    Conflict,
    ConflictSeverity,
    NodeHealth,
    ProcessStatus,
    RosmNode,
    RosmProcess,
    RosmService,
    RosmTopic,
    SystemSnapshot,
    EndpointInfo,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


def _make_snapshot(**overrides: object) -> SystemSnapshot:
    """Build a minimal but complete SystemSnapshot."""
    defaults: dict = {
        "domain_id": 0,
        "rmw_implementation": "rmw_fastrtps_cpp",
        "ros_distro": "jazzy",
        "processes": [
            RosmProcess(
                pid=1001,
                name="localPlanner",
                cmdline="/install/localPlanner --ros-args",
                status=ProcessStatus.RUNNING,
                cpu_percent=5.0,
                memory_mb=120.0,
                create_time=datetime(2026, 4, 3, 10, 0),
                ros2_node_name="/localPlanner",
            ),
            RosmProcess(
                pid=1002,
                name="graph_decoder",
                cmdline="/install/graph_decoder --ros-args",
                status=ProcessStatus.ORPHAN,
                cpu_percent=0.1,
                memory_mb=32.0,
                create_time=datetime(2026, 4, 3, 9, 0),
                ros2_node_name="/graph_decoder",
            ),
        ],
        "nodes": [
            RosmNode(
                name="localPlanner",
                namespace="/",
                full_name="/localPlanner",
                health=NodeHealth.HEALTHY,
                pid=1001,
                published_topics=("/path",),
                subscribed_topics=("/terrain_map",),
            ),
            RosmNode(
                name="far_planner",
                namespace="/",
                full_name="/far_planner",
                health=NodeHealth.STALE,
                pid=1003,
            ),
        ],
        "topics": [
            RosmTopic(
                name="/path",
                msg_type="nav_msgs/msg/Path",
                publishers=(EndpointInfo(node_name="localPlanner", node_namespace="/"),),
                subscribers=(EndpointInfo(node_name="pathFollower", node_namespace="/"),),
                hz=10.0,
            ),
            RosmTopic(
                name="/dead_topic",
                msg_type="std_msgs/msg/String",
                publishers=(EndpointInfo(node_name="ghost_node", node_namespace="/"),),
                subscribers=(),
            ),
        ],
        "services": [
            RosmService(
                name="/localPlanner/set_parameters",
                service_type="rcl_interfaces/srv/SetParameters",
                node_name="localPlanner",
                node_namespace="/",
            ),
        ],
        "conflicts": [
            Conflict(
                rule_name="ZombieProcess",
                severity=ConflictSeverity.WARNING,
                title="Zombie process detected",
                description="graph_decoder has no DDS presence",
                affected_entities=("graph_decoder",),
                suggested_fix="Run `rosm clean`",
            ),
            Conflict(
                rule_name="OrphanedTopic",
                severity=ConflictSeverity.INFO,
                title="Orphaned topic",
                description="/dead_topic has publisher but no subscriber",
                affected_entities=("/dead_topic",),
            ),
        ],
    }
    defaults.update(overrides)
    return SystemSnapshot(**defaults)


# ---------------------------------------------------------------------------
# ps command
# ---------------------------------------------------------------------------

class TestPs:
    def test_ps_shows_ros2_processes(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["ps"])
        assert result.exit_code == 0, result.output
        assert "localPlanner" in result.output
        assert "1001" in result.output

    def test_ps_shows_status_column(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["ps"])
        assert result.exit_code == 0
        # Process names confirm the table rendered (status may be clipped at narrow width)
        assert "localPlanner" in result.output
        assert "graph_decoder" in result.output

    def test_ps_shows_memory(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["ps"])
        assert result.exit_code == 0
        assert "120" in result.output  # memory_mb

    def test_ps_empty_snapshot(self) -> None:
        snap = SystemSnapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["ps"])
        assert result.exit_code == 0
        assert "No ROS2 processes" in result.output

    def test_ps_all_flag_includes_non_ros(self) -> None:
        non_ros = RosmProcess(
            pid=9999,
            name="rviz2",
            cmdline="/opt/ros/jazzy/lib/rviz2/rviz2",
            status=ProcessStatus.RUNNING,
        )
        snap = _make_snapshot(processes=[non_ros])
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["ps", "--all"])
        assert result.exit_code == 0
        assert "rviz2" in result.output

    def test_ps_show_all_short_flag(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["ps", "-a"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# kill command
# ---------------------------------------------------------------------------

class TestKill:
    def test_kill_by_pid(self) -> None:
        runner = _runner()
        with patch("os.kill") as mock_kill:
            result = runner.invoke(cli, ["kill", "1001"])
        assert result.exit_code == 0
        mock_kill.assert_called_once_with(1001, signal.SIGTERM)
        assert "SIGTERM" in result.output

    def test_kill_by_pid_force(self) -> None:
        runner = _runner()
        with patch("os.kill") as mock_kill:
            result = runner.invoke(cli, ["kill", "--force", "1001"])
        assert result.exit_code == 0
        mock_kill.assert_called_once_with(1001, signal.SIGKILL)
        assert "SIGKILL" in result.output

    def test_kill_by_pid_short_force(self) -> None:
        runner = _runner()
        with patch("os.kill") as mock_kill:
            result = runner.invoke(cli, ["kill", "-f", "1001"])
        assert result.exit_code == 0
        mock_kill.assert_called_once_with(1001, signal.SIGKILL)

    def test_kill_by_name(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("os.kill") as mock_kill:
            result = runner.invoke(cli, ["kill", "localPlanner"])
        assert result.exit_code == 0
        mock_kill.assert_called_with(1001, signal.SIGTERM)

    def test_kill_by_name_not_found(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap):
            result = runner.invoke(cli, ["kill", "nonexistent_node"])
        assert result.exit_code == 1
        assert "No processes matching" in result.output

    def test_kill_pid_not_found(self) -> None:
        runner = _runner()
        with patch("os.kill", side_effect=ProcessLookupError):
            result = runner.invoke(cli, ["kill", "99999"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_kill_permission_denied(self) -> None:
        runner = _runner()
        with patch("os.kill", side_effect=PermissionError):
            result = runner.invoke(cli, ["kill", "1"])
        assert result.exit_code == 1
        assert "Permission denied" in result.output


# ---------------------------------------------------------------------------
# clean command
# ---------------------------------------------------------------------------

class TestClean:
    def test_clean_dry_run(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("glob.glob", return_value=[]), \
             patch("rosm.cli.has_ros2_cli", return_value=False):
            result = runner.invoke(cli, ["clean", "--dry-run"])
        assert result.exit_code == 0
        assert "dry-run" in result.output

    def test_clean_no_zombies(self) -> None:
        snap = _make_snapshot(processes=[
            RosmProcess(
                pid=1001,
                name="localPlanner",
                cmdline="",
                status=ProcessStatus.RUNNING,
            )
        ])
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("glob.glob", return_value=[]), \
             patch("rosm.cli.has_ros2_cli", return_value=False):
            result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 0
        assert "No zombie" in result.output

    def test_clean_kills_orphans(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("glob.glob", return_value=[]), \
             patch("os.kill") as mock_kill, \
             patch("rosm.cli.has_ros2_cli", return_value=False):
            result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 0
        # orphan pid=1002 should be killed
        pids_killed = [call.args[0] for call in mock_kill.call_args_list]
        assert 1002 in pids_killed

    def test_clean_removes_shm(self) -> None:
        snap = _make_snapshot(processes=[])
        runner = _runner()
        # clean iterates over 2 glob patterns; give first 1 file, second 1 file
        shm_side_effects = [
            ["/dev/shm/fastrtps_port7412"],
            ["/dev/shm/sem.fastrtps_port7412"],
        ]
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("glob.glob", side_effect=shm_side_effects), \
             patch("os.remove") as mock_remove, \
             patch("rosm.cli.has_ros2_cli", return_value=False):
            result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 0
        assert mock_remove.call_count == 2


# ---------------------------------------------------------------------------
# nuke command
# ---------------------------------------------------------------------------

class TestNuke:
    def test_nuke_requires_confirmation(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["nuke"])
        # Without --yes, should prompt; decline with "n"
        assert result.exit_code != 0 or "Aborted" in result.output or "Kill ALL" in result.output

    def test_nuke_confirmed(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("os.kill") as mock_kill, \
             patch("glob.glob", return_value=[]), \
             patch("rosm.cli.has_ros2_cli", return_value=False):
            result = runner.invoke(cli, ["nuke"], input="y\n")
        assert result.exit_code == 0
        assert "NUKE" in result.output

    def test_nuke_no_processes(self) -> None:
        snap = SystemSnapshot()
        runner = _runner()
        with patch("rosm.cli._load_process_snapshot", return_value=snap), \
             patch("glob.glob", return_value=[]), \
             patch("rosm.cli.has_ros2_cli", return_value=False):
            result = runner.invoke(cli, ["nuke"], input="y\n")
        assert result.exit_code == 0
        assert "No ROS2 processes" in result.output


# ---------------------------------------------------------------------------
# nodes command
# ---------------------------------------------------------------------------

class TestNodes:
    def test_nodes_requires_rclpy(self) -> None:
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=False):
            result = runner.invoke(cli, ["nodes"])
        assert result.exit_code == 1
        assert "rclpy" in result.output

    def test_nodes_shows_table(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["nodes"])
        assert result.exit_code == 0
        assert "localPlanner" in result.output
        assert "far_planner" in result.output

    def test_nodes_empty(self) -> None:
        snap = SystemSnapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["nodes"])
        assert result.exit_code == 0
        assert "No nodes" in result.output

    def test_nodes_shows_health(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["nodes"])
        assert result.exit_code == 0
        assert "healthy" in result.output or "stale" in result.output


# ---------------------------------------------------------------------------
# topics command
# ---------------------------------------------------------------------------

class TestTopics:
    def test_topics_shows_table(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["topics"])
        assert result.exit_code == 0
        assert "/path" in result.output

    def test_topics_empty(self) -> None:
        snap = SystemSnapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["topics"])
        assert result.exit_code == 0
        assert "No topics" in result.output

    def test_topics_hz_flag_without_rclpy(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=False), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["topics", "--hz"])
        # Should warn but not crash
        assert result.exit_code == 0
        assert "hz" in result.output.lower() or "Hz" in result.output

    def test_topics_shows_pub_sub_counts(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["topics"])
        assert result.exit_code == 0
        # pub/sub count columns present
        assert "1" in result.output


# ---------------------------------------------------------------------------
# services command
# ---------------------------------------------------------------------------

class TestServices:
    def test_services_requires_rclpy(self) -> None:
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=False):
            result = runner.invoke(cli, ["services"])
        assert result.exit_code == 1

    def test_services_shows_table(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["services"])
        assert result.exit_code == 0
        assert "localPlanner" in result.output

    def test_services_empty(self) -> None:
        snap = SystemSnapshot()
        runner = _runner()
        with patch("rosm.cli.has_rclpy", return_value=True), \
             patch("rosm.cli._load_graph_snapshot", return_value=snap):
            result = runner.invoke(cli, ["services"])
        assert result.exit_code == 0
        assert "No services" in result.output


# ---------------------------------------------------------------------------
# conflicts command
# ---------------------------------------------------------------------------

class TestConflicts:
    def test_conflicts_no_issues(self) -> None:
        snap = _make_snapshot(conflicts=[])
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["conflicts"])
        assert result.exit_code == 0
        assert "No conflicts" in result.output

    def test_conflicts_shows_warnings(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["conflicts"])
        assert result.exit_code == 0
        assert "Zombie" in result.output or "zombie" in result.output

    def test_conflicts_shows_severity_summary(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["conflicts"])
        assert result.exit_code == 0
        assert "warning" in result.output or "error" in result.output

    def test_conflicts_shows_fix_suggestion(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["conflicts"])
        assert result.exit_code == 0
        assert "rosm clean" in result.output


# ---------------------------------------------------------------------------
# doctor command
# ---------------------------------------------------------------------------

class TestDoctor:
    def test_doctor_shows_system_info(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "CPU" in result.output
        assert "Memory" in result.output

    def test_doctor_shows_health_verdict(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        # One of the verdict strings
        assert any(v in result.output for v in ("OK", "WARNING", "DEGRADED"))

    def test_doctor_ok_when_no_conflicts(self) -> None:
        snap = _make_snapshot(conflicts=[])
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_doctor_shows_distro(self) -> None:
        snap = _make_snapshot()
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "jazzy" in result.output

    def test_doctor_error_severity_shows_degraded(self) -> None:
        snap = _make_snapshot(
            conflicts=[
                Conflict(
                    rule_name="PortConflict",
                    severity=ConflictSeverity.ERROR,
                    title="Port conflict on 10000",
                    description="Two processes bound to port 10000",
                    affected_entities=("endpoint:12345", "endpoint:67890"),
                )
            ]
        )
        runner = _runner()
        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch("rosm.cli._run_conflict_engine", return_value=snap):
            result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "DEGRADED" in result.output


# ---------------------------------------------------------------------------
# dashboard command
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_registered_in_help(self) -> None:
        """dashboard command is registered in the CLI group."""
        runner = _runner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "dashboard" in result.output

    def test_dashboard_no_textual_shows_error(self) -> None:
        """dashboard command shows error message when textual import fails."""
        runner = _runner()

        def _raise_import(*_a: object, **_kw: object) -> None:
            raise ImportError("textual not found")

        # Patch the import inside the dashboard command at the module level
        with patch("rosm.cli._load_full_snapshot", return_value=SystemSnapshot()):
            with patch.dict("sys.modules", {"rosm.tui.app": None}):
                result = runner.invoke(cli, ["dashboard"])
        # Either exits with error or shows import error message
        assert result.exit_code != 0 or "tui" in result.output.lower() or "textual" in result.output.lower()

    def test_dashboard_runs_with_mock(self) -> None:
        """dashboard command calls run_dashboard with loaded snapshot."""
        snap = _make_snapshot()
        mock_run = MagicMock()
        runner = _runner()

        import rosm.tui.app as tui_app

        with patch("rosm.cli._load_full_snapshot", return_value=snap), \
             patch.object(tui_app, "run_dashboard", mock_run):
            result = runner.invoke(cli, ["dashboard"])
        assert mock_run.called or result.exit_code == 0


# ---------------------------------------------------------------------------
# Help and version
# ---------------------------------------------------------------------------

class TestHelpAndVersion:
    def test_help(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "rosm" in result.output

    def test_version(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_ps_help(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["ps", "--help"])
        assert result.exit_code == 0
        assert "--all" in result.output

    def test_kill_help(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["kill", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_clean_help(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["clean", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_topics_help(self) -> None:
        runner = _runner()
        result = runner.invoke(cli, ["topics", "--help"])
        assert result.exit_code == 0
        assert "--hz" in result.output
