# Documentation Trust Protocol v2
## The "Partner" Model: Awareness, Persistence, and Assistance

### 1. Executive Summary
I agree with the "Awareness" model 10/10. It correctly identifies that for ADHD users, **shame is a friction point**. A "Violation" error stops flow and invites negative self-talk. An "Awareness Notice" invites partnership.

However, to make this **100% reliable**, we must add two missing engineering components:
1.  **Persistence**: The system must *remember* your answers. If you say "This flag is internal," it shouldn't ask you again next time.
2.  **Assistance**: The system shouldn't just ask you to "update docs"; it should offer to *do it for you*.

### 2. The Refined Protocol: "Detect, Assist, Remember"

#### Step 1: Detect (The Witness)
The harness scans the code and docs during `c-harness finish`.
*   **Trigger**: A mismatch is found (e.g., `new_feature.py` exists but is not in the README map).
*   **Action**: Pause. Do not fail. Do not strictly block.

#### Step 2: Engage (The Partner)
Present the findings neutrally. Offer **high-agency** choices.

> 🧠 **Harness Awareness Notice**
> I noticed changes that aren't in the documentation yet.
>
> **Item**: New CLI flag `--turbo` found in `harness.py`.
>
> **What should we do?**
> 1. [ ] **Update Specs**: Add it to `README.md` automatically (I will draft the text).
> 2. [ ] **Mark Internal**: This is for dev use only (I will remember this).
> 3. [ ] **Ignore**: Just for now (I will ask again next time).

#### Step 3: Assist (The Secretary)
If the user chooses "Update Specs":
*   **Don't**: Make the user open the file, find the line, and type.
*   **Do**: Prompt for a 1-line description. "What does `--turbo` do?"
*   **Auto-Action**: The harness appends the correct markdown to the `README.md` Table of Arguments.

#### Step 4: Remember (The Vault)
This is the critical missing piece.
If the user chooses "Mark Internal" or intentionally deviates from the pattern, we must **store this decision**.
*   **Mechanism**: A `doc_ignore` list in `pyproject.toml` or `handoff.json`.
*   **Why**: If I run `finish`, mark it as internal, then realize I forgot to push and run `finish` again, **it must not ask me again**. If it asks again, I lose trust that it is "listening."

### 3. Implementation Strategy

#### The "Docs-State" File
We will track the "known state" of documentation to differentiate between *new* drift and *acknowledged* drift.

*   `docs/known_flags.json`: Stores the list of flags that were present last time we checked.
*   `docs/ignored_items.json`: Stores items the user explicitly said to ignore.

#### The Workflow
1.  `c-harness finish` starts.
2.  **Scan**: Compare `harness.py` vs `README.md` + `ignored_items.json`.
3.  **Diff**: Identify truly new/unhandled items.
4.  **Prompt**: If Diff exists, show the interactive menu.
    *   *Option A (Update)*: User inputs string -> Harness edits README -> Harness adds to `known_flags`.
    *   *Option B (Internal)*: Harness adds to `ignored_items`.
5.  **Proceed**: Git push.

### 4. Conclusion
We move from **Policing** (Error: You failed) to **Partnership** (Notice: I found this, let's handle it).
By adding **Persistence** (Memory), the system proves it listens.
By adding **Assistance** (Auto-edit), the system reduces the toll of compliance.
