# Using c-harness with Claude.ai (Manual Agent Mode)

This guide explains how to use c-harness when working interactively with Claude.ai instead of the Claude Code CLI.

## Overview

c-harness is designed to work with both:
- **Automated mode**: `c-harness run` invokes Claude Code CLI as the agent
- **Manual mode**: You work with Claude.ai (web/app) and use c-harness for Git workflow management

This guide covers the **manual mode** workflow.

## When to Use Manual Mode

Use manual mode when:
- You're working with Claude.ai (web interface or app)
- You prefer interactive conversation with Claude
- You want to review and approve changes as you go
- You're using Claude.ai with MCP tools for file editing

## Workflow Steps

### 1. Create Your Handoff

Create a `handoff.json` file describing the tasks:

```json
{
  "meta": {
    "project": "my-project",
    "phase": "Bug Fixes",
    "source": "GitHub Issue #42",
    "lock": true
  },
  "tasks": [
    {
      "id": "BUG-042",
      "category": "functional",
      "title": "Fix login timeout",
      "description": "Login times out after 30 seconds. Increase to 60 seconds.",
      "acceptance_criteria": [
        "Login timeout is 60 seconds",
        "Existing tests pass"
      ],
      "passes": false,
      "files_expected": ["src/auth/login.ts"],
      "steps": ["Update timeout constant", "Run tests"]
    }
  ]
}
```

### 2. Start the Run

```bash
c-harness start BUG-042 \
  --repo-path /path/to/your-project \
  --mode brownfield \
  --handoff-path ./handoff.json
```

This creates:
- An isolated worktree at `runs/BUG-042/`
- A branch `run/BUG-042`
- A copy of `handoff.json` in the run directory

### 3. Share Context with Claude.ai

Tell Claude.ai:
- The path to your worktree: `runs/BUG-042/`
- The tasks from your handoff.json
- Any relevant context about your codebase

Example prompt:
```
I'm working on a bug fix. Here's my setup:
- Worktree: /path/to/harness/runs/BUG-042/
- Task: Fix login timeout (increase from 30s to 60s)
- File to modify: src/auth/login.ts

Please help me make this change.
```

### 4. Make Changes

Work with Claude.ai to:
- Explore the codebase
- Make the necessary code changes
- Commit your work

If Claude.ai has MCP file tools (Desktop Commander, etc.), it can edit files directly. Otherwise, copy/paste code changes manually.

### 5. Commit Changes

In the worktree directory:
```bash
cd runs/BUG-042
git add -A
git commit -m "BUG-042: Fix login timeout - increase to 60 seconds"
```

### 6. Update Handoff Status

Edit `runs/BUG-042/handoff.json` and mark completed tasks:
```json
{
  "id": "BUG-042",
  ...
  "passes": true  // Changed from false
}
```

### 7. Finish and Push

```bash
c-harness finish BUG-042
```

This will:
- Verify all tasks are marked as passing
- Check for documentation drift
- Push the branch to origin
- Provide a PR link

## Tips for Claude.ai Users

### Sharing File Paths

When working with Claude.ai, always use absolute paths:
```
The file is at: /Users/you/tools/harness/runs/BUG-042/src/auth/login.ts
```

### Multiple Tasks

For multiple tasks, work through them one at a time:
1. Complete task, commit
2. Mark as `passes: true`
3. Move to next task
4. Repeat until all done

### Using MCP Tools

If you have MCP file tools configured with Claude.ai:
- Claude can read/write files directly in the worktree
- Claude can run git commands
- Claude can verify changes before you commit

### Reviewing Changes

Before finishing:
```bash
cd runs/BUG-042
git diff main..HEAD  # See all changes
git log --oneline    # See commits
```

## Command Reference

| Command | Purpose |
|---------|---------|
| `c-harness start <name> --handoff-path <path>` | Create worktree and copy handoff |
| `c-harness list` | See active runs |
| `c-harness finish <name>` | Validate and push |
| `c-harness clean <name>` | Remove worktree |

## Skipping `c-harness run`

In manual mode, you skip the `c-harness run` command entirely. That command invokes the Claude Code CLI agent, which isn't needed when you're working interactively with Claude.ai.

Your workflow is:
```
start → [manual work with Claude.ai] → finish
```

Not:
```
start → run → finish
```
