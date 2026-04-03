"""ProcessProbe — detect and classify ROS2 processes via psutil."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterator

import psutil

from rosm.models import ProcessStatus, RosmProcess


class ProcessProbe:
    """Detects and classifies ROS2-related processes via psutil."""

    ROS2_SIGNATURES: tuple[str, ...] = (
        "--ros-args",
        "ros2 run",
        "ros2 launch",
        "ros2cli",
        "rviz2",
        "rqt",
        "ros_tcp_endpoint",
    )

    ROS2_PATH_PATTERNS: tuple[str, ...] = (
        "/install/",
        "/opt/ros/",
    )

    # systemd / init PIDs that indicate an orphaned process
    INIT_PIDS: frozenset[int] = frozenset({1})
    # Parent names that indicate an orphaned process (user-session systemd, init)
    INIT_NAMES: frozenset[str] = frozenset({"systemd", "init"})

    _PROC_ITER_ATTRS = [
        "pid", "name", "cmdline", "status", "ppid",
        "cpu_percent", "memory_info", "create_time",
    ]

    # Pattern: /install/<pkg>/lib/... or /opt/ros/<distro>/lib/<pkg>/...
    _INSTALL_PKG_RE = re.compile(r"/install/([^/]+)/")
    _OPT_ROS_PKG_RE = re.compile(r"/opt/ros/[^/]+/lib/([^/]+)/")

    # --ros-args -r __node:=NAME  or  --ros-args --remap __node:=NAME
    _NODE_REMAP_RE = re.compile(r"__node:=(.+)")

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def snapshot(self) -> list[RosmProcess]:
        """Scan all processes and return ROS2-related ones."""
        results: list[RosmProcess] = []

        try:
            for proc in psutil.process_iter(attrs=self._PROC_ITER_ATTRS):
                try:
                    info = proc.info
                    cmdline: list[str] = info.get("cmdline") or []
                    exe_path: str = cmdline[0] if cmdline else ""

                    if not self._is_ros2_process(cmdline, exe_path):
                        continue

                    results.append(self._build_rosm_process(proc, info, cmdline))

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return results

    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process by PID.

        Sends SIGTERM by default; SIGKILL when force=True.
        Returns True on success, False if process not found or access denied.
        """
        try:
            proc = psutil.Process(pid)
            if force:
                proc.kill()
            else:
                proc.terminate()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def kill_by_name(self, pattern: str, force: bool = False) -> list[int]:
        """Kill all processes whose name contains *pattern*.

        Returns list of killed PIDs.
        """
        killed: list[int] = []
        try:
            for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
                try:
                    name: str = proc.info.get("name") or ""
                    if pattern.lower() in name.lower():
                        if self.kill_process(proc.info["pid"], force=force):
                            killed.append(proc.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return killed

    def kill_all_ros2(self) -> list[int]:
        """Kill all detected ROS2 processes. Returns killed PIDs."""
        procs = self.snapshot()
        killed: list[int] = []
        for rp in procs:
            if self.kill_process(rp.pid):
                killed.append(rp.pid)
        return killed

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _is_ros2_process(self, cmdline: list[str], exe_path: str) -> bool:
        """Return True if this looks like a ROS2 process."""
        joined = " ".join(cmdline)

        # Check signatures against joined cmdline
        for sig in self.ROS2_SIGNATURES:
            if sig in joined:
                return True

        # Check path patterns against each token and exe_path
        candidates = cmdline + ([exe_path] if exe_path else [])
        for token in candidates:
            for pattern in self.ROS2_PATH_PATTERNS:
                if pattern in token:
                    return True

        return False

    def _classify_status(self, proc_info: dict, parent_name: str = "") -> ProcessStatus:
        """Map psutil status string + ppid/parent name to ProcessStatus."""
        raw_status: str = proc_info.get("status", "")
        ppid: int = proc_info.get("ppid", 0) or 0

        if raw_status == "zombie":
            return ProcessStatus.ZOMBIE
        if raw_status == "dead":
            return ProcessStatus.DEAD
        # Orphan: parent is PID 1, or parent is any systemd instance (including user session)
        if ppid in self.INIT_PIDS or parent_name.lower() in self.INIT_NAMES:
            return ProcessStatus.ORPHAN
        if raw_status == "sleeping":
            return ProcessStatus.SLEEPING
        return ProcessStatus.RUNNING

    def _extract_node_name(self, cmdline: list[str]) -> str | None:
        """Extract ROS2 node name from --ros-args remapping tokens."""
        for token in cmdline:
            m = self._NODE_REMAP_RE.search(token)
            if m:
                return m.group(1)
        return None

    def _extract_package(self, cmdline: list[str]) -> str | None:
        """Extract ROS2 package name from install or opt/ros path tokens."""
        for token in cmdline:
            m = self._INSTALL_PKG_RE.search(token)
            if m:
                return m.group(1)
            m = self._OPT_ROS_PKG_RE.search(token)
            if m:
                return m.group(1)
        return None

    def _get_parent_name(self, proc: psutil.Process) -> str:
        """Safely retrieve the parent process name."""
        try:
            parent = proc.parent()
            if parent is None:
                return ""
            name = parent.name()
            if not isinstance(name, str):
                return ""
            return name
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return ""

    def _get_children_pids(self, proc: psutil.Process) -> tuple[int, ...]:
        """Safely retrieve child PIDs."""
        try:
            return tuple(c.pid for c in proc.children())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return ()

    def _build_rosm_process(
        self,
        proc: psutil.Process,
        info: dict,
        cmdline: list[str],
    ) -> RosmProcess:
        """Construct a RosmProcess from psutil data."""
        ppid: int | None = info.get("ppid")
        parent_name = self._get_parent_name(proc)
        status = self._classify_status(info, parent_name)
        memory_info = info.get("memory_info")
        memory_mb: float = (memory_info.rss / (1024 * 1024)) if memory_info else 0.0
        create_ts: float | None = info.get("create_time")
        create_time: datetime | None = (
            datetime.fromtimestamp(create_ts) if create_ts else None
        )

        node_name = self._extract_node_name(cmdline)
        package = self._extract_package(cmdline)

        # Detect launch parent: process that itself contains "launch" in name/cmdline
        joined = " ".join(cmdline)
        is_launch_parent = "ros2 launch" in joined or "launch" in (info.get("name") or "")

        return RosmProcess(
            pid=info["pid"],
            name=info.get("name") or "",
            cmdline=" ".join(cmdline),
            status=status,
            cpu_percent=float(info.get("cpu_percent") or 0.0),
            memory_mb=memory_mb,
            parent_pid=ppid,
            parent_name=parent_name,
            create_time=create_time,
            ros2_node_name=node_name,
            ros2_package=package,
            is_launch_parent=is_launch_parent,
            children_pids=self._get_children_pids(proc),
        )
