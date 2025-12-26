# Brownfield Quick Start

This guide is for using c-harness to fix bugs or add features to an **existing codebase**.

## When to Use Brownfield Mode

Use `--mode brownfield` when:

- Fixing bugs in existing code
- Adding a small feature to an existing project
- Refactoring or improving existing functionality
- Working from GitHub issues or bug reports

**Don't use brownfield for:** Building a new app from scratch (use greenfield instead).

## Quick Start

### 1. Create a handoff.json

Create a file describing what needs to be fixed. See `examples/brownfield_handoff.json` for a template.

```json
{
  "meta": {
    "project": "my-existing-app",
    "phase": "Bug Fixes",
    "source": "GitHub Issue #42",
    "lock": true
  },
  "tasks": [
    {
      "id": "BUG-042",
      "category": "security",
      "title": "Fix SQL injection in login endpoint",
      "description": "The /api/login endpoint concatenates user input directly into SQL. Use parameterized queries instead.",
      "acceptance_criteria": [
        "Login endpoint uses parameterized queries",
        "Existing login functionality still works",
        "No raw string concatenation in auth code"
      ],
      "passes": false,
      "files_expected": ["src/auth/login.py"],
      "steps": ["Run existing tests", "Test with malicious input"]
    }
  ]
}
```

### 2. Start the run

```bash
c-harness start BUG-042 \
  --repo-path /path/to/existing-project \
  --mode brownfield
```

This creates an isolated worktree at `runs/BUG-042/` where the agent will work.

### 3. Run the agent

```bash
c-harness run BUG-042 \
  --repo-path /path/to/existing-project \
  --handoff-path /path/to/handoff.json
```

The agent will:
1. Orient itself (read handoff, explore codebase)
2. Understand the existing code patterns
3. Make minimal, focused changes
4. Test the fix
5. Mark tasks as passing
6. Commit with descriptive messages

### 4. Review and merge

After the agent completes:

```bash
# Check what changed
cd /path/to/existing-project
git diff main..run/BUG-042

# If satisfied, merge
git checkout main
git merge run/BUG-042 --no-ff -m "Merge BUG-042: Fix SQL injection"
git push origin main

# Cleanup
git worktree remove runs/BUG-042 --force
git branch -d run/BUG-042
```

## Brownfield vs Greenfield

| Aspect | Brownfield | Greenfield |
|--------|------------|------------|
| **Use case** | Fix/improve existing code | Build new app from scratch |
| **Scope** | 1-10 focused tasks | 50-200+ tasks |
| **Input** | handoff.json only | app_spec.txt + handoff.json |
| **Agent behavior** | Read first, minimal changes | Build from scratch |
| **Typical duration** | Minutes to hours | Hours to days |

## Tips for Good Brownfield Handoffs

1. **Be specific** — Include file paths, function names, line numbers if known
2. **One bug per task** — Don't combine multiple issues into one task
3. **Clear acceptance criteria** — How will you know it's fixed?
4. **Reference the source** — Link to GitHub issue, error log, etc.
5. **Keep scope small** — 1-5 tasks is ideal for brownfield

## Example: From GitHub Issue to Fix

**GitHub Issue #156:**
> Pagination shows duplicate items when sorting by date

**Your handoff.json task:**
```json
{
  "id": "BUG-156",
  "category": "functional",
  "title": "Fix pagination duplicate items",
  "description": "When paginating results sorted by date, items appear on multiple pages. Add id as secondary sort key.",
  "acceptance_criteria": [
    "No duplicate items across pages",
    "ORDER BY includes id as tiebreaker",
    "Pagination performance unchanged"
  ],
  "passes": false,
  "files_expected": ["src/utils/pagination.py"]
}
```

**Run it:**
```bash
c-harness start BUG-156 --repo-path ../my-app --mode brownfield
c-harness run BUG-156 --repo-path ../my-app --handoff-path ./handoff.json
```
