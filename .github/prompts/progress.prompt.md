---
name: "progress"
description: "Check project progress, show context, and route to next action"
tools: ["read/readFile", "execute/runInTerminal", "search/textSearch", "search/listDirectory"]
---

# Progress Check

Check project progress, summarize recent work, and route to the next action.

## Process

### Step 1: Load Context

```bash
# Current state from session journal
tail -50 plan/session-journal.md

# Open items
grep "OPEN:" plan/session-journal.md

# Blockers
grep "BLOCKED:" plan/session-journal.md

# Recent decisions
grep "DECIDED:" plan/session-journal.md | tail -10

# Test status
cd /home/vishnu/projects/routing_opt
source .venv/bin/activate
pytest --tb=no -q 2>&1 | tail -5

# Codebase size
find core/ -name "*.py" -not -path "*__pycache__*" | wc -l
find tests/ -name "*.py" -not -path "*__pycache__*" | wc -l
```

### Step 2: Present Status

```markdown
## 📋 Project Status

**Phase:** {current phase from journal}
**Last session:** {date} — {summary}
**Tests:** {pass}/{total} passing
**Codebase:** {N} source files, {M} test files

### Recent Decisions
{last 3-5 DECIDED: items}

### Open Items ({count})
{list of unresolved OPEN: items}

### Blockers ({count})
{list of BLOCKED: items, or "None"}
```

### Step 3: Route to Next Action

Based on context, suggest the most logical next step:

- If BLOCKED items exist → address blockers first
- If OPEN items exist → resolve open questions
- If phase work pending → continue phase
- If phase complete → suggest next phase or verification

```markdown
## ▶ Recommended Next

**{action}** — {why this is the right next step}

---

**Also available:**
- 💾 Save Session
- 🔍 Deep Research
- 🧪 Review & Validate
```
