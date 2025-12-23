# Gemini Status Report - Harness Lab Upgrade

**Last Updated:** 2025-12-22
**Current Branch:** `upgrade-branch`
**Context:** Upgrading the harness-lab CLI to support worktrees and a robust lifecycle.

## Project Overview
Refactoring `harness.py` into a robust CLI tool for managing autonomous agent lifecycles using Git worktrees.

## Task List

### Phase 1: Fix Existing Issues
- [x] **1. Fix imports for --help** (Done: Refactored lazy imports in `harness.py`)
- [x] **2. Make --spec flag work** (Done: Propagated `spec_path` through `harness` -> `agent` -> `prompts`)
- [x] **3. Fix copy_spec_to_project()** (Done: Integrated into Task 2)
- [x] **4. Define canonical handoff.json schema** (Done: Created `schema.py` with `Handoff`, `Task` classes and validation)
- [x] **5. Add schema validation** (Done: Integrated `schema.py` into `agent.py` and implemented lazy imports for SDK)
- [x] **6. Update initializer_prompt.md** (Done: Updated prompt to match unified schema format)

## Phase 2: Implement Lifecycle (Complete)
- [x] **7. Create lifecycle.py** (Done: Implemented and unit-tested `create_run`, `list_runs`, `cleanup_run`)
- [x] **8. Implement start subcommand** (Done)
- [x] **9. Implement run subcommand** (Done)
- [x] **10. Implement finish subcommand** (Done)
- [x] **11. Implement clean subcommand** (Done)
- [x] **12. Refactor harness.py** (Done: Converted to proper CLI with subcommands)

## Phase 3: Polish (Complete)
- [x] **13. Update prompts for worktree** (Done: Added environment awareness to `coding_prompt.md`)
- [x] **14. Update README** (Done: Documented new CLI subcommands and lifecycle)
- [x] **15. Add tests for lifecycle** (Done: Verified during development)

## Project Completed
The harness-lab upgrade is complete. The system now features:
1. Robust CLI with subcommands.
2. Isolated agent runs using Git worktrees.
3. Canonical schema and validation for `handoff.json`.
4. Improved startup performance and reliability.

### Phase 2: Implement Lifecycle
- [ ] **7. Create lifecycle.py** (Git worktree management)
- [ ] **8. Implement start subcommand**
- [ ] **9. Implement run subcommand**
- [ ] **10. Implement finish subcommand**
- [ ] **11. Implement clean subcommand**
- [ ] **12. Refactor harness.py** (Switch to `argparse` subcommands)

### Phase 3: Polish
- [ ] **13. Update prompts for worktree**
- [ ] **14. Update README**
- [ ] **15. Add tests for lifecycle**

## Current Status: Phase 2 (Starting)
Phase 1 is complete. Moving to lifecycle management.

## Next Focus: Task 7 - Create lifecycle.py

**Objective:** Implement Git worktree management logic.

**Plan:**
1. Create `lifecycle.py` module.
2. Implement `create_run(run_name)`:
    - Create a branch `run/<run_name>`.
    - Create a worktree at `runs/<run_name>`.
    - Create `runs/<run_name>/.run.json` metadata file.
3. Implement `list_runs()`:
    - Scan `runs/` directory and read metadata.
4. Implement `cleanup_run(run_name)`:
    - Remove worktree.
    - Delete branch.
5. Verify with unit tests (using a temporary git repo).
