# Project Roadmap

This document outlines the future development phases and planned improvements for `claude-harness`.

## Phase 4: UI Capabilities (Complete)
**Goal:** Verify the agent's ability to interact with web interfaces.
- [x] **Browser Automation:** Migrated from `puppeteer-mcp-server` to `chrome-devtools-mcp` (official, actively maintained).
- [x] **UI Tests:** Created `tests/test_ui_capabilities.py` to verify Chrome DevTools MCP integration.
    - Verifies package availability
    - Verifies tool configuration in client.py
    - *Note:* Full browser tests require Chrome and are primarily for manual verification.

## Phase 5: Schema Hardening (Planned)
**Goal:** Improve data integrity for the `handoff.json` format.
- [ ] **Enforce Meta Block:** Update `schema.py` to make the `meta` block mandatory for dictionary-based handoff files.
    - *Current behavior:* Missing meta defaults to `project="Unknown"`.
    - *Target behavior:* Raise `ValidationError` if meta is missing (fail fast).
    - *Note:* Legacy list-based handoff files will continue to be supported.

## Phase 6: Harness Commander (Complete ✅)
**Goal:** Implement the "ADHD-First" Control Plane.
- [x] **Implement `c-harness session`:** The interactive "Cockpit" UI.
- [x] **Implement Registry & Locking:** Single-controller enforcement via `~/.cloud-harness/locks`.
- [x] **Implement "Reconcile Reality":** Logic to sync the registry with Git state.
- [x] **Comprehensive Testing:** Unit and integration tests for all Commander components.
- [x] **Documentation:** README and AGENT_GUIDE updated with Commander workflows.
- **See Specification:** `docs/final_handoff_v_4_harness_commander.md` for full implementation details.
