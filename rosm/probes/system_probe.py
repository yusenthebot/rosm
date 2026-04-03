"""SystemProbe — probe system-level ROS2 artifacts."""

from __future__ import annotations

import os
import subprocess
from typing import Set

import psutil

from rosm.models import PortBinding, ShmFile


_SHM_DIR = "/dev/shm"
_SHM_PREFIXES = ("fastrtps_", "sem.fastrtps_")


class SystemProbe:
    """Probes system-level ROS2 artifacts."""

    # ---------------------------------------------------------------------------
    # Environment accessors
    # ---------------------------------------------------------------------------

    def get_domain_id(self) -> int | None:
        """Read ROS_DOMAIN_ID from environment. Returns None if unset or invalid."""
        raw = os.environ.get("ROS_DOMAIN_ID")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def get_rmw_implementation(self) -> str:
        """Read RMW_IMPLEMENTATION from environment."""
        return os.environ.get("RMW_IMPLEMENTATION", "")

    def get_ros_distro(self) -> str:
        """Read ROS_DISTRO from environment."""
        return os.environ.get("ROS_DISTRO", "")

    # ---------------------------------------------------------------------------
    # Shared memory
    # ---------------------------------------------------------------------------

    def get_shm_files(self) -> list[ShmFile]:
        """Enumerate /dev/shm/fastrtps_* and sem.fastrtps_* files.

        Cross-references with running processes to determine orphan status.
        """
        try:
            entries = os.listdir(_SHM_DIR)
        except (FileNotFoundError, PermissionError):
            return []

        running_pids = self._get_running_pids()
        results: list[ShmFile] = []

        for entry in entries:
            if not any(entry.startswith(prefix) for prefix in _SHM_PREFIXES):
                continue

            path = os.path.join(_SHM_DIR, entry)
            try:
                stat = os.stat(path)
                size_bytes = stat.st_size
            except OSError:
                size_bytes = 0

            # Heuristic: extract a PID from the filename if present
            owner_pid: int | None = self._extract_pid_from_shm_name(entry)

            # Mark orphaned when no running process owns it
            is_orphaned: bool
            if owner_pid is not None:
                is_orphaned = owner_pid not in running_pids
            else:
                # No PID in name — treat as orphaned when no running ROS2 PIDs exist
                is_orphaned = len(running_pids) == 0

            results.append(
                ShmFile(
                    path=path,
                    size_bytes=size_bytes,
                    owner_pid=owner_pid,
                    is_orphaned=is_orphaned,
                )
            )

        return results

    def clean_shm(self, dry_run: bool = False) -> list[str]:
        """Remove orphaned SHM files.

        Returns list of paths that were (or would be) removed.
        """
        orphaned = [f for f in self.get_shm_files() if f.is_orphaned]
        removed: list[str] = []

        for shm in orphaned:
            if not dry_run:
                try:
                    os.remove(shm.path)
                    removed.append(shm.path)
                except OSError:
                    pass
            else:
                removed.append(shm.path)

        return removed

    # ---------------------------------------------------------------------------
    # Port bindings
    # ---------------------------------------------------------------------------

    def get_port_bindings(self) -> list[PortBinding]:
        """Get all UDP/TCP port bindings visible to this process."""
        try:
            connections = psutil.net_connections(kind="all")
        except psutil.AccessDenied:
            return []

        results: list[PortBinding] = []
        for conn in connections:
            try:
                port = conn.laddr.port
                proto = _socket_type_to_proto(conn.type)
                pid: int | None = conn.pid

                proc_name = ""
                if pid is not None:
                    try:
                        proc_name = psutil.Process(pid).name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        proc_name = ""

                results.append(
                    PortBinding(
                        port=port,
                        protocol=proto,
                        pid=pid,
                        process_name=proc_name,
                    )
                )
            except AttributeError:
                # Some connections lack laddr
                continue

        return results

    # ---------------------------------------------------------------------------
    # Daemon management
    # ---------------------------------------------------------------------------

    def reset_daemon(self) -> bool:
        """Stop and restart the ros2 daemon.

        Returns True if both commands succeeded.
        """
        try:
            subprocess.run(
                ["ros2", "daemon", "stop"],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["ros2", "daemon", "start"],
                capture_output=True,
                timeout=10,
            )
            return True
        except Exception:
            return False

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _get_running_pids(self) -> Set[int]:
        """Return the set of all currently running process PIDs."""
        try:
            return set(psutil.pids())
        except Exception:
            return set()

    def _extract_pid_from_shm_name(self, name: str) -> int | None:
        """Try to extract a numeric PID embedded in a SHM filename.

        Examples: fastrtps_1234_abc → 1234, sem.fastrtps_9999 → 9999
        """
        # Look for the first run of digits in the name that could be a PID
        import re
        m = re.search(r"_(\d+)", name)
        if m:
            candidate = int(m.group(1))
            # Sanity: real PIDs are > 1 and < 4 million on Linux
            if 1 < candidate < 4_000_000:
                return candidate
        return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _socket_type_to_proto(sock_type) -> str:
    """Convert socket type constant to 'tcp' or 'udp' string."""
    import socket
    try:
        if sock_type == socket.SOCK_DGRAM:
            return "udp"
        if sock_type == socket.SOCK_STREAM:
            return "tcp"
    except AttributeError:
        pass
    # Fall back to string representation
    name = getattr(sock_type, "name", str(sock_type))
    if "DGRAM" in name.upper():
        return "udp"
    return "tcp"
