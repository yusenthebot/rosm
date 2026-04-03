"""Tests for kill/clean/nuke actions — written first (TDD)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rosm.models import ProcessStatus, RosmProcess, ShmFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rosm_proc(pid: int, status: ProcessStatus = ProcessStatus.RUNNING) -> RosmProcess:
    return RosmProcess(
        pid=pid,
        name=f"node_{pid}",
        cmdline="--ros-args",
        status=status,
    )


# ---------------------------------------------------------------------------
# kill_target (actions/kill.py)
# ---------------------------------------------------------------------------

class TestKillTarget:
    def test_kill_target_by_pid_numeric_string(self):
        from rosm.actions.kill import kill_target

        with patch("rosm.actions.kill.ProcessProbe") as MockProbe:
            instance = MockProbe.return_value
            instance.kill_process.return_value = True
            result = kill_target("1234")

        instance.kill_process.assert_called_once_with(1234, force=False)
        assert result == [1234]

    def test_kill_target_by_pid_returns_empty_when_kill_fails(self):
        from rosm.actions.kill import kill_target

        with patch("rosm.actions.kill.ProcessProbe") as MockProbe:
            instance = MockProbe.return_value
            instance.kill_process.return_value = False
            result = kill_target("9999")

        assert result == []

    def test_kill_target_by_name_pattern(self):
        from rosm.actions.kill import kill_target

        with patch("rosm.actions.kill.ProcessProbe") as MockProbe:
            instance = MockProbe.return_value
            instance.kill_by_name.return_value = [100, 101]
            result = kill_target("talker")

        instance.kill_by_name.assert_called_once_with("talker", force=False)
        assert result == [100, 101]

    def test_kill_target_with_force_flag(self):
        from rosm.actions.kill import kill_target

        with patch("rosm.actions.kill.ProcessProbe") as MockProbe:
            instance = MockProbe.return_value
            instance.kill_process.return_value = True
            kill_target("5678", force=True)

        instance.kill_process.assert_called_once_with(5678, force=True)

    def test_kill_target_name_with_force(self):
        from rosm.actions.kill import kill_target

        with patch("rosm.actions.kill.ProcessProbe") as MockProbe:
            instance = MockProbe.return_value
            instance.kill_by_name.return_value = [42]
            result = kill_target("camera_node", force=True)

        instance.kill_by_name.assert_called_once_with("camera_node", force=True)
        assert result == [42]


# ---------------------------------------------------------------------------
# clean_system (actions/clean.py)
# ---------------------------------------------------------------------------

class TestCleanSystem:
    def test_clean_system_returns_clean_result(self):
        from rosm.actions.clean import clean_system
        from rosm.models import CleanResult

        with patch("rosm.actions.clean.ProcessProbe") as MockProbe:
            with patch("rosm.actions.clean.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.snapshot.return_value = [
                    _make_rosm_proc(1, ProcessStatus.ORPHAN),
                    _make_rosm_proc(2, ProcessStatus.ZOMBIE),
                ]
                proc_instance.kill_process.return_value = True
                sys_instance.clean_shm.return_value = ["/dev/shm/fastrtps_abc"]
                sys_instance.reset_daemon.return_value = True

                result = clean_system()

        assert isinstance(result, CleanResult)

    def test_clean_system_kills_zombies_and_orphans(self):
        from rosm.actions.clean import clean_system

        with patch("rosm.actions.clean.ProcessProbe") as MockProbe:
            with patch("rosm.actions.clean.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.snapshot.return_value = [
                    _make_rosm_proc(10, ProcessStatus.ORPHAN),
                    _make_rosm_proc(20, ProcessStatus.ZOMBIE),
                    _make_rosm_proc(30, ProcessStatus.RUNNING),  # should NOT be killed
                ]
                proc_instance.kill_process.return_value = True
                sys_instance.clean_shm.return_value = []
                sys_instance.reset_daemon.return_value = True

                result = clean_system()

        killed_pids = {c.args[0] for c in proc_instance.kill_process.call_args_list}
        assert 10 in killed_pids
        assert 20 in killed_pids
        assert 30 not in killed_pids

    def test_clean_system_dry_run_does_not_kill(self):
        from rosm.actions.clean import clean_system

        with patch("rosm.actions.clean.ProcessProbe") as MockProbe:
            with patch("rosm.actions.clean.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.snapshot.return_value = [
                    _make_rosm_proc(10, ProcessStatus.ORPHAN),
                ]
                sys_instance.clean_shm.return_value = []
                sys_instance.reset_daemon.return_value = True

                result = clean_system(dry_run=True)

        proc_instance.kill_process.assert_not_called()

    def test_clean_system_dry_run_cleans_shm_dry(self):
        from rosm.actions.clean import clean_system

        with patch("rosm.actions.clean.ProcessProbe") as MockProbe:
            with patch("rosm.actions.clean.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.snapshot.return_value = []
                sys_instance.clean_shm.return_value = ["/dev/shm/fastrtps_x"]
                sys_instance.reset_daemon.return_value = True

                clean_system(dry_run=True)

        sys_instance.clean_shm.assert_called_once_with(dry_run=True)

    def test_clean_result_has_killed_pids_and_shm(self):
        from rosm.actions.clean import clean_system

        with patch("rosm.actions.clean.ProcessProbe") as MockProbe:
            with patch("rosm.actions.clean.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.snapshot.return_value = [
                    _make_rosm_proc(10, ProcessStatus.ORPHAN),
                ]
                proc_instance.kill_process.return_value = True
                sys_instance.clean_shm.return_value = ["/dev/shm/fastrtps_abc"]
                sys_instance.reset_daemon.return_value = True

                result = clean_system()

        assert 10 in result.killed_pids
        assert "/dev/shm/fastrtps_abc" in result.shm_removed


# ---------------------------------------------------------------------------
# nuke_all (actions/nuke.py)
# ---------------------------------------------------------------------------

class TestNukeAll:
    def test_nuke_returns_nuke_result(self):
        from rosm.actions.nuke import nuke_all
        from rosm.models import NukeResult

        with patch("rosm.actions.nuke.ProcessProbe") as MockProbe:
            with patch("rosm.actions.nuke.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.kill_all_ros2.return_value = [100, 200, 300]
                sys_instance.clean_shm.return_value = ["/dev/shm/fastrtps_a"]
                sys_instance.reset_daemon.return_value = True

                result = nuke_all()

        assert isinstance(result, NukeResult)

    def test_nuke_kills_all_ros2(self):
        from rosm.actions.nuke import nuke_all

        with patch("rosm.actions.nuke.ProcessProbe") as MockProbe:
            with patch("rosm.actions.nuke.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.kill_all_ros2.return_value = [1, 2, 3]
                sys_instance.clean_shm.return_value = []
                sys_instance.reset_daemon.return_value = True

                result = nuke_all()

        proc_instance.kill_all_ros2.assert_called_once()
        assert set(result.killed_pids) == {1, 2, 3}

    def test_nuke_cleans_shm(self):
        from rosm.actions.nuke import nuke_all

        with patch("rosm.actions.nuke.ProcessProbe") as MockProbe:
            with patch("rosm.actions.nuke.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.kill_all_ros2.return_value = []
                sys_instance.clean_shm.return_value = ["/dev/shm/fastrtps_1", "/dev/shm/fastrtps_2"]
                sys_instance.reset_daemon.return_value = True

                result = nuke_all()

        sys_instance.clean_shm.assert_called_once_with(dry_run=False)
        assert len(result.shm_removed) == 2

    def test_nuke_resets_daemon(self):
        from rosm.actions.nuke import nuke_all

        with patch("rosm.actions.nuke.ProcessProbe") as MockProbe:
            with patch("rosm.actions.nuke.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.kill_all_ros2.return_value = []
                sys_instance.clean_shm.return_value = []
                sys_instance.reset_daemon.return_value = True

                result = nuke_all()

        sys_instance.reset_daemon.assert_called_once()
        assert result.daemon_restarted is True

    def test_nuke_result_on_empty_system(self):
        from rosm.actions.nuke import nuke_all

        with patch("rosm.actions.nuke.ProcessProbe") as MockProbe:
            with patch("rosm.actions.nuke.SystemProbe") as MockSysProbe:
                proc_instance = MockProbe.return_value
                sys_instance = MockSysProbe.return_value

                proc_instance.kill_all_ros2.return_value = []
                sys_instance.clean_shm.return_value = []
                sys_instance.reset_daemon.return_value = False

                result = nuke_all()

        assert result.killed_pids == []
        assert result.shm_removed == []
        assert result.daemon_restarted is False
