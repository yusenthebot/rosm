# rosm Spec v1.0

## Problem

ROS2 developers on Ubuntu face constant process/node/topic conflicts:
- Zombie nodes persist after crashes, consuming memory (1.4GB observed on this machine)
- /dev/shm/fastrtps_* files leak, breaking DDS on next launch
- No unified view of processes, nodes, topics, QoS, health
- Port conflicts (hardcoded ports like 10000)
- QoS mismatches cause silent communication failures
- No DDS domain isolation between concurrent sessions
- Existing tools (ros2 CLI, rqt_graph, htop) are fragmented and lack management

## Solution

`rosm` -- a standalone Python CLI + TUI tool that unifies process management, ROS2 graph introspection, conflict detection, and real-time monitoring.

## User Persona

ROS2 developer on Ubuntu, works with multiple workspaces, launches complex node graphs, needs to quickly diagnose and resolve conflicts.

## Functional Requirements

### FR-1: Process Management (CLI)
- `rosm ps` -- list all ROS2-related processes (PID, name, CPU%, MEM%, status, node name)
- `rosm kill <target>` -- kill by name pattern or PID, SIGTERM first then SIGKILL
- `rosm clean` -- kill zombies + clean orphaned SHM + reset ros2 daemon
- `rosm nuke` -- kill ALL ROS2 processes + full cleanup (confirmation required)

### FR-2: ROS2 Graph Introspection (CLI)
- `rosm nodes` -- list nodes with namespace, health, PID, pub/sub counts
- `rosm topics` -- list topics with type, pub/sub counts, optional Hz measurement
- `rosm services` -- list services with type and provider node

### FR-3: Conflict Detection (CLI)
- `rosm conflicts` -- detect and report all conflicts with severity and fix suggestions
- `rosm doctor` -- comprehensive health report combining conflicts + system status

### FR-4: TUI Dashboard
- Real-time dashboard with 6 tabs: Overview, Nodes, Topics, Processes, Conflicts, Graph
- Keyboard-driven navigation (F1-F6 tabs, k=kill, c=clean, q=quit, r=refresh)
- Auto-refresh at 1-2 Hz
- Interactive: select process/node and perform actions
- Visually polished: Catppuccin Mocha palette, box-drawing borders, color-coded severity, Unicode status indicators, sparkline Hz trends

### FR-5: Session Manager (stretch)
- Allocate unique ROS_DOMAIN_ID per session
- Per-session namespace prefixing

## Non-Functional Requirements

- NFR-1: Process commands (ps/kill/clean/nuke) work without ROS2 sourced
- NFR-2: Graph commands gracefully degrade if rclpy unavailable
- NFR-3: CLI response < 200ms for process commands, < 6s for graph commands (DDS discovery)
- NFR-4: TUI runs at < 5% CPU in idle
- NFR-5: Zero external service dependencies (no database, no web server)
- NFR-6: pip-installable with `console_scripts` entry point
- NFR-7: 80%+ test coverage on core modules

## Architecture

```
CLI (Click) / TUI (Textual)
        |
Conflict Engine (9 rules)
        |
Probes: ProcessProbe (psutil) | GraphProbe (rclpy) | SystemProbe (SHM/ports/env)
        |
Models (Pydantic v2, frozen)
```

### Introspection Strategy
- ProcessProbe: psutil, ~50ms, no ROS2 dependency
- GraphProbe: persistent rclpy node `/_rosm_monitor_{pid}`, ~5s warmup then sub-ms queries
- SystemProbe: /dev/shm scanning, psutil.net_connections, os.environ

### Conflict Rules
1. QoSMismatch (error) -- rclpy.qos.qos_check_compatible()
2. NodeNameCollision (error) -- duplicate names in same namespace
3. PortConflict (error) -- multiple processes on same port
4. ZombieProcess (warning) -- has --ros-args but no DDS presence
5. ShmLeak (warning) -- /dev/shm files with no owning process
6. MultiPublisher (warning) -- multiple publishers on single-writer topics
7. OrphanedTopic (info) -- pub with no sub or vice versa
8. StaleNode (info) -- node exists but 0 Hz output
9. DomainIsolation (info) -- ROS_DOMAIN_ID not set

## UI Design Spec

