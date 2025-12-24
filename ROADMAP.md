# Project Roadmap

This document outlines the future development phases and planned improvements for `claude-harness`.

## Phase 4: UI Capabilities (Planned)
**Goal:** Verify the agent's ability to interact with web interfaces.
- [ ] **Restore UI Tests:** Create `tests/test_ui_capabilities.py` to verify the Puppeteer MCP integration.
    - Launch a local test server.
    - Verify agent can navigate, click, and take screenshots.
    - *Rationale:* The infrastructure exists in `client.py`, but automated verification is currently missing.

## Phase 5: Schema Hardening (Planned)
**Goal:** Improve data integrity for the `handoff.json` format.
- [ ] **Enforce Meta Block:** Update `schema.py` to make the `meta` block mandatory for dictionary-based handoff files.
    - *Current behavior:* Missing meta defaults to `project="Unknown"`.
    - *Target behavior:* Raise `ValidationError` if meta is missing (fail fast).
    - *Note:* Legacy list-based handoff files will continue to be supported.

## Phase 6: Harness Commander (Approved)
**Goal:** Implement the "ADHD-First" Control Plane.
- [ ] **Implement `c-harness session`:** The interactive "Cockpit" UI.
- [ ] **Implement Registry & Locking:** Single-controller enforcement via `~/.cloud-harness/locks`.
- [ ] **Implement "Reconcile Reality":** Logic to sync the registry with Git state.
- [ ] **See Specification:** `docs/HARNESS_COMMANDER_SPEC.md` for full implementation details.
