---
name: "quick"
description: "Execute a quick task with project standards but skip optional verification agents"
tools:
  [
    "read/readFile",
    "edit/editFiles",
    "search/listDirectory",
    "search/textSearch",
    "execute/runInTerminal",
    "agent",
  ]
---

# Quick Task

Execute small, ad-hoc tasks with project quality standards while skipping the full plan-check-verify cycle.

## When to Use

- Bug fixes that are obvious and localized
- Adding a test for existing code
- Documentation updates
- Small config changes
- Adding a utility function

## When NOT to Use (use full planning instead)

- New modules or features
- Changes that touch multiple modules
- Anything involving interfaces or architecture
- Changes to non-negotiable constraints

## Process

### Step 1: Understand the Task

Parse user's request. Confirm:
- Which files will change
- What the expected outcome is
- Whether tests are needed

### Step 2: Execute

1. Make the change following project conventions:
   - Type hints on all functions
   - Docstrings on every function
   - Design-decision comments for non-trivial logic
   - `core/` never imports from `apps/`

2. Run tests to confirm no regressions:

```bash
cd /home/vishnu/projects/routing_opt
source .venv/bin/activate
pytest --tb=short -q
```

3. If new code was written, add tests if appropriate.

### Step 3: Commit

Use the standard commit format:

```
{type}({module}): {description}

- Key change 1
- Key change 2
```

### Step 4: Report

Present result using continuation format:

```markdown
---

## ✓ Quick Task Complete

**{what was done}**
Files: {changed files}
Tests: {pass count} passing

---
```
