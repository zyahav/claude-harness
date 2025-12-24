# FINAL HANDOFF (Boss Approval)

## Harness Commander — ADHD‑First Control Plane (inside Cloud Harness repo)

**Date:** 2025‑12‑24

---

## 0) Executive Summary

We are adding a new **Commander layer** inside the Cloud Harness repository to solve the real bottleneck for agent-driven development: **trust, focus, and concurrency**.

* **Cloud Harness (`c-harness`) remains fully standalone**: `start/list/run/finish/clean` continue to work without Commander.
* **Harness Commander is optional but default-friendly**: `session/focus/next/inbox/doctor/bootstrap` adds an ADHD‑first “steering wheel” on top of the existing engine.

**Core Product Promise:** *Trust > Intelligence.*
We will build a deterministic manager that is reliable even with weaker models.

---

## 1) Problem

When using agents + worktrees + multiple projects, the failure mode is not capability — it’s **state chaos**:

* “What’s running?”
* “What’s in preview?”
* “Where was I?”
* “Did I start two runs by mistake?”
* “Why is the repo drifting from what I think?”

For ADHD users this becomes anxiety, decision paralysis, and unfinished loops.

---

## 2) Solution

### 2.1 Two Layers (Same Repo)

**Layer A — Engine (existing / stable)**

* `c-harness start | list | run | finish | clean`

**Layer B — Commander (new / ADHD-first)**

* `c-harness session` (home base / cockpit)
* `c-harness focus` (enforced single focus project)
* `c-harness next` (returns exactly one next action)
* `c-harness inbox` (fire‑and‑forget capture)
* `c-harness doctor` (pre‑flight checks)
* `c-harness bootstrap` (install/update discovery & proposal)

Commander wraps the engine; it does **not** rewrite the lifecycle logic.

---

## 3) Operating Model (Trust Contract)

### 3.1 Deterministic Pipeline

Every mutating step follows:

1. **Plan** (exact command + expected outcomes)
2. **Execute**
3. **Verify** (post‑conditions)
4. **Commit** (update state + append audit event)

If verification fails → do not mark success.

### 3.2 ADHD Cockpit Output Rule

Every interaction ends with:

* **NEXT ACTION (single)**
* **WHY (one line)**
* **DONE CRITERIA (one line)**

No wall of text. No decision overload.

### 3.3 Focus Lock (ADHD Killer Feature)

* Only **one Focus Project** (and one Focus Run) in the workspace by default.
* Switching focus requires explicit confirmation.

### 3.4 Loop Closure

* If a run is finished but not cleaned, Commander nudges closure.

---

## 4) Concurrency: Single Controller / Many Observers

### 4.1 Roles

* **Controller**: only entity allowed to execute lifecycle mutations.
* **Observer**: read-only; can view status, propose next steps, capture inbox.
* **Workers/Sub‑agents (Phase 3)**: proposal‑only; cannot execute.

### 4.2 Why

Trust is destroyed when two sessions mutate state concurrently.

### 4.3 Phase 1 Locking (Local MVP)

* **Global local lock**: `~/.cloud-harness/locks/commander.lock`
* Contains PID + start time.
* **Must verify process liveness**: if lock file exists, check whether PID is currently running (and optionally matches expected start time/command). If PID is not alive → treat lock as **stale** and allow safe takeover (log a crash/stale-lock event).
* If a second session starts, it becomes Observer mode and shows who holds control.

### 4.4 Phase 2 Locking (Distributed — Convex)

* Add **lease + heartbeat** in Convex to support multi-device.
* Local lock remains for filesystem operations.

### 4.5 Takeover / Crash Recovery

* Locks are **leases** with heartbeat.
* If heartbeat stale → offer explicit takeover (`--force-takeover`) and log a “death event”.

---

## 5) “Reconcile Reality” (Most Critical MVP Code)

### 5.1 The Split‑Brain Risk

Local/DB registry can drift from filesystem truth.

### 5.2 Rule

**Git/worktrees are the source of truth**. Commander must adopt reality.

### 5.3 Reconcile Rules (MVP)

On `c-harness session`:

1. Read:

   * `git status` on focus repo
   * `git worktree list`
   * `c-harness list`
