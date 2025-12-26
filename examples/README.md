# Example Handoff Files

This folder contains example `handoff.json` files to help you get started with c-harness.

## Which example should I use?

| Scenario | Example File | Description |
|----------|--------------|-------------|
| Building a new app from scratch | `greenfield_handoff.json` | Multiple tasks across categories for a new project |
| Fixing bugs or adding features to existing code | `brownfield_handoff.json` | Focused tasks for modifying an existing codebase |
| Just want to see the minimum valid format | `minimal_handoff.json` | Single task, bare minimum fields |

## Handoff Structure

Every handoff.json has two sections:

```json
{
  "meta": { ... },
  "tasks": [ ... ]
}
```

### Meta (required fields)

| Field | Description | Example |
|-------|-------------|---------|
| `project` | Project name | `"my-awesome-app"` |
| `phase` | Current phase | `"Phase 1"` |
| `source` | Where this handoff came from | `"PRD v2.1"` |
| `lock` | Prevent modifications during run | `true` |

### Task (required fields)

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique identifier | `"TASK-001"` |
| `category` | Task category (see below) | `"api"` |
| `title` | Short, action-oriented title | `"Add user authentication endpoint"` |
| `description` | What must be implemented | `"Create POST /auth/login endpoint..."` |
| `acceptance_criteria` | List of verifiable criteria | `["Returns JWT token", "Validates password"]` |
| `passes` | Whether task is complete | `false` |

### Optional Task Fields

| Field | Description |
|-------|-------------|
| `files_expected` | Hint for files that will be touched |
| `steps` | Verification steps for testing |

## Valid Categories

Tasks must use one of these categories:

- `api` - API endpoints and routes
- `auth` - Authentication and authorization
- `cli` - Command-line interface features
- `database` - Database schemas, migrations, queries
- `docs` - Documentation
- `functional` - General features
- `infrastructure` - DevOps, deployment, config
- `oidc` - OpenID Connect integration
- `roles` - Role-based access control
- `security` - Security features and fixes
- `style` - UI/UX styling
- `testing` - Tests and test infrastructure
- `ui` - User interface components

## Usage

1. Copy the appropriate example to your handoffs directory:
   ```bash
   cp examples/brownfield_handoff.json ~/handoffs/my-project/handoff.json
   ```

2. Edit the file to match your project and tasks

3. Run c-harness:
   ```bash
   c-harness run MY-RUN-ID --handoff-path ~/handoffs/my-project/handoff.json
   ```

## Validating Your Handoff

Use the schema command to validate your handoff before running:

```bash
c-harness schema path/to/handoff.json
```

This will report any errors in your handoff structure.
