# Claude-Harness Agent Guide

This guide is written for Autonomous LLM Agents. It details the repository architecture, standard operating procedures, and strict schema requirements for interacting with `claude-harness`.

## 1. Repository Purpose

`claude-harness` is an **Orchestrator** tool. It manages *other* Git repositories.
You should almost never modify `claude-harness` itself. Instead, you use it to manage **Target Repositories**.

## 0. Credential Handling

This agent requires the following environment variables to be **transported** into the runtime.
**DO NOT store these in local files or `.env` inside the worktree.**

- `ANTHROPIC_API_KEY` (Option 1: Basic Auth)
- `CLAUDE_CODE_OAUTH_TOKEN` (Option 2: OAuth / `claude login`)

**Protocol:** Export these variables in your shell before running `harness`.

## 2. Core Architecture

- **`c-harness`**: The CLI entry point (installed via `pip`). YOU CALL THIS.
- **`harness.py`**: The raw script (developer fallback).
- **`lifecycle.py`**: Git worktree and branch management.
- **`schema.py`**: The validator for `handoff.json`. **Note:** Uses Python `dataclasses` (Standard Library) for dependency-free validation. Not Pydantic.
- **`doc_check.py`**: Documentation Trust Protocol implementation. Detects and tracks documentation drift for CLI flags and public Python files.

## 3. Standard Operating Procedures

### A. Start a New Task (The "Clone & Branch" equivalent)

Command:
```bash
c-harness start <task-name> --repo-path <path/to/target-repo>
```
> **Developer Note:** If `c-harness` is not in your PATH, you can use `python3 harness.py ...` instead.
- **Effect:** Creates a new git worktree in `runs/<task-name>` and a branch `run/<task-name>` in the target repo.
- **Output:** Returns the path to the NEW worktree.
- **Next Step:** Do your work inside that new worktree path.

### B. Execute Agent Loop (Optional)

Command:
```bash
c-harness run <task-name> --repo-path <path/to/target-repo>
```
- **Effect:** Runs the automated agent loop (if configured). Usually, you (the LLM) *are* the agent, so you might skip this and just edit files directly in the worktree.

### C. Finish & Handoff (Critical)

Command:
```bash
c-harness finish <task-name> --repo-path <path/to/target-repo> --handoff-path <path/to/handoff.json>
```
- **Effect:**
    1. Validates the `handoff.json` file against strict schema.
    2. Checks if tasks are marked `passes: true`.
    3. Pushes the branch to the remote origin.
- **Requirement:** You MUST create a valid `handoff.json` before calling finish.

## 4. Handoff Schema Specification

Your `handoff.json` MUST strictly adhere to this format.

### Valid Categories
`security`, `oidc`, `roles`, `infrastructure`, `cli`, `testing`, `docs`, `functional`, `style`, `api`, `database`, `auth`, `ui`

### JSON Template

```json
{
  "meta": {
    "project": "Project Name",
    "phase": "Phase 1",
    "source": "manual",
    "lock": true
  },
  "tasks": [
    {
      "id": "TASK-001",
      "category": "api",
      "title": "Short Title",
      "description": "Detailed description of what was done.",
      "acceptance_criteria": [
        "Server starts on port 8080",
        "Endpoint /health returns 200"
      ],
      "passes": true,
      "files_expected": [
        "src/server.py",
        "tests/test_server.py"
      ],
      "steps": [
        "Run `python server.py`",
        "Curl localhost:8080/health"
      ]
    }
  ]
}
```

### Common Validation Errors
- **Missing `meta` block**: The root object must have `meta` and `tasks`.
- **Invalid `category`**: Use ONLY the list provided above.
- **Missing `acceptance_criteria`**: Must be a non-empty list of strings.
- **`passes` is not boolean**: Must be `true` or `false` (literal).

## 5. Harness Commander (Advanced Workflow)

Harness Commander is an ADHD-first control plane that helps manage multiple concurrent projects and tasks. It provides state management, reconciliation, and intelligent next-action recommendations.

### When to Use Harness Commander

Use Commander when:
- Working across multiple repositories simultaneously
- Managing complex task dependencies
- Need help prioritizing what to work on next
- Want to minimize context switching between projects

### Commander Architecture

