---
description: "Git integration — commit strategies, branch patterns, and atomic commits for the routing optimization project"
applyTo: "**/*"
---

# Git Integration

## Core Principle

**Commit outcomes, not process.**

The git log should read like a changelog of what shipped, not a diary of planning activity.

## Commit Points

| Event | Commit? | Why |
|---|---|---|
| Design doc updated | YES | Architecture decisions |
| Plan created in .planning/ | NO | Intermediate — commit with plan completion |
| **Task completed** | YES | Atomic unit of work (1 commit per task) |
| **Phase completed** | YES | Metadata commit (verification + journal) |
| Session journal updated | YES | Cross-session context preserved |

## Commit Format

### Task Completion

Each task gets its own commit immediately after completion.

```
{type}({module}): {description}

- [Key change 1]
- [Key change 2]
- [Key change 3]
```

**Commit types:**
- `feat` — New feature/functionality
- `fix` — Bug fix
- `test` — Test-only changes
- `refactor` — Code cleanup (no behavior change)
- `perf` — Performance improvement
- `chore` — Dependencies, config, tooling
- `docs` — Documentation only

**Module names** (use the core module or app name):

| Module | For |
|---|---|
| `routing` | core/routing/ changes |
| `optimizer` | core/optimizer/ changes |
| `geocoding` | core/geocoding/ changes |
| `data-import` | core/data_import/ changes |
| `database` | core/database/ changes |
| `models` | core/models/ changes |
| `kerala` | apps/kerala_delivery/ changes |
| `infra` | Docker, deployment, CI changes |
| `scripts` | scripts/ changes |

**Examples:**

```bash
# Standard implementation
git add core/routing/osrm_adapter.py core/routing/interfaces.py
git commit -m "feat(routing): implement OSRM adapter with distance matrix

- GET /route/v1/driving for point-to-point queries
- GET /table/v1/driving for distance matrix
- 1.3x safety multiplier applied to all durations
"

# TDD — RED phase
git add tests/core/optimizer/test_vroom_adapter.py
git commit -m "test(optimizer): add failing tests for VROOM job construction

- Tests vehicle capacity constraints
- Tests 30-minute minimum time windows
- Tests depot start/end location
"

# TDD — GREEN phase
git add core/optimizer/vroom_adapter.py
git commit -m "feat(optimizer): implement VROOM job construction

- Converts Order models to VROOM job format
- Enforces 30-min minimum time windows
- Sets vehicle capacity from config
"

# Bug fix
git add core/geocoding/google_adapter.py
git commit -m "fix(geocoding): handle API rate limit with exponential backoff

- Retry up to 3 times on 429 response
- Exponential backoff: 1s, 2s, 4s
- Log warning on each retry
"
```

### Phase Completion

After all phase tasks committed:

```
docs(phase-N): complete {phase-name}

Tasks completed: N/N
- Task 1 description
- Task 2 description

Verification: .planning/phases/{phase}-VERIFICATION.md
```

### Project Initialization

```
docs: initialize routing-optimization platform

Stack: VROOM + OSRM + PostgreSQL/PostGIS + FastAPI
Phases: See .planning/ROADMAP.md for current phase plan
```

## Branch Strategy

**For solo developer + Copilot workflow:**

```
main ← stable, deployable
  └── dev ← daily work, merge to main when phase complete
       └── feature/{module}-{description} ← optional, for risky changes
```

**When to branch:**
- Risky refactors (changing interfaces multiple modules depend on)
- Experimental features (trying OR-Tools alongside VROOM)
- Infrastructure changes (Docker compose restructuring)

**For normal phase work:** Commit directly to `dev`, merge to `main` at phase completion.

## What NOT to Commit

- `.env` files (use `.env.example` as template)
- `__pycache__/` directories
- `.venv/` virtual environment
- `data/osrm/*.osrm*` (large binary files — document download in SETUP.md)
- `data/geocode_cache/` (contains API responses with coordinates)
- Node modules (`node_modules/`)
- IDE settings (`.vscode/settings.json` — but DO commit `.vscode/mcp.json`)

## Anti-Patterns

**Still don't commit (intermediate artifacts):**
- Plan drafts in `.planning/` (commit with plan completion)
- Debug session files (commit when resolved, if lessons are valuable)
- "Fixed typo" micro-commits

**Do commit (outcomes):**
- Each task completion (feat/fix/test/refactor)
- Phase completion metadata (docs)
- Session journal updates (docs)
- Configuration changes that affect runtime (chore)