### Color Palette (Catppuccin Mocha)
- Background: #1e1e2e (Base)
- Surface: #313244 (Surface0)
- Accent: #89b4fa (Blue)
- Success: #a6e3a1 (Green)
- Warning: #f9e2af (Yellow)
- Error: #f38ba8 (Red)
- Info: #89dceb (Sky)
- Text: #cdd6f4 (Text)
- Subtext: #a6adc8 (Subtext0)

### Overview Tab Layout
```
+-- rosm dashboard -----------------------------------------------+
| Domain: 0  | Nodes: 21 | Topics: 129 | CPU: 12% | MEM: 4.2 GB  |
+-----------------------------------------------------------------+
| [Overview] [Nodes] [Topics] [Processes] [Conflicts] [Graph]     |
+-----------------------------------------------------------------+
|                                                                  |
| +-- Nodes ------+ +-- Topics -----+ +-- System ------+          |
| | total    21   | | total    129  | | CPU      12%   |          |
| | healthy  19   | | active    98  | | MEM    4.2 GB  |          |
| | stale     2   | | orphaned  31  | | SHM    205 MB  |          |
| +-+-------------+ +---------------+ +----------------+          |
|                                                                  |
| +-- Processes ---+ +-- Conflicts --+ +-- Domain ------+         |
| | total    15   | | errors     1  | | ID       0     |         |
| | zombies   9   | | warnings   2  | | RMW  fastrtps  |         |
| | orphans   3   | | info       4  | | distro  jazzy  |         |
| +---------------+ +---------------+ +----------------+          |
|                                                                  |
| +-- Alerts -------------------------------------------------+   |
| | [!] 9 zombie graph_decoder processes (1.4GB wasted)       |   |
| | [!] 47 orphaned FastRTPS SHM semaphores in /dev/shm       |   |
| | [i] ROS_DOMAIN_ID not set (using default 0)               |   |
| +-----------------------------------------------------------+   |
+-----------------------------------------------------------------+
| [k]ill  [c]lean  [n]uke  [r]efresh  [?]help  [q]uit            |
+-----------------------------------------------------------------+
```

### Nodes Tab
- Left: Tree view (namespace / node_name)
- Right: Detail panel (publishers, subscribers, services, parameters, PID, CPU, health)
- Color-coded health dots: green=healthy, yellow=stale, red=zombie

### Topics Tab
- Sortable table: Name | Type | Pubs | Subs | Hz | BW | QoS
- Hz column shows sparkline trend (last 10 samples)
- Highlight rows with QoS mismatches in red

### Processes Tab
- Sortable table: PID | Name | Node | CPU% | MEM(MB) | Status | Uptime
- Status column color-coded
- Select + Enter to see details, 'k' to kill

### Conflicts Tab
- Grouped by severity (errors first)
- Each conflict shows: icon, title, description, affected entities, suggested fix
- Action button to auto-fix where possible (clean SHM, kill zombie)

### Graph Tab
- ASCII/Unicode node-topic connectivity visualization
- Nodes as boxes, topics as lines with arrows
- Color by namespace

## Tech Stack
- Python 3.12, ROS2 Jazzy
- click>=8.0 (CLI framework)
- psutil>=5.9 (process management)
- rich>=13.0 (terminal formatting)
- pydantic>=2.0 (data models)
- textual>=0.80 (TUI, optional dependency)
- rclpy (runtime import, not pip dependency)

## Test Harness

### L0: Models + Utils (unit, no deps)
- Pydantic model creation, serialization, validation
- _compat.py fallback logic

### L1: ProcessProbe (unit, mock psutil)
- Process detection with mock psutil.process_iter
- Zombie/orphan classification
- Kill logic with mock signals

### L2: SystemProbe (unit, mock filesystem)
- SHM file enumeration with mock /dev/shm
- Port conflict detection with mock net_connections
- Environment variable reading

### L3: GraphProbe (integration, needs rclpy)
- Node discovery with test node
- Topic introspection
- QoS profile extraction

### L4: ConflictEngine (unit, mock snapshots)
- Each rule tested with handcrafted SystemSnapshot
- Engine aggregation and sorting

### L5: CLI (unit, Click CliRunner)
- All commands with mocked probes
- Output format verification
- Flag handling (--dry-run, --force, --hz)

### L6: TUI (integration, Textual pilot)
- Dashboard launch and tab switching
- Widget rendering with mock data
- Keyboard binding verification

### L7: E2E (requires ROS2 environment)
- Full pipeline: launch test nodes -> rosm discovers -> conflicts detected -> cleanup works
