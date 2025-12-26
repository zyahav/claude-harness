# Harness Lab

A robust CLI harness for running long-running autonomous coding agents using Claude and Git worktrees.

## Features

- **Isolated Execution:** Each agent run gets its own Git worktree and dedicated branch.
- **Lifecycle Management:** Simple commands to start, run, list, finish, and clean up agent runs.
- **Schema Validation:** Ensures `handoff.json` remains valid and follows the canonical project format.
- **Resilient CLI:** Lazy loading of heavy dependencies (like the Claude SDK) for fast help and validation.

## Quick Links

- **[🤖 Agent Guide](AGENT_GUIDE.md)**: Strictly formatted guide for autonomous agents.
- **[Architectural Decision Records](docs/)**: detailed design documents.

## Installation

```bash
# Clone the repository
git clone https://github.com/zyahav/claude-harness.git
cd claude-harness

# Install dependencies (Claude SDK is optional for help/list/clean)
pip install -r requirements.txt

# For full agent functionality (requires access to private SDK):
# For full agent functionality (requires access to private SDK):
pip install -r requirements-sdk.txt

# Install the tool in editable mode to get the 'c-harness' command:
pip install -e .
```

## Quick Start (Orchestrator Mode)

The recommended way to use `claude-harness` is as an external orchestrator managing other repositories.

```bash
# 1. Start a new run for an external repo
# 1. Start a new run for an external repo
c-harness start my-task --repo-path ../target-repo

# 2. Do your work in the new worktree: runs/my-task

# 3. Finish and push
c-harness finish my-task --repo-path ../target-repo --handoff-path ../handoff.json
```

## Usage (Resident Mode)

The `c-harness` command (or `harness.py` script) is the main entry point. Use subcommands to manage the agent lifecycle.

### 1. Start a new run
Creates a new branch and an isolated worktree in the `runs/` directory.
```bash
c-harness start my-feature-run
```

### 2. List active runs
Shows all runs, their status, and creation time.
```bash
c-harness list
```

### 3. Execute the agent
Runs the autonomous agent loop inside the specified worktree.
```bash
c-harness run my-feature-run
```

### 4. Finish a run
Verifies all tasks are complete, pushes the branch to the remote repository, and provides PR instructions.
```bash
c-harness finish my-feature-run
```

### 5. Clean up
Removes the worktree and optionally deletes the local branch.
```bash
c-harness clean my-feature-run --delete-branch
```

## 🗺️ Repository Map (Agent-Ready)

To ensure seamless integration for both humans and AI agents, here is the architectural map:

- **Core Logic:** `harness.py` (CLI entry point) and `lifecycle.py` (Git worktree management).
- **Agent Intelligence:** `agent.py` (The interface for Claude/LLMs).
- **Quality Gate (CI/CD):** Located in `.github/workflows/tests.yml`. Runs pytest on every push.
- **Testing Suite:** Located in `tests/`. Includes `test_orchestrator.py` for cross-directory validation.
- **Agent Guide:** `AGENT_GUIDE.md` (Specific instructions for LLMs driving this tool).
- **Schema:** `schema.py` defines the `handoff.json` structure.

## Testing

The project includes a comprehensive test suite using Python's `unittest` framework.

```bash
# Run all tests
python3 -m unittest discover tests
```

Tests cover:
- Schema validation
- CLI argument parsing
- Git lifecycle operations (in isolated temp environments)
- Agent logic (mocked)

## License
MIT