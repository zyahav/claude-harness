# BOSS APPROVAL — FINAL HANDOFF v4

## Harness Commander (ADHD-First Control Plane) — Dev Team Build Instructions

**Date:** 2025-12-24  
**Version:** v4 (with engineer-level hardening)

---

## 0) Executive Summary (Read this first)

We will ship a new **Commander layer** inside the **Cloud Harness** repository.

* **Cloud Harness (`c-harness`) stays standalone** and unchanged in principle: `start/list/run/finish/clean` must work without Commander.
* **Harness Commander** is an optional—but default-friendly—ADHD-first operator UI on top of the engine:

  * `session / next / focus / inbox / doctor / bootstrap / status`

**Product Promise:** **Trust > Intelligence.**
Commander must be reliable even with weaker models. Determinism + guardrails + verification > "smartness."

---

## 1) Problem

With agents + worktrees + multiple projects, teams fail due to **state chaos**:

* unclear "what's running"
* accidental parallel mutations
* drift between cached state and actual Git reality
* open loops (unfinished runs, uncleaned worktrees)

For ADHD users this becomes anxiety, decision paralysis, and abandonment.

---

## 2) Solution Overview

### 2.1 Two Layers (Same Repo)

**Layer A — Engine (existing)**

* `c-harness start | list | run | finish | clean`

**Layer B — Commander (new)**

* `c-harness session` → ADHD cockpit + controller/observer role
* `c-harness next` → one next action only
* `c-harness focus` → enforce one focus project
* `c-harness inbox` → capture + list + promote + dismiss
* `c-harness doctor` → pre-flight checks + optional repair
* `c-harness bootstrap` → install / update discovery & proposal
* `c-harness status` → one-line status for scripts/prompts

Commander **wraps** the engine; it does not replace lifecycle logic.

---

## 3) Non-Negotiables (Boss Approval Criteria)

### 3.1 Trust Contract (Deterministic Pipeline)

All mutating actions must run as:

1. **Plan** — exact command and expected post-conditions
2. **Execute**
3. **Verify** — check post-conditions
4. **Commit** — update state + append audit event

If verification fails, Commander must **not** mark success.

### 3.2 ADHD Output Rule

Every Commander interaction must end with:

* **NEXT ACTION (single)**
* **WHY (one line)**
* **DONE CRITERIA (one line)**

### 3.3 Single Controller / Many Observers (Phase 1)

Only one session can execute mutations at a time.
All others are observer (read-only).

### 3.4 Git-First "Reconcile Reality"

Git/worktrees are the source of truth.
Commander must detect drift and either adopt reality or prompt the user.

### 3.5 No Generic Shell Tool

Do not expose `runShell(command)` to any LLM wrapper.
Only whitelisted verbs.

---

## 4) Phase 1 Target: Local MVP (Ship this first)

### 4.1 What "Working" means

A developer can:

* run `c-harness session` and see a cockpit
* run `c-harness next` and get one next step
* capture ideas via `c-harness inbox "…"`
* never accidentally operate from two controller sessions
* recover cleanly after crashes

**No Convex required in Phase 1.** (Convex is Phase 2.)

---

## 5) Local State & Logging

### 5.1 Locations

Use a single home:

* `~/.cloud-harness/`

Suggested structure:

* `~/.cloud-harness/state.json` (registry)
* `~/.cloud-harness/events.log` (append-only JSON lines)
* `~/.cloud-harness/locks/commander.lock`
* `~/.cloud-harness/locks/commander.heartbeat`

### 5.2 State schema (minimal)

`state.json` must include:

* `focusProjectId`
* `projects[]`: `{ id, name, repoPath, status, lastTouchedAt }`
* `runs[]`: `{ id, projectId, runName, state, worktreePath, branchName, lastCommand, lastResult }`
* `tasks[]`: `{ id, projectId, title, column, createdAt }`
* `inbox[]`: `{ id, text, createdAt, triageStatus? }`

Keep schema forward-compatible (Phase 2 Convex).

**ID Generation:** Use UUID v4 for all `id` fields (projects, runs, tasks, inbox items).

### 5.2.1 Atomic State Writes (CRITICAL)

All writes to `state.json` must be **atomic**:

