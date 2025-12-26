# The Documentation Trust Protocol
## Ensuring Reliability for the ADHD Brain

### 1. The Core Challenge
For developers with ADHD, **trust in the system is binary**.
*   If the documentation works 100% of the time, the system is a stable anchor.
*   If the documentation fails once (e.g., a flag is missing, a command has changed), the entire system becomes a source of anxiety and distraction. "Is the tool broken, or am I doing it wrong?"

**Current State**: `c-harness` relies on human memory to update `README.md` and `AGENT_GUIDE.md` when code changes. This is a single point of failure.

### 2. The Solution: "Docs as Code"
We must move from **Documentation by Memory** to **Documentation by Architecture**. The system shouldn't ask "Did you remember to update the docs?"; it should say "I have updated the docs for you" or "I cannot build because docs are out of sync."

### 3. Proposed Strategy

#### Phase 1: The Gatekeeper (Validation)
**Goal**: Stop the bleeding. Prevent `finish` if documentation is stale.

Implement a `verify_docs` check in `harness.py`'s `finish` command that runs **locally** before the push.

1.  **CLI Consistency Check**:
    *   Run `python harness.py --help`.
    *   Extract the Arguments/Commands section.
    *   Scan `README.md` and `AGENT_GUIDE.md`.
    *   **Rule**: Every argument (e.g., `--mode`, `--handoff-path`) appearing in the code MUST appear in the docs. If `--no-archon` is in `harness.py` but not `README.md`, the `finish` command **fails** with a specific error:
        > ❌ **Documentation Integrity Error**: New flag `--no-archon` detected in code but missing from `README.md`.
        > Please describe this flag in the documentation before finishing.

2.  **Repository Map Integrity**:
    *   Scan `*.py` files in the root.
    *   Check the "Repository Map" section in `README.md`.
    *   **Rule**: If a new python file is added, it must be listed in the map.

#### Phase 2: The Generator (Automation)
**Goal**: Remove the burden entirely.

Instead of writing docs manually, we **embed** the source of truth.

1.  **Auto-Generated Usage**:
    *   Use a marker in `README.md`:
        ```markdown
        ## Usage
        <!-- BEGIN_CLI_HELP -->
        (This will be overwritten by the build system)
        <!-- END_CLI_HELP -->
        ```
    *   Create a simple hook (e.g., `.git/hooks/pre-commit` or a `c-harness docs:update` command) that runs the CLI help and injects it directly into the Markdown.
    *   **Result**: The documentation is *always* perfectly accurate because it is a reflection of the code itself.

### 4. Recommendation for `c-harness`
We should immediately implement **Phase 1 (The Gatekeeper)** inside the `finish` command.

**Why?**
*   It is low-effort to implement.
*   It provides immediate feedback during the workflow (where it matters).
*   It builds trust: You know the system "has your back" and won't let you ship broken instructions.

### 5. Implementation Draft (Concept)

```python
# Pseudo-code for harness.py -> handle_finish
def verify_documentation_integrity():
    # 1. Get Code Reality
    parser = setup_argparse()
    cli_flags = extract_flags(parser) # ['--mode', '--repo-path', ...]

    # 2. Get Docs Reality
    readme_content = Path("README.md").read_text()
    
    # 3. Compare
    missing = [flag for flag in cli_flags if flag not in readme_content]
    
    if missing:
        raise IntegrityError(f"Protocol Violation: The following flags are undocumented: {missing}")
```

### Conclusion
"Professional" means **predictable**. By enforcing documentation consistency programmatically, we convert a "best practice" into a hard guarantee. This allows the user to offload the mental burden of "checking" to the machine, which is the ultimate accommodation for ADHD.
