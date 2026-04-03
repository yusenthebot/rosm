"""Pydantic v2 data models for rosm."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ProcessStatus(str, Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    ZOMBIE = "zombie"
    DEAD = "dead"
    ORPHAN = "orphan"


class RosmProcess(BaseModel, frozen=True):
    """OS-level process with ROS2 metadata."""

    pid: int
    name: str
    cmdline: str
    status: ProcessStatus
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    parent_pid: int | None = None
    parent_name: str = ""
    create_time: datetime | None = None
    ros2_node_name: str | None = None
    ros2_package: str | None = None
    is_launch_parent: bool = False
    children_pids: tuple[int, ...] = ()


class QoSProfile(BaseModel, frozen=True):
    """Simplified QoS profile for display."""

    reliability: str = "UNKNOWN"
    durability: str = "UNKNOWN"
    history: str = "UNKNOWN"
    depth: int = 0
    lifespan_ns: int = 0
    deadline_ns: int = 0
    liveliness: str = "AUTOMATIC"


class EndpointInfo(BaseModel, frozen=True):
    """A publisher or subscriber endpoint on a topic."""

    node_name: str
    node_namespace: str
    qos: QoSProfile = Field(default_factory=QoSProfile)
    gid: str = ""


class NodeHealth(str, Enum):
    HEALTHY = "healthy"
    STALE = "stale"
    UNKNOWN = "unknown"
    ZOMBIE = "zombie"


class RosmNode(BaseModel, frozen=True):
    """A ROS2 node with health and connectivity info."""

    name: str
    namespace: str
    full_name: str
    health: NodeHealth = NodeHealth.UNKNOWN
    pid: int | None = None
    published_topics: tuple[str, ...] = ()
    subscribed_topics: tuple[str, ...] = ()
    services: tuple[str, ...] = ()


class RosmTopic(BaseModel, frozen=True):
    """A ROS2 topic with full introspection data."""

    name: str
    msg_type: str
    publishers: tuple[EndpointInfo, ...] = ()
    subscribers: tuple[EndpointInfo, ...] = ()
    hz: float | None = None
    bandwidth_bps: float | None = None

    @property
    def pub_count(self) -> int:
        return len(self.publishers)

    @property
    def sub_count(self) -> int:
        return len(self.subscribers)


class RosmService(BaseModel, frozen=True):
    """A ROS2 service."""

    name: str
    service_type: str
    node_name: str
    node_namespace: str


class ConflictSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Conflict(BaseModel, frozen=True):
    """A detected conflict or issue."""

    rule_name: str
    severity: ConflictSeverity
    title: str
    description: str
    affected_entities: tuple[str, ...] = ()
    suggested_fix: str = ""


class ShmFile(BaseModel, frozen=True):
    """A shared memory file in /dev/shm."""

    path: str
    size_bytes: int = 0
    owner_pid: int | None = None
    is_orphaned: bool = False


class PortBinding(BaseModel, frozen=True):
    """A port binding by a ROS2 process."""

    port: int
    protocol: str = "udp"
    pid: int | None = None
    process_name: str = ""


class SystemSnapshot(BaseModel):
    """Complete system state at a point in time."""

    timestamp: datetime = Field(default_factory=datetime.now)
    domain_id: int | None = None
    rmw_implementation: str = ""
    ros_distro: str = ""
    processes: list[RosmProcess] = Field(default_factory=list)
    nodes: list[RosmNode] = Field(default_factory=list)
    topics: list[RosmTopic] = Field(default_factory=list)
    services: list[RosmService] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    shm_files: list[ShmFile] = Field(default_factory=list)
    port_bindings: list[PortBinding] = Field(default_factory=list)


class CleanResult(BaseModel, frozen=True):
    """Result of a clean_system operation."""

    killed_pids: list[int] = Field(default_factory=list)
    shm_removed: list[str] = Field(default_factory=list)
    daemon_restarted: bool = False
    dry_run: bool = False


class NukeResult(BaseModel, frozen=True):
    """Result of a nuke_all operation."""

    killed_pids: list[int] = Field(default_factory=list)
    shm_removed: list[str] = Field(default_factory=list)
    daemon_restarted: bool = False
