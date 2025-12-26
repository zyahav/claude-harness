# Architecture & System Overview

**Project:** Harness Lab (Autonomous Agent Orchestrator)
**Status:** Production Ready (v2.0)

## 1. Executive Summary

Harness Lab is a robust CLI tool for running autonomous coding agents. It uses a **long-running agent loop** (Claude) isolated within **Git worktrees**. This architecture ensures that agent-generated code changes are kept separate from the main development branch until they are verified and explicitly finished.

The system has recently transitioned from a prototype script to a modular, type-safe CLI application with a dedicated testing suite.

---

## 2. System Architecture

The codebase is organized into modular components to ensure separation of concerns:

-   **`harness.py`**: A thin CLI wrapper using `argparse` for subcommand dispatch (`start`, `run`, `list`, `clean`, `finish`).

### Layer A: The Engine (Existing)
*Core components providing the Git worktree lifecycle.*

-   **`lifecycle.py`**: Encapsulates all Git worktree operations, ensuring isolation between agent runs and the main repo.
-   **`schema.py`**: Defines the canonical data model (`Handoff`, `Task`) with built-in validation methods.
-   **`agent.py`**: Orchestrates the agent loop, decoupling high-level logic from the SDK implementation.
-   **`client.py`**: Centralized configuration for the Claude SDK, enforcing security policies and environment management.

#### Key Design Decisions (Engine)
-   **Git Worktrees for Isolation**: Each agent run operates in its own folder (`runs/<run-name>`) backed by a dedicated branch (`run/<run-name>`). This prevents "dirty working directory" issues and allows parallel runs.
-   **Lazy Imports**: Heavy dependencies (like `claude-code-sdk`) are lazy-loaded. This ensures the CLI remains snappy.

### Layer B: Harness Commander (New)
*The ADHD-First Control Plane.*

**Status:** Phase 1 MVP Construction

To solve "state chaos" and "ADHD execution drift", we are adding a **Commander Layer** on top of the Engine.

*   **Role**: The "Steering Wheel". It provides a deterministic, single-controller interface for managing the agent's focus.
*   **Key Concepts**:
    *   **Controller vs Observer**: Only one process can mutate state at a time (guarded by a lock file).
    *   **Reconcile Reality**: The system trust's `git` over its own internal database. If the user changes branches, the Commander adapts.
    *   **Loop Closure**: The system nudges the user to finish runs and clean up worktrees.

---

## 3. Current System State

### Capabilities (Engine v2.0)
-   **Robust Lifecycle**: Agents can be started, stopped, resumed, and cleaned up via simple CLI commands.
-   **Schema Validation**: The system strictly validates `handoff.json` on startup.
-   **Type Safety**: The codebase is fully typed and uses `dataclasses`.

### Technical Audit
-   **Memory Persistence**: File-based via `handoff.json`.
-   **Tooling**: Implicitly defined via the SDK (`"Read"`, `"Bash"`).

---

## 4. Future Roadmap & Multi-Provider Strategy

*Note: The "Universal Intelligence Console" vision has evolved into "Harness Commander".*

### Phase 1: Harness Commander MVP (Current Focus)
Goal: **Trust > Intelligence.**
-   Implement `c-harness session` (Cockpit).
-   Implement `c-harness next` (Single Instruction).
-   Implement `c-harness inbox` (Fire-and-forget capture).
-   **No Convex yet** (Local filesystem state only).

### Phase 2: Distributed State
Goal: **Multi-Device / Team Synchronization.**
-   Introduce Convex backend.
-   Kanban UI.
-   Shared leases.

### Phase 3: Multi-Provider Support
Goal: **Agnt-Agnostic.**
-   Refactoring `agent.py` to support OpenAI/Gemini via a Provider Protocol.


---

## 5. Testing Strategy

We maintain a permanent, automated test suite using Python's `unittest` framework.

### Test Structure
-   **`tests/test_schema.py`**: Validates JSON contracts and data integrity.
-   **`tests/test_lifecycle.py`**: Validates Git worktree operations. **Safe Execution**: Uses temporary directories and bare repos to avoid touching the user's actual environment.
-   **`tests/test_cli.py`**: Validates command-line entry points.
-   **`tests/test_agent.py`**: Validates agent logic using Mocks (no API costs).

### Running Tests
```bash
python3 -m unittest discover tests
```
Output should show `OK` if all tests pass.
