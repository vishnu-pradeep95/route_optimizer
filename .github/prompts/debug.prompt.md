---
name: "debug"
description: "Systematic debugging with persistent state across context resets"
tools: ["read/readFile", "execute/runInTerminal", "agent"]
---

# Debug

Debug issues using the scientific method with subagent isolation.

## How It Works

1. Gather symptoms from user
2. Spawn the **Debugger** agent as a subagent with full context
3. Debugger creates/updates a debug file in `.planning/debug/`
4. Handle checkpoints if the debugger needs user input
5. On resolution, move debug file to `.planning/debug/resolved/`

## Process

### Step 1: Check for Active Debug Sessions

```bash
ls .planning/debug/*.md 2>/dev/null | grep -v resolved
```

If active session exists, ask: "Resume existing debug session or start new one?"

### Step 2: Gather Context

Collect from user:
- **What's happening?** (symptoms, error messages)
- **What should happen?** (expected behavior)
- **What changed recently?** (code changes, config changes, updates)
- **Can you reproduce it?** (always/sometimes/once)

### Step 3: Spawn Debugger

Spawn the **Debugger** agent with:

```
Debug this issue in the routing optimization project:

**Symptoms:** {user's description}
**Expected:** {expected behavior}
**Recent changes:** {what changed}
**Reproducibility:** {always/sometimes/once}

Project context:
- Stack: Python 3.12, FastAPI, VROOM, OSRM, PostgreSQL/PostGIS
- Test command: pytest (from project root, venv at .venv/)
- Services: Docker Compose (osrm, vroom, postgres containers)
- Project reference: .planning/PROJECT.md
- Project state: .planning/STATE.md

Follow the scientific debugging method. Create/update debug file at .planning/debug/{issue-name}.md
```

### Step 4: Handle Result

**If resolved:**
- Move debug file to `.planning/debug/resolved/`
- Present fix summary to user
- Suggest saving session

**If needs more info:**
- Present debugger's questions to user
- Re-spawn with additional context

**If blocked:**
- Document blocker in session journal
- Present workaround options if any
