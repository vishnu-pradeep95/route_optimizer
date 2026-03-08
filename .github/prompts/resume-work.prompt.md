---
name: "resume-work"
description: "Resume work from previous session with full context restoration"
tools: ["read/readFile", "execute/runInTerminal", "edit/editFiles"]
---

# Resume Work

Restore complete project context and resume work seamlessly from a previous session.

## Process

### Step 1: Load Session Journal

```bash
# Read the full journal for context
cat plan/session-journal.md
```

### Step 2: Check for Interrupted Work

```bash
# Active debug sessions
ls .planning/debug/*.md 2>/dev/null | grep -v resolved

# Incomplete verifications
ls .planning/phases/*-VERIFICATION.md 2>/dev/null

# Uncommitted changes
cd /home/vishnu/projects/routing_opt
git status --short 2>/dev/null | head -20

# Recent file modifications (last 24 hours)
find core/ apps/ tests/ -name "*.py" -newer plan/session-journal.md -not -path "*__pycache__*" 2>/dev/null
```

### Step 3: Run Quick Health Check

```bash
# Test suite status
source .venv/bin/activate
pytest --tb=no -q 2>&1 | tail -5

# Docker services status
docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null

# Check for any errors
python -c "import core; print('Core imports OK')" 2>&1
```

### Step 4: Present Briefing

```markdown
## 📋 Session Briefing

**Phase:** {current phase}
**Last session:** {date} — {summary from last journal entry}
**Tests:** {pass}/{total} passing
**Services:** {Docker status summary}

### Unresolved from Last Session
{OPEN: items that haven't been DECIDED:}

### Blockers
{BLOCKED: items, or "None"}

### Interrupted Work
{Any active debug sessions, uncommitted changes, or incomplete verifications}

## ▶ Recommended

**{next action from last session's "Next steps"}**

---

**Also available:**
- Review open items in detail
- Check full progress → progress prompt
- Start fresh on a different task
```

### Step 5: Load Working Context

Based on the recommended next action, proactively load relevant files:

- If continuing a phase → read the design doc section for that phase
- If debugging → read the active debug file
- If implementing → read the relevant module's interface and tests
- If reviewing → read recent changes

This ensures the session starts with full context loaded, not just a summary.
