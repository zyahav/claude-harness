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

- **`harness.py`**: The CLI entry point. YOU CALL THIS.
- **`lifecycle.py`**: Git worktree and branch management.
- **`schema.py`**: The validator for `handoff.json`. **Note:** Uses Python `dataclasses` (Standard Library) for dependency-free validation. Not Pydantic.

## 3. Standard Operating Procedures

### A. Start a New Task (The "Clone & Branch" equivalent)

Command:
```bash
python3 harness.py start <task-name> --repo-path <path/to/target-repo>
```
- **Effect:** Creates a new git worktree in `runs/<task-name>` and a branch `run/<task-name>` in the target repo.
- **Output:** Returns the path to the NEW worktree.
- **Next Step:** Do your work inside that new worktree path.

### B. Execute Agent Loop (Optional)

Command:
```bash
python3 harness.py run <task-name> --repo-path <path/to/target-repo>
```
- **Effect:** Runs the automated agent loop (if configured). Usually, you (the LLM) *are* the agent, so you might skip this and just edit files directly in the worktree.

### C. Finish & Handoff (Critical)

Command:
```bash
python3 harness.py finish <task-name> --repo-path <path/to/target-repo> --handoff-path <path/to/handoff.json>
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
