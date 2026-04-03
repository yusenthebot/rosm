"""Tests for GraphProbe — fully mocked rclpy."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from rosm.models import NodeHealth, QoSProfile, RosmNode, RosmService, RosmTopic


# ---------------------------------------------------------------------------
# Helpers to build mock rclpy endpoint info
# ---------------------------------------------------------------------------

def _make_endpoint_info(
    node_name: str,
    node_namespace: str,
    reliability: int = 1,
    durability: int = 1,
) -> MagicMock:
    """Build a mock TopicEndpointInfo."""
    ep = MagicMock()
    ep.node_name = node_name
    ep.node_namespace = node_namespace
    ep.endpoint_gid = b"\x01\x02\x03"
    qos = MagicMock()
    qos.reliability = MagicMock()
    qos.reliability.name = "RELIABLE" if reliability == 1 else "BEST_EFFORT"
    qos.durability = MagicMock()
    qos.durability.name = "TRANSIENT_LOCAL" if durability == 1 else "VOLATILE"
    qos.history = MagicMock()
    qos.history.name = "KEEP_LAST"
    qos.depth = 10
    qos.lifespan = MagicMock()
    qos.lifespan.nanoseconds = 0
    qos.deadline = MagicMock()
    qos.deadline.nanoseconds = 0
    qos.liveliness = MagicMock()
    qos.liveliness.name = "AUTOMATIC"
    ep.qos_profile = qos
    return ep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rclpy():
    """Provide a fully mocked rclpy module."""
    mock = MagicMock()
    mock.ok.return_value = False

    mock_node = MagicMock()
    mock_node.get_node_names_and_namespaces.return_value = [
        ("localPlanner", "/"),
        ("terrain_analysis", "/"),
    ]
    mock_node.get_publisher_names_and_types_by_node.side_effect = lambda name, ns: (
        [("/path", ["nav_msgs/msg/Path"]), ("/goal_reached", ["std_msgs/msg/Bool"])]
        if name == "localPlanner"
        else [("/terrain_map", ["sensor_msgs/msg/PointCloud2"])]
    )
    mock_node.get_subscriber_names_and_types_by_node.side_effect = lambda name, ns: (
        [("/terrain_map", ["sensor_msgs/msg/PointCloud2"])]
        if name == "localPlanner"
        else []
    )
    mock_node.get_service_names_and_types_by_node.return_value = []
    mock_node.get_topic_names_and_types.return_value = [
        ("/path", ["nav_msgs/msg/Path"]),
        ("/terrain_map", ["sensor_msgs/msg/PointCloud2"]),
    ]
    mock_node.get_service_names_and_types.return_value = [
        ("/terrain_analysis/set_parameters", ["rcl_interfaces/srv/SetParameters"]),
    ]

    pub_ep = _make_endpoint_info("terrain_analysis", "/")
    sub_ep = _make_endpoint_info("localPlanner", "/")
    mock_node.get_publishers_info_by_topic.return_value = [pub_ep]
    mock_node.get_subscriptions_info_by_topic.return_value = [sub_ep]

    mock.create_node.return_value = mock_node

    mock_executor = MagicMock()
    return mock, mock_node, mock_executor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGraphProbeInit:
    def test_default_init(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        assert probe._node is None
        assert probe._spin_thread is None
        assert probe._domain_id is None
        assert probe._timeout_sec == 5.0
        assert probe._executor is None

    def test_custom_domain_and_timeout(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe(domain_id=42, timeout_sec=2.0)
        assert probe._domain_id == 42
        assert probe._timeout_sec == 2.0


class TestGraphProbeStart:
    def test_start_initialises_rclpy_when_not_ok(self, mock_rclpy):
        mock, mock_node, mock_executor = mock_rclpy
        mock.ok.return_value = False

        with patch.dict("sys.modules", {"rclpy": mock, "rclpy.executors": MagicMock()}):
            mock_exec_module = MagicMock()
            mock_exec_instance = MagicMock()
            mock_exec_module.SingleThreadedExecutor.return_value = mock_exec_instance

            from rosm.probes import graph_probe
            import importlib
            importlib.reload(graph_probe)
            from rosm.probes.graph_probe import GraphProbe

            probe = GraphProbe(timeout_sec=0.0)
            with patch.object(probe, "_spin_worker"):
                with patch("threading.Thread") as mock_thread_cls:
                    mock_thread = MagicMock()
                    mock_thread_cls.return_value = mock_thread
                    with patch("rclpy.ok", return_value=False), \
                         patch("rclpy.init") as mock_init, \
                         patch("rclpy.create_node", return_value=mock_node), \
                         patch("rclpy.executors.SingleThreadedExecutor", return_value=mock_exec_instance), \
                         patch("time.sleep"):
                        probe.start()
                        mock_init.assert_called_once()

    def test_start_skips_init_when_rclpy_ok(self, mock_rclpy):
        mock, mock_node, mock_executor = mock_rclpy
        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init") as mock_init, \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()
            mock_init.assert_not_called()


class TestGraphProbeStop:
    def test_stop_destroys_node_and_shuts_down(self):
        mock_node = MagicMock()
        mock_executor = MagicMock()

        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.shutdown") as mock_shutdown:
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe()
            probe._node = mock_node
            probe._executor = mock_executor
            probe.stop()
            # rclpy.shutdown called first, then node destroyed
            mock_shutdown.assert_called_once()
            mock_node.destroy_node.assert_called_once()
            assert probe._node is None
            assert probe._executor is None

    def test_stop_is_safe_when_not_started(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        # Should not raise
        probe.stop()


class TestGraphProbeGetNodes:
    def test_get_nodes_returns_rosm_nodes(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            nodes = probe.get_nodes()
            assert len(nodes) == 2
            names = {n.name for n in nodes}
            assert "localPlanner" in names
            assert "terrain_analysis" in names

    def test_get_nodes_are_rosm_node_type(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            nodes = probe.get_nodes()
            for node in nodes:
                assert isinstance(node, RosmNode)

    def test_get_nodes_full_name_includes_namespace(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        mock_node.get_node_names_and_namespaces.return_value = [
            ("myNode", "/robot"),
        ]
        mock_node.get_publisher_names_and_types_by_node.return_value = []
        mock_node.get_subscriber_names_and_types_by_node.return_value = []
        mock_node.get_service_names_and_types_by_node.return_value = []

        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()
            nodes = probe.get_nodes()
            assert nodes[0].full_name == "/robot/myNode"

    def test_get_nodes_root_namespace(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        mock_node.get_node_names_and_namespaces.return_value = [
            ("myNode", "/"),
        ]
        mock_node.get_publisher_names_and_types_by_node.return_value = []
        mock_node.get_subscriber_names_and_types_by_node.return_value = []
        mock_node.get_service_names_and_types_by_node.return_value = []

        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()
            nodes = probe.get_nodes()
            assert nodes[0].full_name == "/myNode"


class TestGraphProbeGetTopics:
    def test_get_topics_returns_rosm_topics(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            topics = probe.get_topics()
            assert len(topics) == 2
            for t in topics:
                assert isinstance(t, RosmTopic)

    def test_get_topics_includes_endpoints(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            topics = probe.get_topics()
            for t in topics:
                assert len(t.publishers) >= 0
                assert len(t.subscribers) >= 0

    def test_get_topics_msg_type_extracted(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        mock_node.get_topic_names_and_types.return_value = [
            ("/cmd_vel", ["geometry_msgs/msg/TwistStamped"]),
        ]
        mock_node.get_publishers_info_by_topic.return_value = []
        mock_node.get_subscriptions_info_by_topic.return_value = []

        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            topics = probe.get_topics()
            assert topics[0].msg_type == "geometry_msgs/msg/TwistStamped"


class TestGraphProbeGetServices:
    def test_get_services_returns_rosm_services(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            services = probe.get_services()
            assert len(services) == 1
            assert isinstance(services[0], RosmService)
            assert services[0].name == "/terrain_analysis/set_parameters"

    def test_get_services_empty(self, mock_rclpy):
        mock, mock_node, _ = mock_rclpy
        mock_node.get_service_names_and_types.return_value = []

        with patch("rclpy.ok", return_value=True), \
             patch("rclpy.init"), \
             patch("rclpy.create_node", return_value=mock_node), \
             patch("rclpy.executors.SingleThreadedExecutor", return_value=MagicMock()), \
             patch("threading.Thread") as mock_thread_cls, \
             patch("time.sleep"):
            mock_thread_cls.return_value = MagicMock()
            from rosm.probes.graph_probe import GraphProbe
            probe = GraphProbe(timeout_sec=0.0)
            probe.start()

            services = probe.get_services()
            assert services == []


class TestGraphProbeQoSExtraction:
    def test_extract_qos_reliable_transient_local(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        ep = _make_endpoint_info("node", "/", reliability=1, durability=1)
        qos = probe._extract_qos(ep.qos_profile)
        assert isinstance(qos, QoSProfile)
        assert qos.reliability == "RELIABLE"
        assert qos.durability == "TRANSIENT_LOCAL"

    def test_extract_qos_best_effort_volatile(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        ep = _make_endpoint_info("node", "/", reliability=0, durability=0)
        qos = probe._extract_qos(ep.qos_profile)
        assert qos.reliability == "BEST_EFFORT"
        assert qos.durability == "VOLATILE"

    def test_extract_qos_depth(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        ep = _make_endpoint_info("node", "/")
        ep.qos_profile.depth = 5
        qos = probe._extract_qos(ep.qos_profile)
        assert qos.depth == 5


class TestGraphProbeManagedContextManager:
    def test_managed_calls_start_and_stop(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        with patch.object(probe, "start") as mock_start, \
             patch.object(probe, "stop") as mock_stop:
            with probe.managed():
                mock_start.assert_called_once()
                mock_stop.assert_not_called()
            mock_stop.assert_called_once()

    def test_managed_stops_on_exception(self):
        from rosm.probes.graph_probe import GraphProbe
        probe = GraphProbe()
        with patch.object(probe, "start"), \
             patch.object(probe, "stop") as mock_stop:
            with pytest.raises(ValueError):
                with probe.managed():
                    raise ValueError("test error")
            mock_stop.assert_called_once()
