# rosm

ROS2 process, node, and topic manager for Ubuntu. CLI + TUI dashboard with conflict detection.

Detects zombie processes, port conflicts, QoS mismatches, SHM leaks, and orphaned topics. One command to diagnose, one command to clean up.

## Architecture

```
+------------------------------------------------------------------+
|                        rosm CLI / TUI                            |
|   rosm ps | kill | clean | nuke | nodes | topics | conflicts    |
|   rosm dashboard (Textual TUI, 5 tabs, real-time)               |
+------------------------------------------------------------------+
|                    Conflict Detection Engine                      |
|   9 rules: QoS mismatch | port conflict | zombie process        |
|            name collision | SHM leak | orphaned topic            |
|            multi-publisher | stale node | domain isolation        |
+------------------------------------------------------------------+
|                      Core Probes                                 |
|   ProcessProbe    |   GraphProbe      |   SystemProbe            |
|   (psutil)        |   (rclpy node)    |   (/dev/shm, ports, env) |
|   ~50ms, no ROS2  |   ~5s discovery   |   ~10ms                  |
+------------------------------------------------------------------+
|                    Pydantic v2 Models                             |
|   RosmProcess | RosmNode | RosmTopic | Conflict | SystemSnapshot |
+------------------------------------------------------------------+
```

## Install

```bash
cd rosm
pip install -e ".[tui]"
```

Requires ROS2 Jazzy (or any ROS2 distro) for node/topic introspection. Process management works without ROS2.

## Usage

```bash
# Process management
rosm ps                    # List all ROS2 processes
rosm kill graph_decoder    # Kill by name
rosm kill 12345            # Kill by PID
rosm clean                 # Kill zombies + clean /dev/shm + reset daemon
rosm clean --dry-run       # Preview without executing
rosm nuke                  # Kill ALL ROS2 processes + full cleanup

# ROS2 introspection (requires ROS2 sourced)
rosm nodes                 # List nodes with health status
rosm topics                # List topics with pub/sub counts
rosm topics --hz           # Include Hz measurement (~5s)
rosm services              # List services

# Diagnostics
rosm conflicts             # Detect all conflicts with fix suggestions
rosm doctor                # Full system health report

# TUI dashboard
rosm dashboard             # Real-time monitoring (F1-F5 tabs, q quit)
```

## Conflict Detection

rosm detects 9 types of issues:

| Rule | Severity | What it catches |
|------|----------|-----------------|
| QoS Mismatch | error | Publisher BEST_EFFORT + Subscriber RELIABLE (silent failure) |
| Node Name Collision | error | Duplicate node names in same namespace |
| Port Conflict | error | Multiple processes binding same DDS port |
| Zombie Process | warning | Orphaned ROS2 processes (parent died) |
| SHM Leak | warning | /dev/shm/fastrtps_* files with no owning process |
| Multi-Publisher | warning | Multiple publishers on /cmd_vel (race condition) |
| Orphaned Topic | info | Publisher with no subscriber, or vice versa |
| Stale Node | info | Node in DDS graph but not publishing |
| Domain Isolation | info | ROS_DOMAIN_ID not set (default 0, no isolation) |

## TUI Dashboard

```
rosm dashboard
```

5 tabs: Overview | Nodes | Topics | Processes | Conflicts

- Overview: 6 status cards (nodes, topics, system, processes, conflicts, domain) + alert feed
- Processes: sortable table, select + `k` to kill
- Conflicts: severity-grouped with fix suggestions
- Auto-refreshes every 2 seconds
- Catppuccin Mocha color scheme

Keybindings: `F1`-`F5` switch tabs, `k` kill, `c` clean, `r` refresh, `q` quit.

## How It Works

**ProcessProbe** scans all OS processes via psutil, filters by ROS2 signatures (`--ros-args`, `/opt/ros/`, `/install/`), classifies status (running/orphan/zombie), and extracts node names from cmdline args.

**GraphProbe** creates a hidden rclpy node (`/_rosm_monitor_{pid}`) that discovers all DDS participants. Returns nodes, topics, services, and QoS profiles. Takes ~5s for initial DDS discovery, then sub-millisecond queries.

**SystemProbe** enumerates `/dev/shm/fastrtps_*` files, cross-references with running PIDs to find leaks, reads environment variables (ROS_DOMAIN_ID, RMW_IMPLEMENTATION).

**ConflictEngine** runs all 9 rules against a unified SystemSnapshot and returns severity-sorted conflicts with actionable fix suggestions.

## Project Structure

```
rosm/
  cli.py               # Click CLI, 10 commands
  models.py            # Pydantic v2 data models (frozen)
  _compat.py           # rclpy availability check + fallback
  probes/
    process_probe.py   # psutil-based process detection
    graph_probe.py     # rclpy DDS graph introspection
    system_probe.py    # SHM, ports, environment
  engine/
    conflict_engine.py # Rule runner
    rules/             # 9 conflict detection rules
  actions/
    kill.py            # Process termination
    clean.py           # Zombie + SHM cleanup
    nuke.py            # Full cleanup
  tui/
    app.py             # Textual dashboard
    theme.py           # Catppuccin Mocha CSS
    screens/           # Tab content widgets
    widgets/           # StatusCard, AlertLog
tests/                 # 240 tests, ~93% coverage
```

## Dependencies

- Python >= 3.10
- click, psutil, rich, pydantic (core)
- textual >= 0.80 (optional, for TUI)
- rclpy (system install via apt, not pip)

## License

MIT
