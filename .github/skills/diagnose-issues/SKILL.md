---
name: diagnose-issues
description: "Orchestrate debug agents to investigate UAT gaps and find root causes. Spawns debugger per gap, collects diagnoses, updates UAT.md."
---

# Diagnose Issues Skill

Orchestrate debug agents to investigate gaps found during verification or UAT.

## Purpose

After verification or UAT finds gaps, spawn one debugger per gap. Each debugger investigates autonomously with symptoms pre-filled. Collect root causes, update UAT/verification docs with diagnosis, then hand off to planning with actual diagnoses.

**Core principle:** Diagnose before planning fixes.

- Without diagnosis: "Route optimizer returns empty" → guess at fix → maybe wrong
- With diagnosis: "Route optimizer returns empty" → "VROOM adapter not applying vehicle capacity constraint" → precise fix

## Process

### Step 1: Parse Gaps

Extract gaps from the verification or UAT document:

```bash
# From verification
cat .planning/phases/*-VERIFICATION.md 2>/dev/null | grep -A5 "gaps:"

# From UAT
cat .planning/phases/*-UAT.md 2>/dev/null | grep -A5 "Gaps"
```

Build gap list with: truth (what should be true), status (failed/partial), reason (what's wrong), severity.

### Step 2: Report Plan

```markdown
## Diagnosing {N} Gaps

Spawning debug agents to investigate root causes:

| Gap (Truth) | Severity |
|---|---|
| {truth 1} | {severity} |
| {truth 2} | {severity} |

Each agent will:
1. Create `.planning/debug/{issue-slug}.md` with symptoms
2. Investigate autonomously (read code, form hypotheses, test)
3. Return root cause and fix recommendation
```

### Step 3: Spawn Debuggers

For each gap, spawn a **Debugger** agent with:

```
Debug this gap in the routing optimization project:

**Truth that should hold:** {truth}
**What's happening instead:** {reason}
**Severity:** {severity}
**Related artifacts:** {file paths if known}

Project context:
- Stack: Python 3.12, FastAPI, VROOM, OSRM, PostgreSQL/PostGIS
- Tests: pytest (source .venv/bin/activate && pytest)
- Design doc: plan/kerala_delivery_route_system_design.md

Investigate the root cause. Create debug file at .planning/debug/{slug}.md
Return: root cause + recommended fix (specific files and changes)
```

### Step 4: Collect Results

For each completed debugger:
1. Read the debug file from `.planning/debug/`
2. Extract root cause and recommended fix
3. Update the verification/UAT document with diagnosis

### Step 5: Present Results

```markdown
## Diagnosis Complete

| Gap | Root Cause | Fix |
|---|---|---|
| {truth 1} | {root cause} | {recommended fix} |
| {truth 2} | {root cause} | {recommended fix} |

### Ready for Fix Planning

{N} gaps diagnosed. Fixes can be implemented via:
- Quick task (for simple fixes) → quick prompt
- Implementation task → Implementer agent
- Full plan (for complex fixes) → architect agent
```
