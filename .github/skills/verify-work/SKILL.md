---
name: verify-work
description: "Validate built features through conversational UAT with persistent state. Creates UAT.md tracking test progress and feeds gaps into diagnosis."
---

# Verify Work Skill

Validate built features through automated checks and conversational testing.

## Purpose

Confirm what was built actually works from the user's perspective. Automated checks first, then human verification one test at a time. Plain text responses. When issues found, route to diagnosis.

## Philosophy

**Show expected, ask if reality matches.**

Present what SHOULD happen. User confirms or describes what's different.

- "yes" / "y" / "next" / empty → pass
- Anything else → logged as issue, severity inferred

No forms. No severity questions. Just: "Here's what should happen. Does it?"

## Process

### Step 1: Determine Scope

Parse what to verify:
- Phase number → verify phase goals from design doc
- Module name → verify module artifacts
- "recent work" → files changed since last session

### Step 2: Run Automated Checks

Before any human verification, run automated checks:

```bash
cd /home/vishnu/projects/routing_opt
source .venv/bin/activate

# Test suite
pytest --tb=short -q

# Architecture boundary
grep -rn "from apps\.\|import apps\." core/ --include="*.py" 2>/dev/null

# Stub detection
grep -rn "raise NotImplementedError\|pass$" core/ --include="*.py" 2>/dev/null | grep -v "test_\|__pycache__"

# Missing docstrings
grep -B1 "def " core/ --include="*.py" -rn 2>/dev/null | grep -v '"""' | grep -v "^--$" | grep -v "__" | head -20
```

### Step 3: Generate Test List

From the phase goals and design doc, derive user-observable truths to verify:

```markdown
## Tests for Phase {N}

1. **{Truth 1}** — {what to check}
2. **{Truth 2}** — {what to check}
3. **{Truth 3}** — {what to check}
```

### Step 4: Present Tests One at a Time

For each test:

```markdown
### Test {N}/{Total}: {Truth}

**What to check:**
{Specific steps — URLs to visit, commands to run, API calls to make}

**Expected:**
{What should happen}

Does this work? (yes/describe issue)
```

Wait for user response before presenting next test.

**Recording responses:**
- Pass → mark ✓, move to next
- Issue described → log as gap with user's description, infer severity:
  - **blocker**: Feature doesn't work at all
  - **major**: Feature works but with significant issues
  - **minor**: Cosmetic or edge-case issue

### Step 5: Create UAT Document

Write results to `.planning/phases/{phase}-UAT.md` using the template from `.planning/templates/UAT.md`.

Include:
- All test results (pass/fail with details)
- Summary counts
- Gaps in structured format

### Step 6: Handle Gaps

If any gaps found:

```markdown
## UAT Results

**Score:** {passed}/{total} tests passed
**Gaps:** {count} issues found

### Issues Found
1. **{Truth}** [{severity}] — {user's description}
2. **{Truth}** [{severity}] — {user's description}

### Next Steps
- Diagnose issues → diagnose-issues skill
- Fix directly → quick prompt (for simple fixes)
- Plan fixes → architect agent (for complex fixes)
```

If all tests pass:

```markdown
## ✓ All Tests Passed

**Score:** {total}/{total}
**Phase {N} verified through UAT.**

---

**Also available:**
- 💾 Save Session
- Continue to next phase
```