- **`state.py`**: Atomic state management with crash recovery
- **`locking.py`**: Concurrency control (Controller/Observer mode)
- **`reconcile.py`**: Git-first synchronization (prevents split-brain)
- **`cockpit.py`**: Interactive display of current state
- **`rules.py`**: Rule engine for computing next actions

### Core Concepts

#### 1. State Management

Commander maintains persistent state in `~/.cloud-harness/state.json`:
- **Projects**: Repositories you're working on
- **Runs**: Individual worktrees/branches
- **Tasks**: Work items linked to projects
- **Inbox**: Quick-capture ideas for later processing
- **Focus Project**: The currently active project

#### 2. Controller vs Observer Mode

- **Controller Mode**: Exclusive write access (one session at a time)
- **Observer Mode**: Read-only access when another controller is active

The lock system prevents concurrent mutations using:
- PID liveness checks (is the process still running?)
- Heartbeat freshness checks (updated every 60s)
- Atomic file locking (flock/O_EXCL)

#### 3. Git-First Reconciliation

Commander automatically syncs state with Git reality:
- Runs `git worktree list` to detect missing worktrees
- Parks runs with missing worktrees (state: "parked")
- Updates branch names if they've changed
- Refuses mutations on dirty working trees

**Key Principle**: Git is the source of truth. State is derived, not authoritative.

### Commander Workflows

#### Initial Setup

```bash
# Run pre-flight checks
c-harness doctor

# Start interactive session
c-harness session
```

#### Daily Workflow

```bash
# 1. Check status
c-harness status
# Output: Controller | focus: my-project | run: BUG-123 | state: 5 runs, 12 tasks

# 2. See next action
c-harness next
# Output: Next Action, Why, Done Criteria

# 3. Start focused work session
c-harness session
# Displays cockpit with all your projects, runs, and tasks
```

#### Quick Capture (Inbox)

```bash
# Capture idea without interrupting work
c-harness inbox "Remember to add error handling to API"

# Review and process inbox later
c-harness inbox --list
c-harness inbox --promote <id>  # Convert to task
```

#### Focus Management

```bash
# View current focus
c-harness focus

# Switch focus project (requires confirmation)
c-harness focus set <project-id>
```

### Example Agent Workflow with Commander

As an autonomous agent, you should integrate Commander into your workflow:

1. **Session Start**: Run `c-harness session` to get controller lock
2. **Read Cockpit**: Understand current state and priorities
3. **Follow Next Action**: Use `c-harness next` to determine what to work on
4. **Execute Work**: Use standard `c-harness start/run/finish` commands
5. **Auto-Reconcile**: Commander syncs state with Git after each operation
6. **Capture Ideas**: Use `c-harness inbox` for thoughts that don't fit current task
7. **Session End**: Ctrl+C releases controller lock automatically

### Commander State Schema

State is stored in `~/.cloud-harness/state.json`:

```json
{
  "focusProjectId": "uuid-1234",
  "projects": [
    {
      "id": "uuid",
      "name": "my-app",
      "repoPath": "/path/to/repo",
      "status": "active",
      "lastTouchedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "runs": [
    {
      "id": "uuid",
      "projectId": "uuid",
      "runName": "BUG-123",
      "state": "running",
      "worktreePath": "/path/to/worktree",
      "branchName": "run/BUG-123",
      "lastTouchedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "tasks": [
    {
      "id": "uuid",
      "projectId": "uuid",
      "title": "Fix login bug",
      "column": "doing",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  ],
  "inbox": [
    {
      "id": "uuid",
      "text": "Add unit tests for auth module",
      "createdAt": "2024-01-15T10:30:00Z",
      "triageStatus": null
    }
  ]
}
```

### Important: Commander vs Core Harness

- **Core Harness** (`start/run/finish`): Manages individual agent runs
- **Commander** (`session/status/next`): Orchestrates across multiple runs/projects

You can use core harness commands WITHOUT Commander, but Commander adds:
- Multi-project coordination
- Persistent state tracking
- Intelligent next-action recommendations
- Quick capture inbox system
- Concurrency safety for multiple sessions

### Phase 1 Limitations

Current Commander implementation (Phase 1):
- ✅ Git-based state management
- ✅ Local concurrency control
- ✅ Interactive cockpit display
- ✅ Rule engine for next actions
- ⏳ No cloud sync (Convex integration planned for Phase 2)
- ⏳ No external task integrations (Jira, GitHub Issues, etc.)
