"""Shared fixtures for rosm tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rosm.models import (
    Conflict,
    ConflictSeverity,
    EndpointInfo,
    NodeHealth,
    PortBinding,
    ProcessStatus,
    QoSProfile,
    RosmNode,
    RosmProcess,
    RosmService,
    RosmTopic,
    ShmFile,
    SystemSnapshot,
)


# ---------------------------------------------------------------------------
# Process fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def zombie_process() -> RosmProcess:
    return RosmProcess(
        pid=12345,
        name="graph_decoder",
        cmdline="/install/graph_decoder/lib/graph_decoder/graph_decoder --ros-args",
        status=ProcessStatus.ORPHAN,
        cpu_percent=0.1,
        memory_mb=32.0,
        parent_pid=1,
        parent_name="systemd",
        create_time=datetime(2026, 4, 2, 14, 0),
        ros2_node_name="/graph_decoder",
        ros2_package="graph_decoder",
    )


@pytest.fixture
def healthy_process() -> RosmProcess:
    return RosmProcess(
        pid=54321,
        name="localPlanner",
        cmdline="/install/local_planner/lib/local_planner/localPlanner --ros-args -r __node:=localPlanner",
        status=ProcessStatus.RUNNING,
        cpu_percent=8.5,
        memory_mb=120.0,
        parent_pid=54000,
        parent_name="ros2-launch",
        create_time=datetime(2026, 4, 3, 10, 0),
        ros2_node_name="/localPlanner",
        ros2_package="local_planner",
    )


@pytest.fixture
def sample_processes(zombie_process, healthy_process) -> list[RosmProcess]:
    return [
        zombie_process,
        healthy_process,
        RosmProcess(
            pid=99999,
            name="rviz2",
            cmdline="/opt/ros/jazzy/lib/rviz2/rviz2",
            status=ProcessStatus.RUNNING,
            cpu_percent=5.0,
            memory_mb=400.0,
            parent_pid=1,
            parent_name="systemd",
            create_time=datetime(2026, 4, 3, 10, 0),
        ),
    ]


# ---------------------------------------------------------------------------
# Node fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def healthy_node() -> RosmNode:
    return RosmNode(
        name="localPlanner",
        namespace="/",
        full_name="/localPlanner",
        health=NodeHealth.HEALTHY,
        pid=54321,
        published_topics=("/path", "/goal_reached", "/free_paths"),
        subscribed_topics=("/terrain_map", "/way_point", "/registered_scan"),
    )


@pytest.fixture
def stale_node() -> RosmNode:
    return RosmNode(
        name="far_planner",
        namespace="/",
        full_name="/far_planner",
        health=NodeHealth.STALE,
        pid=55555,
        published_topics=("/way_point",),
        subscribed_topics=("/odom_world", "/scan_cloud"),
    )


@pytest.fixture
def sample_nodes(healthy_node, stale_node) -> list[RosmNode]:
    return [
        healthy_node,
        stale_node,
        RosmNode(
            name="localPlanner",
            namespace="/sim",
            full_name="/sim/localPlanner",
            health=NodeHealth.HEALTHY,
            pid=66666,
        ),
    ]


# ---------------------------------------------------------------------------
# Topic fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def topic_with_qos_mismatch() -> RosmTopic:
    return RosmTopic(
        name="/terrain_map",
        msg_type="sensor_msgs/msg/PointCloud2",
        publishers=(
            EndpointInfo(
                node_name="terrainAnalysis",
                node_namespace="/",
                qos=QoSProfile(reliability="BEST_EFFORT", durability="VOLATILE"),
            ),
        ),
        subscribers=(
            EndpointInfo(
                node_name="localPlanner",
                node_namespace="/",
                qos=QoSProfile(reliability="RELIABLE", durability="TRANSIENT_LOCAL"),
            ),
        ),
        hz=10.0,
    )


@pytest.fixture
def orphaned_topic() -> RosmTopic:
    return RosmTopic(
        name="/dead_topic",
        msg_type="std_msgs/msg/String",
        publishers=(
            EndpointInfo(node_name="ghost_node", node_namespace="/"),
        ),
        subscribers=(),
    )


@pytest.fixture
def multi_pub_topic() -> RosmTopic:
    return RosmTopic(
        name="/cmd_vel",
        msg_type="geometry_msgs/msg/TwistStamped",
        publishers=(
            EndpointInfo(node_name="pathFollower", node_namespace="/"),
            EndpointInfo(node_name="teleop_node", node_namespace="/"),
        ),
        subscribers=(
            EndpointInfo(node_name="vehicle_simulator", node_namespace="/"),
        ),
        hz=50.0,
    )


@pytest.fixture
def sample_topics(topic_with_qos_mismatch, orphaned_topic, multi_pub_topic) -> list[RosmTopic]:
    return [
        topic_with_qos_mismatch,
        orphaned_topic,
        multi_pub_topic,
        RosmTopic(
            name="/rosout",
            msg_type="rcl_interfaces/msg/Log",
            publishers=(EndpointInfo(node_name="localPlanner", node_namespace="/"),),
            subscribers=(EndpointInfo(node_name="rosout", node_namespace="/"),),
        ),
    ]


# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orphaned_shm_files() -> list[ShmFile]:
    return [
        ShmFile(path="/dev/shm/fastrtps_port7412", size_bytes=4096, owner_pid=None, is_orphaned=True),
        ShmFile(path="/dev/shm/sem.fastrtps_port7412", size_bytes=32, owner_pid=None, is_orphaned=True),
    ]


@pytest.fixture
def port_conflict_bindings() -> list[PortBinding]:
    return [
        PortBinding(port=10000, protocol="tcp", pid=12345, process_name="endpoint"),
        PortBinding(port=10000, protocol="tcp", pid=67890, process_name="endpoint"),
    ]


# ---------------------------------------------------------------------------
# Snapshot fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_snapshot(
    sample_processes,
    sample_nodes,
    sample_topics,
    orphaned_shm_files,
    port_conflict_bindings,
) -> SystemSnapshot:
    return SystemSnapshot(
        domain_id=0,
        rmw_implementation="rmw_fastrtps_cpp",
        ros_distro="jazzy",
        processes=sample_processes,
        nodes=sample_nodes,
        topics=sample_topics,
        shm_files=orphaned_shm_files,
        port_bindings=port_conflict_bindings,
    )


@pytest.fixture
def empty_snapshot() -> SystemSnapshot:
    return SystemSnapshot()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def make_mock_psutil_process(
    pid: int,
    name: str,
    cmdline: list[str],
    status: str = "running",
    ppid: int = 1,
    cpu_percent: float = 0.0,
    memory_mb: float = 0.0,
    create_time: float = 1743700800.0,
) -> MagicMock:
    """Create a mock psutil.Process with given attributes."""
    proc = MagicMock()
    proc.pid = pid
    proc.info = {
        "pid": pid,
        "name": name,
        "cmdline": cmdline,
        "status": status,
        "ppid": ppid,
        "cpu_percent": cpu_percent,
        "memory_info": MagicMock(rss=int(memory_mb * 1024 * 1024)),
        "create_time": create_time,
    }
    proc.name.return_value = name
    proc.cmdline.return_value = cmdline
    proc.status.return_value = status
    proc.ppid.return_value = ppid
    proc.cpu_percent.return_value = cpu_percent
    proc.memory_info.return_value = MagicMock(rss=int(memory_mb * 1024 * 1024))
    proc.create_time.return_value = create_time
    proc.parent.return_value = MagicMock(name=MagicMock(return_value="systemd"))
    proc.children.return_value = []
    return proc
