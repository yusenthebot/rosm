"""ROS2 availability checks with graceful fallback."""

from __future__ import annotations

import shutil
import functools


@functools.cache
def has_rclpy() -> bool:
    """Check if rclpy is importable."""
    try:
        import rclpy  # noqa: F401
        return True
    except ImportError:
        return False


@functools.cache
def has_ros2_cli() -> bool:
    """Check if ros2 CLI is available on PATH."""
    return shutil.which("ros2") is not None


def require_rclpy(func):
    """Decorator that raises RuntimeError if rclpy unavailable."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not has_rclpy():
            raise RuntimeError(
                "rclpy not available. Source ROS2: 'source /opt/ros/jazzy/setup.bash'"
            )
        return func(*args, **kwargs)
    return wrapper


class ROS2Unavailable(RuntimeError):
    """Raised when ROS2 is required but not available."""

    def __init__(self):
        super().__init__(
            "ROS2 not available. Source your ROS2 installation first.\n"
            "  source /opt/ros/jazzy/setup.bash"
        )
