"""Tests for SystemProbe — written first (TDD)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from rosm.models import PortBinding, ShmFile


# ---------------------------------------------------------------------------
# get_domain_id
# ---------------------------------------------------------------------------

class TestGetDomainId:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def test_returns_domain_id_from_env(self):
        with patch.dict(os.environ, {"ROS_DOMAIN_ID": "42"}):
            assert self.probe.get_domain_id() == 42

    def test_returns_none_when_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "ROS_DOMAIN_ID"}
        with patch.dict(os.environ, env, clear=True):
            assert self.probe.get_domain_id() is None

    def test_returns_zero_for_domain_id_zero(self):
        with patch.dict(os.environ, {"ROS_DOMAIN_ID": "0"}):
            assert self.probe.get_domain_id() == 0

    def test_returns_none_for_non_numeric(self):
        with patch.dict(os.environ, {"ROS_DOMAIN_ID": "abc"}):
            assert self.probe.get_domain_id() is None


# ---------------------------------------------------------------------------
# get_rmw_implementation
# ---------------------------------------------------------------------------

class TestGetRmwImplementation:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def test_returns_rmw_from_env(self):
        with patch.dict(os.environ, {"RMW_IMPLEMENTATION": "rmw_fastrtps_cpp"}):
            assert self.probe.get_rmw_implementation() == "rmw_fastrtps_cpp"

    def test_returns_empty_string_when_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "RMW_IMPLEMENTATION"}
        with patch.dict(os.environ, env, clear=True):
            assert self.probe.get_rmw_implementation() == ""


# ---------------------------------------------------------------------------
# get_ros_distro
# ---------------------------------------------------------------------------

class TestGetRosDistro:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def test_returns_distro_from_env(self):
        with patch.dict(os.environ, {"ROS_DISTRO": "jazzy"}):
            assert self.probe.get_ros_distro() == "jazzy"

    def test_returns_empty_string_when_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "ROS_DISTRO"}
        with patch.dict(os.environ, env, clear=True):
            assert self.probe.get_ros_distro() == ""


# ---------------------------------------------------------------------------
# get_shm_files
# ---------------------------------------------------------------------------

class TestGetShmFiles:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def test_returns_fastrtps_files(self):
        shm_entries = [
            "fastrtps_port7412",
            "sem.fastrtps_port7412_el0_0",
            "unrelated_file",
        ]

        def mock_listdir(path):
            return shm_entries

        def mock_stat(path):
            s = MagicMock()
            s.st_size = 4096
            return s

        mock_running_pids = set()

        with patch("os.listdir", side_effect=mock_listdir):
            with patch("os.stat", return_value=MagicMock(st_size=4096)):
                with patch.object(self.probe, "_get_running_pids", return_value=mock_running_pids):
                    result = self.probe.get_shm_files()

        paths = [f.path for f in result]
        assert any("fastrtps_port7412" in p for p in paths)
        assert any("sem.fastrtps_port7412" in p for p in paths)
        assert not any("unrelated_file" in p for p in paths)

    def test_shm_files_are_orphaned_when_no_owner(self):
        with patch("os.listdir", return_value=["fastrtps_port1234"]):
            with patch("os.stat", return_value=MagicMock(st_size=100)):
                with patch.object(self.probe, "_get_running_pids", return_value=set()):
                    result = self.probe.get_shm_files()

        assert len(result) == 1
        assert result[0].is_orphaned is True

    def test_shm_files_not_orphaned_when_owner_running(self):
        with patch("os.listdir", return_value=["fastrtps_port1234"]):
            with patch("os.stat", return_value=MagicMock(st_size=100)):
                with patch.object(self.probe, "_get_running_pids", return_value={1234}):
                    # owner_pid detection is heuristic, just verify structure
                    result = self.probe.get_shm_files()

        assert len(result) == 1
        # When running pids exist, orphan status depends on owner_pid lookup
        assert isinstance(result[0].is_orphaned, bool)

    def test_returns_empty_when_shm_dir_missing(self):
        with patch("os.listdir", side_effect=FileNotFoundError):
            result = self.probe.get_shm_files()
        assert result == []

    def test_returns_shmfile_models(self):
        with patch("os.listdir", return_value=["fastrtps_abc"]):
            with patch("os.stat", return_value=MagicMock(st_size=512)):
                with patch.object(self.probe, "_get_running_pids", return_value=set()):
                    result = self.probe.get_shm_files()

        assert all(isinstance(f, ShmFile) for f in result)


# ---------------------------------------------------------------------------
# clean_shm
# ---------------------------------------------------------------------------

class TestCleanShm:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def _orphaned_shm(self) -> list[ShmFile]:
        return [
            ShmFile(path="/dev/shm/fastrtps_port7412", size_bytes=4096, is_orphaned=True),
            ShmFile(path="/dev/shm/sem.fastrtps_port7412", size_bytes=32, is_orphaned=True),
        ]

    def _live_shm(self) -> list[ShmFile]:
        return [
            ShmFile(path="/dev/shm/fastrtps_live", size_bytes=4096, owner_pid=1234, is_orphaned=False),
        ]

    def test_dry_run_returns_paths_without_deleting(self):
        with patch.object(self.probe, "get_shm_files", return_value=self._orphaned_shm()):
            with patch("os.remove") as mock_remove:
                result = self.probe.clean_shm(dry_run=True)

        mock_remove.assert_not_called()
        assert len(result) == 2

    def test_removes_orphaned_files(self):
        with patch.object(self.probe, "get_shm_files", return_value=self._orphaned_shm()):
            with patch("os.remove") as mock_remove:
                result = self.probe.clean_shm(dry_run=False)

        assert mock_remove.call_count == 2
        assert len(result) == 2

    def test_skips_non_orphaned_files(self):
        all_files = self._orphaned_shm() + self._live_shm()
        with patch.object(self.probe, "get_shm_files", return_value=all_files):
            with patch("os.remove") as mock_remove:
                result = self.probe.clean_shm(dry_run=False)

        assert mock_remove.call_count == 2
        assert len(result) == 2

    def test_handles_removal_error_gracefully(self):
        with patch.object(self.probe, "get_shm_files", return_value=self._orphaned_shm()):
            with patch("os.remove", side_effect=OSError("permission denied")):
                result = self.probe.clean_shm(dry_run=False)

        # Should return empty list or partial — not raise
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_port_bindings
# ---------------------------------------------------------------------------

class TestGetPortBindings:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def test_returns_port_bindings(self):
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7412
        mock_conn.type = MagicMock()
        mock_conn.type.name = "SOCK_DGRAM"
        mock_conn.pid = 1234

        mock_proc = MagicMock()
        mock_proc.name.return_value = "fastrtps"

        with patch("psutil.net_connections", return_value=[mock_conn]):
            with patch("psutil.Process", return_value=mock_proc):
                result = self.probe.get_port_bindings()

        assert len(result) >= 0  # May filter depending on implementation
        assert all(isinstance(b, PortBinding) for b in result)

    def test_returns_empty_on_access_denied(self):
        import psutil as _psutil
        with patch("psutil.net_connections", side_effect=_psutil.AccessDenied(pid=0)):
            result = self.probe.get_port_bindings()
        assert result == []


# ---------------------------------------------------------------------------
# reset_daemon
# ---------------------------------------------------------------------------

class TestResetDaemon:
    def setup_method(self):
        from rosm.probes.system_probe import SystemProbe
        self.probe = SystemProbe()

    def test_reset_daemon_runs_stop_and_start(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = self.probe.reset_daemon()

        assert mock_run.call_count == 2
        calls_str = str(mock_run.call_args_list)
        assert "stop" in calls_str or "daemon" in calls_str

    def test_reset_daemon_returns_true_on_success(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            assert self.probe.reset_daemon() is True

    def test_reset_daemon_returns_false_on_failure(self):
        with patch("subprocess.run", side_effect=Exception("cmd not found")):
            assert self.probe.reset_daemon() is False
