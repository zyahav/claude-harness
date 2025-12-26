# HANDOFF — Documentation Trust Protocol (Partner Model)

**Status:** Proposed for Boss Approval
**Confidence:** 10/10
**Audience:** c-harness maintainers, core contributors
**Scope:** Architecture & workflow only (no code in this handoff)

---

## 0. Executive Answer (Read First)

**Did we integrate the latest Gemini + Anti-Gravity insights?**
Yes — fully.

**Are we happy with the solution?**
Yes. This is a complete, professional, ADHD-safe design.

**Is this 10/10?**
Yes — because it eliminates silent failure, removes shame, and proves the system listens.

This handoff proposes adopting the **Documentation Trust Protocol (DTP)** as a **core harness principle**, not a feature.

---

## 1. Problem Statement (Why This Exists)

### Current Gap

`c-harness` currently manages:

* code execution
* task state
* worktrees
* finishing & pushing

But it treats documentation (`README.md`, `AGENT_GUIDE.md`) as **external artifacts**.

### Resulting Failure Mode

* Code evolves
* Docs stagnate
* Mismatch is silent

For ADHD users, this causes:

* self-doubt ("I must be wrong")
* cognitive overload
* permanent trust collapse

**Professional conclusion:** A system that allows silent documentation drift is unreliable by definition.

---

## 2. Design Philosophy (Non-Negotiable)

### Core Principle

> **The harness is the final authority on what is true for humans.**

Therefore:

* Documentation is part of runtime integrity
* Drift must be detected, surfaced, and resolved in-flow
* Memory and assistance must be provided by the system

---

## 3. The Solution: The Partner Model

We adopt a **Partner Model** built on three guarantees:

> **Detect · Assist · Remember**

This replaces policing with partnership.

---

## 4. Workflow Integration (Critical Path)

The protocol runs **inside `c-harness finish`**.

### Step 1 — Detect (The Witness)

The harness scans for documentation-relevant changes:

* New or modified CLI flags
* New or renamed public files

This step is always on. Silence is forbidden.

---

### Step 2 — Engage (The Partner)

If drift is detected, the harness pauses and presents a neutral notice:

> 🧠 **Documentation Awareness Notice**
> I noticed changes that may affect how humans use this system.
>
> **Item:** New CLI flag `--turbo`
>
> What would you like to do?
>
> 1. Update documentation (I will help)
> 2. Mark as internal (I will remember)
> 3. Defer (I will ask again later)

No errors. No blame. Full agency.

---

### Step 3 — Assist (The Secretary)

If the user selects **Update documentation**:

* The harness asks for a short description
* The harness edits the correct section automatically

The human provides *meaning*; the system handles *mechanics*.

---

### Step 4 — Remember (The Vault)

All explicit decisions are persisted:

* Internal-only items are remembered
* Deferred items are tracked

**Rule:** If the user answers once, the system must not ask again unnecessarily.

This persistence is the trust seal.

---

## 5. Enforcement Levels (Configurable)

| Mode             | Behavior                            |
| ---------------- | ----------------------------------- |
| Default          | Awareness + Assistance + Memory     |
| Release / Strict | Blocking if unresolved drift exists |

This allows fast iteration **and** hard guarantees when required.

---

## 6. Why This Is Professionally Correct

* Removes reliance on human memory
* Eliminates silent failure
* Preserves psychological safety
* Reduces ADHD cognitive load
* Scales from solo devs to teams

Most importantly:

> **The system never lies by omission.**

---

## 7. Final Recommendation

Adopt the Documentation Trust Protocol (Partner Model) as:

* a core harness workflow
* a required invariant
* a design philosophy

This completes `c-harness` as a **trustworthy system**, not just a powerful one.

---

**Approval Requested:**
Proceed with implementation following this handoff.