2. Compare with registry:

   * If registry references missing worktree → auto-mark run as `missing` and park.
   * If branch/worktree changed manually → prompt: “Update Commander to match reality?”
   * If mismatch unresolved → Commander becomes Observer until reconciled.

---

## 6) Long-Running / Context Management (“Session Roll”)

Commander must not accumulate logs in model context.

### Rule

Persist state to disk/DB; keep LLM context minimal.

**Session Roll strategy:**

* Summarize into a compact `cockpit` object.
* Reload only cockpit + current task when continuing.

---

## 7) Tooling Guardrails (MCP / Capabilities)

### 7.1 No Generic Shell Tool

Do **not** expose `runShell(command)`.

### 7.2 Whitelisted Verbs (Example)

**Read-only:**

* `getCockpit()`
* `listProjects()`
* `listRuns(projectId)`
* `doctorReport()`
* `getEventLog()`

**Write (requires approval):**

* `registerProject(path, type)`
* `setFocusProject(projectId)`
* `startRun(projectId, runName)`
* `finishRun(projectId, runName, handoffPath)`
* `markPreview(projectId, url)`

**Destructive (strong confirmation):**

* `cleanRun(projectId, runName, deleteBranch)`

### 7.3 Path Allowlist

Agent can only touch:

* harness install dir
* registered project roots
* harness-created worktrees

### 7.4 Auditability

Append-only log per action:

* command/tool call
* args (redacted)
* stdout/stderr
* verification results

---

## 8) Multi-Run Policy

* Multiple worktrees/runs can exist concurrently.
* Default ADHD mode: **only one run executes at a time**.
* Parallel execution is an advanced mode (Phase 4 per-project controllers).

---

## 9) Product UI: Kanban Cockpit (Phase 2)

Columns:

* **To Do**
* **Doing (Focus)** (max one)
* **In Preview**
* **Blocked**
* **Done**

UI must reflect verified truth (runs/tasks), not wishful state.

---

## 10) Implementation Plan (Phased)

### Phase 1 — Local MVP (Boss target)

Deliverables:

1. `c-harness session` cockpit
2. `c-harness doctor` pre-flight
3. local lock + Observer/Controller mode
4. reconcile reality (Git-first)
5. `c-harness inbox` fire-and-forget capture
6. `c-harness next` returns exactly one next action
7. append-only logs

Acceptance Criteria:

* Starting two sessions → one Controller, one Observer.
* Manual repo changes detected and reconciled.
* No silent success; verification required.
* One-next-action UX consistent.

### Phase 2 — Convex + Kanban

* Convex schema + leases + realtime UI
* multi-device safe controller lease

### Phase 3 — Sub-agents

* workers create **proposals** only
* controller selects and executes

### Phase 4 — Optional per-project parallelism

* scoped leases per project
* still enforce focus by default

---

## 11) Testing & Simulation

### Concurrency tests

1. two terminals start session → lock prevents dual control
2. finish vs clean race attempt → blocked by lock
3. crash recovery → lease expires and takeover works

### Reconcile tests

* delete worktree manually → commander marks missing and parks
* checkout different branch manually → prompts to adopt reality

### Verification tests

* after start: worktree exists + listed
* after finish: branch pushed + state updated
* after clean: worktree gone + state updated

---

## 12) Landing Page (Website) — Final Copy Outline

**Hero:**

* “Stop juggling. Start finishing.”
* “Harness Commander is the ADHD‑first shipping assistant for builders.”

**Value Pillars:**

1. **One cockpit** (Focus / Preview / Blocked / Inbox)
2. **One next action** (Next / Why / Done)
3. **One driver** (Controller lease prevents chaos)
4. **Always verifiable** (plan → execute → verify)

**Features:**

* Focus Lock
* Loop Closure
* Fire-and-forget Inbox
* Pre-flight Doctor
* Works with multiple worktrees
* Logs everything

**CTA:**

* “Join the waitlist / Get early access.”

---

## 13) Boss Decision Request

Approve Phase 1 Local MVP build with the following non-negotiables:

* Single Controller + Observer mode
* Reconcile Reality (Git-first)
* Doctor pre-flight
* One-next-action cockpit
* Append-only audit logs

Once Phase 1 proves trust and daily usefulness, proceed to Convex + Kanban (Phase 2).
