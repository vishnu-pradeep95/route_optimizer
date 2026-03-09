---
description: "Standard format for presenting next steps and session continuation"
applyTo: "**/*.md"
---

# Continuation Format

Standard format for presenting next steps after completing a task or phase.

## After Task Completion

```markdown
---

## ✓ Task Complete

**{module}: {task name}**
Files: {list of files changed}
Tests: {pass count}/{total} passing

## ▶ Next Up

**{next task name}** — {one-line description}

---

**Also available:**
- Save session → 💾 Save Session
- Review changes → 🧪 Review & Validate
- Check progress → session journal

---
```

## After Phase Completion

```markdown
---

## ✓ Phase {N} Complete

{summary of what was built}
Tests: {count} passing

## ▶ Next Up

**Phase {N+1}: {name}** — {goal from design doc}

---

**Before starting:**
- Review `.planning/ROADMAP.md` for Phase {N+1} details
- Check `.planning/STATE.md` for current project state
- Save this session → 💾 Save Session

---
```

## After Debugging

```markdown
---

## ✓ Issue Resolved

**Root cause:** {one-line root cause}
**Fix:** {what was changed}
**Debug file:** `.planning/debug/{issue-name}.md` → moved to `.planning/debug/resolved/`

## ▶ Resume Previous Work

{What you were doing before the bug interrupted}

---
```

## Session Start

```markdown
---

## 📋 Session Briefing

**Phase:** {current phase}
**Last session:** {date} — {summary}
**Open items:** {count}
**Blockers:** {count or "none"}

## ▶ Recommended

**{next action}** — {why this is the right next step}

---

**Also available:**
- Review open items in detail
- Start a different task
- 🔍 Deep Research on a topic

---
```

## Format Rules

1. **Always show what it is** — name + description, never just a file path
2. **Pull context from source** — design doc for phases, session journal for status
3. **Visual separators** — `---` above and below to make it stand out
4. **Include test counts** — always mention how many tests are passing
5. **Reference agents** — use handoff labels (💾 Save Session, 🧪 Review & Validate)
