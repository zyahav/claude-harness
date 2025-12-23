# Harness Lab

A robust CLI harness for running long-running autonomous coding agents using Claude and Git worktrees.

## Features

- **Isolated Execution:** Each agent run gets its own Git worktree and dedicated branch.
- **Lifecycle Management:** Simple commands to start, run, list, finish, and clean up agent runs.
- **Schema Validation:** Ensures `handoff.json` remains valid and follows the canonical project format.
- **Resilient CLI:** Lazy loading of heavy dependencies (like the Claude SDK) for fast help and validation.

## Installation

```bash
# Clone the repository
git clone https://github.com/<ORG_OR_USER>/claude-harness.git
cd claude-harness

# Install dependencies (Claude SDK is optional for help/list/clean)
pip install -r requirements.txt
```

## Usage

The `harness.py` script is the main entry point. Use subcommands to manage the agent lifecycle.

### 1. Start a new run
Creates a new branch and an isolated worktree in the `runs/` directory.
```bash
python3 harness.py start my-feature-run
```

### 2. List active runs
Shows all runs, their status, and creation time.
```bash
python3 harness.py list
```

### 3. Execute the agent
Runs the autonomous agent loop inside the specified worktree.
```bash
python3 harness.py run my-feature-run
```

### 4. Finish a run
Verifies all tasks are complete, pushes the branch to the remote repository, and provides PR instructions.
```bash
python3 harness.py finish my-feature-run
```

### 5. Clean up
Removes the worktree and optionally deletes the local branch.
```bash
python3 harness.py clean my-feature-run --delete-branch
```

## Architecture

- **`harness.py`**: The main CLI dispatcher.
- **`lifecycle.py`**: Handles Git worktree operations and metadata.
- **`schema.py`**: Defines the `handoff.json` format and validation logic.
- **`agent.py`**: Orchestrates the interaction between Claude and the SDK.
- **`prompts/`**: Contains the system prompts for different agent roles.

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