# Harness Lab

A robust CLI harness for running long-running autonomous coding agents using Claude and Git worktrees.

## Features

- **Isolated Execution:** Each agent run gets its own Git worktree and dedicated branch.
- **Lifecycle Management:** Simple commands to start, run, list, finish, and clean up agent runs.
- **Schema Validation:** Ensures `handoff.json` remains valid and follows the canonical project format.
- **Resilient CLI:** Lazy loading of heavy dependencies (like the Claude SDK) for fast help and validation.

## Quick Links

- **[🤖 Agent Guide](AGENT_GUIDE.md)**: Strictly formatted guide for autonomous agents.
- **[📁 Examples](examples/)**: Sample handoff.json files to get started.
- **[🔧 Brownfield Quick Start](docs/BROWNFIELD_QUICKSTART.md)**: Guide for fixing bugs in existing code.
- **[Architectural Decision Records](docs/)**: Detailed design documents.

## Modes: Greenfield vs Brownfield

c-harness supports two modes depending on your use case:

| Mode | Use Case | Flag |
|------|----------|------|
| **Greenfield** | Building a new app from scratch | `--mode greenfield` (default) |
| **Brownfield** | Fixing bugs or adding features to existing code | `--mode brownfield` |

### Which mode should I use?

```
Do you have existing code?
├── No  → Greenfield (build from app_spec.txt)
└── Yes → Are you building a major new feature from scratch?
          ├── Yes → Greenfield
          └── No  → Brownfield (focused fixes/improvements)
```

### Greenfield Mode (default)

For building new applications from scratch. The agent expects:
- `app_spec.txt` — Full application specification
- `handoff.json` — 50-200+ tasks covering the entire build

```bash
c-harness start my-app --repo-path ../new-project --mode greenfield
```

### Brownfield Mode

For fixing bugs or making targeted improvements to existing code. The agent expects:
- `handoff.json` — 1-10 focused tasks
- Existing codebase to understand and modify

```bash
c-harness start BUG-123 --repo-path ../existing-project --mode brownfield
```

See [Brownfield Quick Start](docs/BROWNFIELD_QUICKSTART.md) for a complete guide.

## Installation

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for browser automation via MCP)
- **Google Chrome** (for UI testing and verification)

### Setup

```bash
# Clone the repository
git clone https://github.com/zyahav/claude-harness.git
cd claude-harness

# Install dependencies (Claude SDK is optional for help/list/clean)
pip install -r requirements.txt

# For full agent functionality (requires access to private SDK):
pip install -r requirements-sdk.txt

# Install the tool in editable mode to get the 'c-harness' command:
pip install -e .
```

### Browser Automation

c-harness uses [Chrome DevTools MCP](https://github.com/anthropics/anthropic-quickstarts/tree/main/mcp-servers/chrome-devtools) for browser automation. This allows agents to:
- Navigate to URLs and take screenshots
- Click elements and fill forms
- Verify UI behavior end-to-end
- Check console errors and network requests

The MCP server is automatically downloaded via `npx` when the agent runs.

## Quick Start (Orchestrator Mode)

The recommended way to use `claude-harness` is as an external orchestrator managing other repositories.

```bash
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
Verifies all tasks are complete, checks for documentation drift, pushes the branch to the remote repository, and provides PR instructions.
```bash
c-harness finish my-feature-run
```

**Documentation Trust Protocol (DTP):**
By default, `finish` checks for undocumented changes (new CLI flags, new public Python files) and displays a warning. To enforce documentation compliance, use `--doc-strict`:

```bash
c-harness finish my-feature-run --doc-strict
```

With `--doc-strict`, the command will block if documentation drift is detected. To mark items as internal or manage deferred items, edit `.harness/doc_decisions.json`.

### 5. Clean up
Removes the worktree and optionally deletes the local branch.
```bash
c-harness clean my-feature-run --delete-branch
```

## Harness Commander (ADHD-First Control Plane)

Harness Commander is an additional layer on top of the core harness functionality, designed to help manage multiple concurrent projects and tasks. It provides state management, reconciliation, and an ADHD-friendly interface for tracking work across multiple repositories.

### Key Features

- **State Management**: Track projects, runs, and tasks across all your work
- **Git-First Reconciliation**: Automatically syncs state with Git reality
- **Concurrency Control**: Controller/Observer mode with lock management
- **Interactive Cockpit**: Visual overview of your current focus and next actions
- **Inbox System**: Quick capture of ideas without context switching
- **Rule Engine**: Computes the next best action automatically

### Commander Commands

#### Health Check & Setup

```bash
# Run pre-flight checks
c-harness doctor

# Run checks and auto-fix safe issues
c-harness doctor --repair-state

# Check installation and updates
c-harness bootstrap
```

#### Session Management

```bash
# Start interactive session (recommended)
c-harness session

# Show current status
c-harness status

# Show next recommended action
c-harness next
```

#### Focus & Project Management

```bash
# View current focus project
c-harness focus

# Set focus project
c-harness focus set <project-id-or-name>
```

#### Inbox (Quick Capture)

```bash
# Capture an idea (fire-and-forget)
c-harness inbox "Add dark mode to dashboard"

# List all inbox items
c-harness inbox --list

# Promote inbox item to task
c-harness inbox --promote <item-id>

# Dismiss (delete) inbox item
c-harness inbox --dismiss <item-id>
```

### Commander Workflow

1. **Start Session**: `c-harness session` runs pre-flight checks and acquires controller lock
2. **View Cockpit**: See focus project, active runs, blocked items, and inbox
3. **Follow Next Action**: Commander tells you exactly what to work on next
4. **Capture Ideas**: Use `c-harness inbox` to quickly capture thoughts without interrupting work
5. **Auto-Reconcile**: Commander automatically syncs with Git reality (no manual state updates)

### Phase 1 Limitations

Current implementation (Phase 1) focuses on:
- ✅ Git-based project management
- ✅ Local state synchronization
- ✅ Interactive cockpit display
- ✅ Quick capture inbox system
- ⏳ Convex integration (planned for Phase 2)

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