1. Write to temp file: `state.json.tmp`
2. `fsync` the temp file (flush to disk)
3. Rename `state.json.tmp` → `state.json` (atomic on POSIX)

**Never:**
* Write directly to `state.json`
* Use partial/incremental writes

**Recovery:** If `state.json.tmp` exists on startup, delete it (incomplete write from prior crash).

### 5.3 Events (append-only)

Write one JSON line per event:

* `SESSION_STARTED`
* `SESSION_ENDED`
* `LOCK_ACQUIRED / LOCK_DENIED / LOCK_RELEASED / LOCK_STALE_TAKEOVER`
* `RECONCILE_START / RECONCILE_RESULT`
* `COMMAND_PLAN / COMMAND_EXECUTE / COMMAND_VERIFY_OK / COMMAND_VERIFY_FAIL`
* `STATE_UPDATED`

---

## 6) Concurrency Control (Local)

### 6.1 Controller Lock File

Lock file: `~/.cloud-harness/locks/commander.lock`

Contents:

```json
{
  "pid": 12345,
  "startTime": "2025-12-24T10:30:00Z",
  "sessionId": "uuid-v4-here"
}
```

**Requirement:** Acquisition must be **ATOMIC** (use `flock` or `O_EXCL` mode). Two sessions must never believe they both hold the lock.

### 6.2 Liveness Check (Crash-proof)

If lock exists, check `pid`:

* **Case A: PID Dead** → Lock is **stale**.
  * Action: Allow immediate auto-takeover.
  * Log: `LOCK_STALE_TAKEOVER (PID_DEAD)`

* **Case B: PID Alive** → Check heartbeat (Section 6.3).

### 6.3 Heartbeat (Hung-process protection)

PID running is not enough (process can hang).

**Heartbeat file:** `~/.cloud-harness/locks/commander.heartbeat`

**Contents** (not just mtime):

```json
{
  "sessionId": "uuid-v4-matching-lock",
  "lastBeatAt": "2025-12-24T10:35:00Z"
}
```

**Update frequency:** Controller updates heartbeat every **60 seconds** (only during **Interactive Session** via `c-harness session`).

**Short-lived commands** (`next`, `status`, `inbox`) do **not** maintain a heartbeat loop.

**Stale detection:**

If lock exists AND PID is alive:
* Read `commander.heartbeat`
* If `sessionId` ≠ lock's `sessionId` → inconsistent state → require `--force-takeover`
* If `lastBeatAt` > **5 minutes ago** → Lock is **stale**
  * Action: **Prompt user** to confirm takeover (safety first)
  * Log: `LOCK_STALE_TAKEOVER (HEARTBEAT_TIMEOUT)`

### 6.4 Modes

* If lock acquired → **Controller mode**
* If lock denied → **Observer mode**

  * still allowed: status/cockpit read, inbox capture, list
  * not allowed: start/finish/clean mutations

### 6.5 Lock Release (CRITICAL)

**On normal exit:**
* Commander must delete `commander.lock` and `commander.heartbeat` before process termination.
* Use `atexit` handler or `try/finally` block.
* Log: `LOCK_RELEASED`

**On crash recovery takeover:**
* New controller must **overwrite** lock atomically (not delete-then-create, which has a race window).

**Release triggers:**
* `session` command exits (user quits or Ctrl+C)
* Any fatal error that terminates Commander

**Never release on:**
* Short-lived commands (`status`, `next`, `inbox`) — these don't hold the lock long-term

---

## 7) Reconcile Reality (Most Critical Code)

### 7.1 Trigger Policy

Reconcile runs on:

* `session`, `next`, `focus`, `doctor --repair-state`, and before any mutating command

### 7.2 Caching

To avoid expensive git ops:

* cache reconcile results for **30 seconds**
* still re-run immediately if a command mutates worktrees/runs

### 7.3 Truth Source

Git/worktrees override registry.
Commander must adopt reality.

### 7.4 Required checks

On reconcile:

* `git status` (clean/dirty)
* `git worktree list`
* `c-harness list`

### 7.5 Drift handling rules

* registry references missing worktree → mark run `missing`, park it
* user checked out a different branch manually → prompt: "Adopt current branch/worktree as focus?"
* unresolved mismatch → Commander stays Observer until reconciled

### 7.5.1 Dirty Working Tree Policy (CRITICAL)

