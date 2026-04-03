"""rclpy-based DDS graph introspection probe."""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Generator

from rosm.models import EndpointInfo, QoSProfile, RosmNode, RosmService, RosmTopic


class GraphProbe:
    """rclpy-based DDS graph introspection with persistent background node."""

    def __init__(
        self,
        domain_id: int | None = None,
        timeout_sec: float = 5.0,
    ) -> None:
        self._node = None
        self._spin_thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._domain_id = domain_id
        self._timeout_sec = timeout_sec
        self._executor = None

    def start(self) -> None:
        """Init rclpy, create /_rosm_monitor_{pid} node, start spin thread.

        Blocks until DDS discovery completes (timeout_sec).
        """
        import rclpy
        from rclpy.executors import SingleThreadedExecutor

        if not rclpy.ok():
            rclpy.init(domain_id=self._domain_id)

        node_name = f"_rosm_monitor_{os.getpid()}"
        self._node = rclpy.create_node(node_name)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        self._spin_thread = threading.Thread(
            target=self._spin_worker,
            daemon=True,
        )
        self._spin_thread.start()

        # Wait for DDS discovery
        time.sleep(self._timeout_sec)
        self._ready.set()

    def stop(self) -> None:
        """Shutdown node and spin thread."""
        # Order matters: shutdown rclpy first (stops executor spin),
        # then destroy node, then join thread.
        try:
            import rclpy
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass

        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None

        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                pass
            self._node = None

        self._executor = None

    @contextmanager
    def managed(self) -> Generator[GraphProbe, None, None]:
        """Context manager for start/stop lifecycle."""
        self.start()
        try:
            yield self
        finally:
            self.stop()

    def get_nodes(self) -> list[RosmNode]:
        """Get all discovered nodes with their pub/sub/service info."""
        if self._node is None:
            return []

        results: list[RosmNode] = []
        for name, namespace in self._node.get_node_names_and_namespaces():
            try:
                pub_topics = self._node.get_publisher_names_and_types_by_node(
                    name, namespace
                )
                sub_topics = self._node.get_subscriber_names_and_types_by_node(
                    name, namespace
                )
                services = self._node.get_service_names_and_types_by_node(
                    name, namespace
                )
            except Exception:
                pub_topics = []
                sub_topics = []
                services = []

            full_name = self._build_full_name(name, namespace)

            node = RosmNode(
                name=name,
                namespace=namespace,
                full_name=full_name,
                published_topics=tuple(t for t, _ in pub_topics),
                subscribed_topics=tuple(t for t, _ in sub_topics),
                services=tuple(s for s, _ in services),
            )
            results.append(node)

        return results

    def get_topics(self) -> list[RosmTopic]:
        """Get all topics with endpoint info and QoS profiles."""
        if self._node is None:
            return []

        results: list[RosmTopic] = []
        for topic_name, type_list in self._node.get_topic_names_and_types():
            msg_type = type_list[0] if type_list else "UNKNOWN"

            try:
                pub_endpoints_raw = self._node.get_publishers_info_by_topic(topic_name)
                sub_endpoints_raw = self._node.get_subscriptions_info_by_topic(topic_name)
            except Exception:
                pub_endpoints_raw = []
                sub_endpoints_raw = []

            publishers = tuple(
                self._build_endpoint_info(ep) for ep in pub_endpoints_raw
            )
            subscribers = tuple(
                self._build_endpoint_info(ep) for ep in sub_endpoints_raw
            )

            topic = RosmTopic(
                name=topic_name,
                msg_type=msg_type,
                publishers=publishers,
                subscribers=subscribers,
            )
            results.append(topic)

        return results

    def get_services(self) -> list[RosmService]:
        """Get all services."""
        if self._node is None:
            return []

        results: list[RosmService] = []
        for svc_name, type_list in self._node.get_service_names_and_types():
            svc_type = type_list[0] if type_list else "UNKNOWN"
            # Parse node name from service name (heuristic: last segment before /set_parameters etc.)
            # We use empty strings when node identity is not easily recoverable
            service = RosmService(
                name=svc_name,
                service_type=svc_type,
                node_name="",
                node_namespace="",
            )
            results.append(service)

        return results

    def _spin_worker(self) -> None:
        """Background spin — runs executor until shutdown."""
        try:
            self._executor.spin()
        except Exception:
            pass

    def _extract_qos(self, qos_profile: object) -> QoSProfile:
        """Convert rclpy QoS to our QoSProfile model."""
        try:
            reliability = getattr(getattr(qos_profile, "reliability", None), "name", "UNKNOWN")
        except Exception:
            reliability = "UNKNOWN"

        try:
            durability = getattr(getattr(qos_profile, "durability", None), "name", "UNKNOWN")
        except Exception:
            durability = "UNKNOWN"

        try:
            history = getattr(getattr(qos_profile, "history", None), "name", "UNKNOWN")
        except Exception:
            history = "UNKNOWN"

        try:
            depth = int(getattr(qos_profile, "depth", 0))
        except Exception:
            depth = 0

        try:
            lifespan_ns = int(getattr(getattr(qos_profile, "lifespan", None), "nanoseconds", 0))
        except Exception:
            lifespan_ns = 0

        try:
            deadline_ns = int(getattr(getattr(qos_profile, "deadline", None), "nanoseconds", 0))
        except Exception:
            deadline_ns = 0

        try:
            liveliness = getattr(getattr(qos_profile, "liveliness", None), "name", "AUTOMATIC")
        except Exception:
            liveliness = "AUTOMATIC"

        return QoSProfile(
            reliability=reliability,
            durability=durability,
            history=history,
            depth=depth,
            lifespan_ns=lifespan_ns,
            deadline_ns=deadline_ns,
            liveliness=liveliness,
        )

    def _build_endpoint_info(self, endpoint_info: object) -> EndpointInfo:
        """Convert rclpy TopicEndpointInfo to our EndpointInfo model."""
        node_name = getattr(endpoint_info, "node_name", "")
        node_namespace = getattr(endpoint_info, "node_namespace", "")
        qos_raw = getattr(endpoint_info, "qos_profile", None)
        qos = self._extract_qos(qos_raw) if qos_raw is not None else QoSProfile()

        gid_raw = getattr(endpoint_info, "endpoint_gid", b"")
        try:
            gid = gid_raw.hex() if isinstance(gid_raw, (bytes, bytearray)) else str(gid_raw)
        except Exception:
            gid = ""

        return EndpointInfo(
            node_name=node_name,
            node_namespace=node_namespace,
            qos=qos,
            gid=gid,
        )

    @staticmethod
    def _build_full_name(name: str, namespace: str) -> str:
        """Combine name and namespace into a full node path."""
        if namespace == "/":
            return f"/{name}"
        return f"{namespace}/{name}"
