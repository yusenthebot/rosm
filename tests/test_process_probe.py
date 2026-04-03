"""Tests for ProcessProbe — written first (TDD)."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, call, patch

import psutil
import pytest

from rosm.models import ProcessStatus, RosmProcess
from tests.conftest import make_mock_psutil_process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ros2_proc(
    pid: int = 100,
    name: str = "talker",
    cmdline: list[str] | None = None,
    status: str = "running",
    ppid: int = 500,
) -> MagicMock:
    if cmdline is None:
        cmdline = [
            "/install/demo_nodes_py/lib/demo_nodes_py/talker",
            "--ros-args",
            "-r", "__node:=talker",
        ]
    return make_mock_psutil_process(
        pid=pid, name=name, cmdline=cmdline, status=status, ppid=ppid,
    )


def make_non_ros2_proc() -> MagicMock:
    return make_mock_psutil_process(
        pid=9999, name="bash", cmdline=["/bin/bash"], ppid=500,
    )


# ---------------------------------------------------------------------------
# _is_ros2_process
# ---------------------------------------------------------------------------

class TestIsRos2Process:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_detects_ros_args_signature(self):
        assert self.probe._is_ros2_process(["--ros-args", "-r", "__node:=foo"], "") is True

    def test_detects_ros2_run_signature(self):
        assert self.probe._is_ros2_process(["ros2", "run", "demo_nodes_py", "talker"], "") is True

    def test_detects_ros2_launch_signature(self):
        assert self.probe._is_ros2_process(["ros2", "launch", "nav2_bringup"], "") is True

    def test_detects_rviz2_signature(self):
        assert self.probe._is_ros2_process(["rviz2", "--display-config", "foo.rviz"], "") is True

    def test_detects_rqt_signature(self):
        assert self.probe._is_ros2_process(["rqt", "--standalone", "rqt_graph"], "") is True

    def test_detects_ros_tcp_endpoint_signature(self):
        assert self.probe._is_ros2_process(["ros_tcp_endpoint"], "") is True

    def test_detects_install_path(self):
        assert self.probe._is_ros2_process([], "/install/my_pkg/lib/my_pkg/my_node") is True

    def test_detects_opt_ros_path(self):
        assert self.probe._is_ros2_process([], "/opt/ros/jazzy/lib/rviz2/rviz2") is True

    def test_rejects_plain_bash(self):
        assert self.probe._is_ros2_process(["/bin/bash"], "/bin/bash") is False

    def test_rejects_empty_cmdline(self):
        assert self.probe._is_ros2_process([], "") is False

    def test_cmdline_joined_for_substring(self):
        # "ros2cli" can appear as part of a longer token
        assert self.probe._is_ros2_process(["/usr/lib/ros2cli/ros2"], "") is True


# ---------------------------------------------------------------------------
# _classify_status
# ---------------------------------------------------------------------------

class TestClassifyStatus:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_zombie_status(self):
        assert self.probe._classify_status({"status": "zombie", "ppid": 500}) == ProcessStatus.ZOMBIE

    def test_dead_status(self):
        assert self.probe._classify_status({"status": "dead", "ppid": 500}) == ProcessStatus.DEAD

    def test_orphan_when_ppid_is_1(self):
        assert self.probe._classify_status({"status": "running", "ppid": 1}) == ProcessStatus.ORPHAN

    def test_orphan_when_ppid_in_init_pids(self):
        probe = __import__("rosm.probes.process_probe", fromlist=["ProcessProbe"]).ProcessProbe()
        # INIT_PIDS always contains 1
        assert self.probe._classify_status({"status": "sleeping", "ppid": 1}) == ProcessStatus.ORPHAN

    def test_running_status(self):
        assert self.probe._classify_status({"status": "running", "ppid": 500}) == ProcessStatus.RUNNING

    def test_sleeping_status(self):
        assert self.probe._classify_status({"status": "sleeping", "ppid": 500}) == ProcessStatus.SLEEPING

    def test_unknown_status_falls_back_to_running(self):
        result = self.probe._classify_status({"status": "disk-sleep", "ppid": 500})
        assert result == ProcessStatus.RUNNING


# ---------------------------------------------------------------------------
# _extract_node_name
# ---------------------------------------------------------------------------

class TestExtractNodeName:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_extracts_node_name_with_remapping(self):
        cmdline = ["./my_node", "--ros-args", "-r", "__node:=myActualNode"]
        assert self.probe._extract_node_name(cmdline) == "myActualNode"

    def test_returns_none_when_no_ros_args(self):
        assert self.probe._extract_node_name(["./my_node"]) is None

    def test_returns_none_when_no_node_remapping(self):
        assert self.probe._extract_node_name(["./my_node", "--ros-args", "-p", "rate:=10"]) is None

    def test_node_remap_with_namespace(self):
        cmdline = ["./node", "--ros-args", "-r", "__node:=ns/nodeName"]
        assert self.probe._extract_node_name(cmdline) == "ns/nodeName"

    def test_node_remap_as_single_token(self):
        # Some processes embed as one token: --ros-args --remap __node:=foo
        cmdline = ["./node", "--ros-args", "--remap", "__node:=foo"]
        assert self.probe._extract_node_name(cmdline) == "foo"


# ---------------------------------------------------------------------------
# _extract_package
# ---------------------------------------------------------------------------

class TestExtractPackage:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_extracts_from_install_path(self):
        cmdline = ["/install/local_planner/lib/local_planner/localPlanner", "--ros-args"]
        assert self.probe._extract_package(cmdline) == "local_planner"

    def test_extracts_from_opt_ros_path(self):
        cmdline = ["/opt/ros/jazzy/lib/rviz2/rviz2"]
        assert self.probe._extract_package(cmdline) == "rviz2"

    def test_returns_none_for_no_match(self):
        cmdline = ["/usr/bin/python3", "script.py"]
        assert self.probe._extract_package(cmdline) is None

    def test_returns_none_for_empty(self):
        assert self.probe._extract_package([]) is None


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def _make_process_iter_return(self, mocks: list[MagicMock]):
        """Wrap mocks so process_iter yields them."""
        return mocks

    def test_snapshot_returns_only_ros2_processes(self):
        ros2_proc = make_ros2_proc(pid=100)
        non_ros2_proc = make_non_ros2_proc()

        with patch("psutil.process_iter", return_value=[ros2_proc, non_ros2_proc]):
            result = self.probe.snapshot()

        pids = [p.pid for p in result]
        assert 100 in pids
        assert 9999 not in pids

    def test_snapshot_builds_rosm_process(self):
        proc = make_ros2_proc(
            pid=200, name="camera_node",
            cmdline=["/install/camera_pkg/lib/camera_pkg/camera_node", "--ros-args", "-r", "__node:=camera"],
            ppid=500,
        )
        with patch("psutil.process_iter", return_value=[proc]):
            result = self.probe.snapshot()

        assert len(result) == 1
        rp = result[0]
        assert isinstance(rp, RosmProcess)
        assert rp.pid == 200
        assert rp.name == "camera_node"
        assert rp.ros2_node_name == "camera"
        assert rp.ros2_package == "camera_pkg"

    def test_snapshot_classifies_orphan(self):
        proc = make_ros2_proc(pid=300, ppid=1)
        with patch("psutil.process_iter", return_value=[proc]):
            result = self.probe.snapshot()

        assert result[0].status == ProcessStatus.ORPHAN

    def test_snapshot_classifies_zombie(self):
        proc = make_ros2_proc(pid=400, status="zombie", ppid=500)
        with patch("psutil.process_iter", return_value=[proc]):
            result = self.probe.snapshot()

        assert result[0].status == ProcessStatus.ZOMBIE

    def test_snapshot_skips_no_such_process(self):
        good_proc = make_ros2_proc(pid=500)
        bad_proc = MagicMock()
        bad_proc.info = None
        # Simulate NoSuchProcess when accessing info
        bad_proc.info = MagicMock(side_effect=psutil.NoSuchProcess(pid=999))

        # Make process_iter return both, but info on bad_proc raises
        bad_proc2 = MagicMock()
        bad_proc2.pid = 999
        # We'll test via a probe that handles exception during iteration

        # More direct: patch process_iter to raise partway
        def _iter_with_exception(attrs):
            yield good_proc
            raise psutil.NoSuchProcess(pid=999)

        with patch("psutil.process_iter", side_effect=_iter_with_exception):
            result = self.probe.snapshot()

        assert len(result) == 1
        assert result[0].pid == 500

    def test_snapshot_skips_access_denied(self):
        def _iter_raise(attrs):
            raise psutil.AccessDenied(pid=1)
            yield  # make it a generator

        with patch("psutil.process_iter", side_effect=_iter_raise):
            result = self.probe.snapshot()

        assert result == []

    def test_snapshot_empty_when_no_ros2(self):
        non_ros2 = make_non_ros2_proc()
        with patch("psutil.process_iter", return_value=[non_ros2]):
            result = self.probe.snapshot()
        assert result == []


# ---------------------------------------------------------------------------
# kill_process
# ---------------------------------------------------------------------------

class TestKillProcess:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_kill_process_sends_sigterm(self):
        mock_proc = MagicMock()
        with patch("psutil.Process", return_value=mock_proc):
            result = self.probe.kill_process(1234)

        mock_proc.terminate.assert_called_once()
        assert result is True

    def test_kill_process_force_sends_sigkill(self):
        mock_proc = MagicMock()
        with patch("psutil.Process", return_value=mock_proc):
            result = self.probe.kill_process(1234, force=True)

        mock_proc.kill.assert_called_once()
        assert result is True

    def test_kill_process_returns_false_on_no_such_process(self):
        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(pid=1234)):
            result = self.probe.kill_process(1234)

        assert result is False

    def test_kill_process_returns_false_on_access_denied(self):
        with patch("psutil.Process", side_effect=psutil.AccessDenied(pid=1234)):
            result = self.probe.kill_process(1234)

        assert result is False


# ---------------------------------------------------------------------------
# kill_by_name
# ---------------------------------------------------------------------------

class TestKillByName:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_kills_matching_processes(self):
        ros2_proc1 = make_ros2_proc(pid=100, name="talker")
        ros2_proc2 = make_ros2_proc(pid=101, name="talker")
        non_match = make_ros2_proc(pid=200, name="listener")

        with patch("psutil.process_iter", return_value=[ros2_proc1, ros2_proc2, non_match]):
            with patch.object(self.probe, "kill_process", return_value=True) as mock_kill:
                result = self.probe.kill_by_name("talker")

        assert set(result) == {100, 101}

    def test_kill_by_name_returns_empty_for_no_match(self):
        ros2_proc = make_ros2_proc(pid=100, name="listener")
        with patch("psutil.process_iter", return_value=[ros2_proc]):
            result = self.probe.kill_by_name("talker")

        assert result == []

    def test_kill_by_name_uses_pattern_matching(self):
        ros2_proc = make_ros2_proc(pid=100, name="my_talker_node")
        with patch("psutil.process_iter", return_value=[ros2_proc]):
            with patch.object(self.probe, "kill_process", return_value=True):
                result = self.probe.kill_by_name("talker")

        assert 100 in result


# ---------------------------------------------------------------------------
# kill_all_ros2
# ---------------------------------------------------------------------------

class TestKillAllRos2:
    def setup_method(self):
        from rosm.probes.process_probe import ProcessProbe
        self.probe = ProcessProbe()

    def test_kills_all_ros2_processes(self):
        procs = [make_ros2_proc(pid=i) for i in range(3)]
        with patch.object(self.probe, "snapshot", return_value=[
            RosmProcess(
                pid=i, name="node", cmdline="--ros-args", status=ProcessStatus.RUNNING
            ) for i in range(3)
        ]):
            with patch.object(self.probe, "kill_process", return_value=True):
                result = self.probe.kill_all_ros2()

        assert set(result) == {0, 1, 2}

    def test_kill_all_ros2_returns_empty_when_no_processes(self):
        with patch.object(self.probe, "snapshot", return_value=[]):
            result = self.probe.kill_all_ros2()
        assert result == []