If `git status` shows uncommitted changes in the focus project or active worktree:

* **Mutating commands** (`start`, `finish`, `clean`) → **REFUSE**
  * Output: `"Working tree is dirty. Commit or stash changes first."`
* **Read-only commands** (`status`, `next`, `session`, `inbox`) → **ALLOW** but show warning:
  * Output: `"Warning: Working tree has uncommitted changes."`

**Rationale:** Trust-first. Never silently operate on uncommitted work.

### 7.6 Worktree Path Safety (CRITICAL)

Before any destructive operation on a worktree path:

1. **Normalize path**: Resolve symlinks, use `realpath`
2. **Allowlist check**: Path must be either:
   * Under a registered project's `repoPath`
   * In the harness worktree directory (e.g., `~/.cloud-harness/worktrees/`)
3. **Marker check**: Directory must contain `.harness-worktree` marker file (created by `start`)

If any check fails → **REFUSE** with explicit error:
* Output: `"Refusing to delete: path is not a harness-managed worktree."`

**Never delete a path that fails these checks.**

---

## 8) Commander Commands (Phase 1)

### 8.1 `c-harness status` (one-liner)

Output example:
```
Controller | focus: my-project | run: feature-x | state: executing
```

Observer mode:
```
Observer | focus: my-project | run: feature-x | state: executing | controller: PID 12345
```

### 8.2 `c-harness session` (home base)

* runs `doctor` preflight
* runs reconcile
* acquires controller lock (or becomes observer)
* starts heartbeat loop (60s interval)
* prints cockpit + next action

Cockpit sections (compact):

* Focus Now
* In Preview
* Blocked
* Active Runs
* Inbox count

Ends with:

* Next Action / Why / Done

### 8.3 `c-harness next`

* reconcile (cached)
* computes **one** next step using rule engine (below)

### 8.4 `c-harness focus set <projectId|name>`

* reconcile
* requires confirmation if switching from current focus

### 8.5 `c-harness inbox`

Must support:

* `c-harness inbox "text"` (or: `c-harness inbox add "text"`)
* `c-harness inbox list`
* `c-harness inbox promote <id>` → creates a **Task** in `state.json` linked to focus project
* `c-harness inbox dismiss <id>`

**Capture must be fire-and-forget**: no follow-up questions.

### 8.6 `c-harness doctor`

Runs these checks in order:

| Check | Pass condition | Fail action |
|-------|----------------|-------------|
| Git installed | `git --version` exits 0 | Error: "Git not found" |
| Git version | ≥ 2.20 (worktree support) | Warning: "Git version may lack worktree features" |
| Home dir exists | `~/.cloud-harness/` exists | Auto-create |
| Home dir writable | Can create temp file | Error: "Cannot write to ~/.cloud-harness/" |
| Lock dir exists | `~/.cloud-harness/locks/` exists | Auto-create |
| State file valid | `state.json` parses as valid JSON | Error + offer `--repair-state` |
| State file not corrupted | No `state.json.tmp` present | Warning: "Incomplete write detected" + auto-cleanup |
| Engine available | `c-harness list` exits 0 | Error: "Cloud Harness engine not found" |
| Focus project exists | If `focusProjectId` set, path exists | Warning: "Focus project path missing" |

**Output format:**
```
[✓] Git installed (2.39.0)
[✓] Home directory
[✓] Lock directory  
[✓] State file valid
[✓] Engine available
[!] Focus project path missing — run `focus set` to fix

Status: 5 passed, 1 warning, 0 errors
```

**`doctor --repair-state`:**
* Runs reconcile
* Fixes: missing worktree → park run, orphaned inbox items → keep, stale tmp file → delete
* Never deletes user data automatically

### 8.7 `c-harness bootstrap`

* checks if harness installed/available
* if missing, prints exact install steps (never silently installs)
* if update available, **notify + propose** (never auto-update)
* update requires explicit: `bootstrap --apply`

---

## 9) "Next Action" Rule Engine (Phase 1)

Commander chooses the smallest loop-closing step.

Priority order:

1. Finished run not cleaned → suggest `clean`
2. Active run missing verification/test step → suggest tests
3. Run ready to finish → suggest `finish`
4. No focus project → suggest focus selection
5. No runs in focus project → suggest `start`
6. Otherwise → suggest the next smallest defined task (if tasks exist)

