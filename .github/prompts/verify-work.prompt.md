---
name: "verify-work"
description: "Validate built features through conversational UAT and automated verification"
tools:
  [
    "read/readFile",
    "execute/runInTerminal",
    "search/listDirectory",
    "search/textSearch",
    "edit/editFiles",
    "agent",
  ]
---

# Verify Work

Validate built features through automated checks and conversational testing.

## How It Works

1. Run automated verification (tests, stub detection, wiring checks)
2. Present human-verification items one at a time
3. Track results in `.planning/phases/{phase}-UAT.md`
4. If issues found: diagnose and create fix tasks

## Process

### Step 1: Determine Scope

Parse user's request to determine what to verify:
- **Phase verification:** "verify phase 0" → full phase goal-backward verification
- **Module verification:** "verify routing module" → focus on `core/routing/`
- **Recent work:** "verify what we just did" → check files changed in current session

### Step 2: Run Automated Checks

Spawn the **Verifier** agent as a subagent:

```
Verify {scope} in the routing optimization project.

Phase/Module: {what to verify}
Design doc: plan/kerala_delivery_route_system_design.md
Session history: plan/session-journal.md

Run the full verification process:
1. Establish must-haves from the design doc
2. Three-level artifact verification (exists, substantive, wired)
3. Run pytest
4. Nyquist validation (test coverage adequacy)
5. Anti-pattern scan
6. Non-negotiable constraint check
7. Architecture boundary check (core/ never imports apps/)

Write results to .planning/phases/{phase}-VERIFICATION.md
```

### Step 3: Present Results

Show verification results to user:

**If all automated checks pass:**
- Present any human-verification items one at a time
- Wait for user response before next item
- Track in UAT.md

**If gaps found:**
- Present gap summary
- Offer to create fix tasks
- Offer to spawn Implementer for fixes

### Step 4: Handle Issues

For each issue found:

1. **Diagnose:** What's wrong and why
2. **Plan fix:** Specific files and changes needed
3. **Execute fix:** Spawn Implementer or fix directly
4. **Re-verify:** Run verification again on fixed items

### Step 5: Record Results

Write results to `.planning/phases/{phase}-UAT.md` using template from `.planning/templates/UAT.md`.
