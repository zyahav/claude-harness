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
-   **`lifecycle.py`**: Encapsulates all Git worktree operations, ensuring isolation between agent runs and the main repo.
-   **`schema.py`**: Defines the canonical data model (`Handoff`, `Task`) with built-in validation methods.
-   **`agent.py`**: Orchestrates the agent loop, decoupling high-level logic from the SDK implementation.
-   **`client.py`**: Centralized configuration for the Claude SDK, enforcing security policies and environment management.

### Key Design Decisions
-   **Git Worktrees for Isolation**: Each agent run operates in its own folder (`runs/<run-name>`) backed by a dedicated branch (`run/<run-name>`). This prevents "dirty working directory" issues and allows parallel runs.
-   **Lazy Imports**: Heavy dependencies (like `claude-code-sdk`) are lazy-loaded. This ensures the CLI remains snappy (e.g., for `--help` or `list`) even if the SDK is not installed or configured (see `docs/ADR-001-lazy-imports.md`).

---

## 3. Current System State

### Capabilities
-   **Robust Lifecycle**: Agents can be started, stopped, resumed, and cleaned up via simple CLI commands.
-   **Schema Validation**: The system strictly validates `handoff.json` on startup. Corrupted files are rejected to prevent "zombie" runs.
-   **Type Safety**: The codebase is fully typed and uses `dataclasses` for data contracts.

### Technical Audit (v2.0)
-   **Memory Persistence**: File-based via `handoff.json` in the project worktree.
-   **Context Window**: Managed by `claude-code-sdk` (defaults to 100k tokens).
-   **Tooling**: Implicitly defined via the SDK (`"Read"`, `"Bash"`).

---

## 4. Future Roadmap & Multi-Provider Strategy

*Note: This section outlines the planned transition to a "Universal Intelligence Console" supporting models beyond Claude.*

**Feasibility Verdict:** **GO**
The structure (worktrees + independent task tracking) is provider-agnostic. The transition is feasible but requires refactoring `client.py` and `agent.py`.

### Proposed Phases
1.  **Phase 1: Provider Factory**: Create an `LLMProvider` protocol to abstract away the specific SDK. Implement `AnthropicProvider` and `OpenAIProvider`.
2.  **Phase 2: Schema Evolution**: Update `schema.py` to allow tasks to specify their preferred model/provider in `handoff.json`.
3.  **Phase 3: The Orchestrator**: Modify `harness.py` to instantiate the correct provider for each task dynamically.

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