Output must always end with:

* Next Action / Why / Done

---

## 10) Guardrails (for future LLM wrappers)

Even if wrapped by GPT/Gem/Claude:

* Commander is the only executor.
* LLM sessions can be many, but only one controller lock can mutate.
* No generic shell tool.
* Only whitelisted verbs.

### 10.1 Explicit Mutating Commands

These commands require Controller mode and follow Plan → Execute → Verify → Commit:

* `start`
* `finish`
* `clean`
* `focus set`
* `inbox promote`
* `inbox dismiss`

All other commands are read-only and allowed in Observer mode.

---

## 11) Testing & Simulation (Phase 1)

### 11.1 Concurrency

1. start two sessions in two terminals → exactly one controller
2. kill controller process → new session detects stale PID and takes over
3. simulate hang (stop heartbeat updates) → new session takeover after 5 minutes
4. simultaneous lock attempt → one wins atomically, other becomes observer

### 11.2 Reconcile

1. delete worktree manually → run marked missing, parked
2. checkout branch manually → prompt to adopt reality
3. dirty working tree + mutating command → refused with clear message

### 11.3 Verification

* after start: worktree exists + listed + `.harness-worktree` marker present
* after finish: branch pushed + state updated
* after clean: worktree removed + state updated + marker gone

### 11.4 State Safety

1. kill process mid-write → `state.json.tmp` exists, `state.json` intact
2. restart after crash → tmp file cleaned, state recovered
3. corrupt `state.json` → doctor detects, offers repair

---

## 12) Phase 2 (After Phase 1 proves daily trust)

Add Convex for:

* shared state across devices
* distributed leases + heartbeat
* Kanban UI (ToDo/Doing/Preview/Blocked/Done)

Do not start Phase 2 until Phase 1 is trusted daily.

---

## 13) Definition of Done (Boss Approval)

Phase 1 is done when:

* `session/next/status/focus/inbox/doctor` work end-to-end
* single controller is enforced with crash + hang recovery
* lock release is clean on normal exit
* state writes are atomic (no corruption on crash)
* dirty tree policy prevents unsafe mutations
* worktree paths are validated before deletion
* reconcile is Git-first and prevents "split brain"
* every mutating step is verified and logged
* inbox capture is usable (list/promote/dismiss)
* doctor has explicit checklist with pass/fail output

---

## 14) Boss Decision Request

Approve Phase 1 Local MVP with these non-negotiables:

* Single controller + observers
* PID liveness + heartbeat stale detection (with sessionId)
* Lock release on exit + atomic takeover
* Atomic state.json writes (temp + rename)
* Dirty working tree policy (refuse mutations)
* Worktree path safety (normalize + allowlist + marker)
* Git-first reconcile on every command (cached 30s)
* Doctor with explicit checklist
* Inbox lifecycle commands
* `status` one-liner
* Plan → Execute → Verify → Commit

Once Phase 1 is trusted, proceed to Convex + Kanban.

---

## Appendix: v3 → v4 Changes

| Section | Change |
|---------|--------|
| 5.2.1 | Added: Atomic state writes |
| 6.3 | Modified: Heartbeat now contains sessionId, not just mtime |
| 6.5 | Added: Lock release rules |
| 7.5.1 | Added: Dirty working tree policy |
| 7.6 | Added: Worktree path safety |
| 8.6 | Replaced: Doctor now has explicit checklist table |
| 10.1 | Added: Explicit mutating commands list |
| 11.4 | Added: State safety tests |
| 13 | Expanded: Definition of Done includes new items |
| 14 | Expanded: Boss Decision Request includes new items |



FROM THE CHAT>>>https://chatgpt.com/c/694c21af-49bc-8330-b489-67211ea3c6f5

FROM TEST CHAT CLAUDE >>> https://docs.google.com/document/d/1z8Kv6MutYhNpZeAtxjS4ocH9U1wDipZsswmqJCMk_jY/edit?tab=t.0


FRONTEND PAGE >>>https://aistudio.google.com/apps/drive/1vAMp9b3xvpwEgnGLpz7r7euo4Tsx9j7U?source=start&showAssistant=true&showPreview=true&resourceKey=&fullscreenApplet=true
