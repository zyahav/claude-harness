# Testing Strategy & Implementation Plan

## Overview
We will implement a permanent, automated test suite using Python's standard `unittest` framework. This ensures `harness-lab` remains stable, reliable, and regression-free.

## Directory Structure
We will create a `tests/` directory with the following structure:
```text
tests/
├── __init__.py          # Makes the directory a package
├── test_schema.py       # Validates JSON contracts
├── test_lifecycle.py    # Validates Git worktree operations (isolated)
├── test_cli.py          # Validates command-line interface entry points
└── test_agent.py        # Validates agent logic (using Mocks)
```

## Detailed Test List

### 1. `tests/test_schema.py`
**Goal:** Ensure `handoff.json` and other metadata files are parsed and validated correctly.
*   [ ] **test_valid_handoff**: Load a perfect `handoff.json` and verify `count_passing()` returns correct numbers.
*   [ ] **test_invalid_json**: Load a malformed file and ensure it raises a `JSONDecodeError` or handled exception.
*   [ ] **test_missing_fields**: Load a JSON missing required fields (e.g., `tasks`) and verify schema validation fails.
*   [ ] **test_task_status_parsing**: Verify that `[ ]`, `[/]`, and `[x]` are correctly parsed into status enums.

### 2. `tests/test_lifecycle.py`
**Goal:** specific Git operations without touching the user's actual `runs/` folder.
*   *Mechanism:* Each test `setUp` creates a temporary directory and initializes a bare Git repo to act as "remote", then runs tests against that.
*   [ ] **test_create_run_success**: Verify `create_run` creates a new folder strings and a new git branch.
*   [ ] **test_create_duplicate_run**: Verify `create_run` raises `FileExistsError` if run name exists.
*   [ ] **test_list_runs**: Create 2 dummy runs and verify `list_runs` returns them sorted by date.
*   [ ] **test_cleanup_run**: Verify `cleanup_run` removes the directory and prunes the git worktree.
*   [ ] **test_finish_run_check**: Verify `handle_finish` fails if `handoff.json` is missing tasks.

### 3. `tests/test_cli.py`
**Goal:** Ensure the `harness.py` dispatcher works.
*   [ ] **test_help**: Run `harness.py --help` and verify exit code 0.
*   [ ] **test_start_command**: subprocess call `harness.py start <name>` and verify stdout contains "Success".
*   [ ] **test_invalid_command**: Run `harness.py bananarama` and verify it prints usage/error.

### 4. `tests/test_agent.py` (Mocked)
**Goal:** Verify the `run_autonomous_agent` loop handles lifecycle correctly without calling Anthropic API.
*   *Mechanism:* Mock the `ClaudeSDKClient`.
*   [ ] **test_agent_loop_explicit_stop**:
    *   Setup: Mock client returns "continue" then "stop".
    *   Verify: Loop runs exactly twice.
*   [ ] **test_agent_handles_error**:
    *   Setup: Mock client throws exception on first call.
    *   Verify: Agent catches error, sleeps, and retries (or exits depending on logic).
*   [ ] **test_init_first_run**:
    *   Setup: No `handoff.json` exists.
    *   Verify: Agent uses `get_initializer_prompt`.
*   [ ] **test_resume_run**:
    *   Setup: `handoff.json` exists.
    *   Verify: Agent uses `get_coding_prompt`.

## How to Run
```bash
python3 -m unittest discover tests
```
Output should be a series of dots (`.......`) followed by `OK`.
