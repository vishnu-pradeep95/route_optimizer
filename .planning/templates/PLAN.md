# Plan: Phase [N]-[Plan Number] — [Plan Title]

**Phase:** [N] — [Phase Name]
**Phase Goal:** [Goal from design doc]
**Wave:** [1/2/3]
**Depends On:** [None / Plan numbers]

---

## Must-Haves

```yaml
must_haves:
  truths:
    - "[User-observable behavior that must be true]"
    - "[Another truth]"
  artifacts:
    - path: "core/path/to/file.py"
      provides: "[What this file delivers]"
    - path: "tests/path/to/test_file.py"
      provides: "[What this test validates]"
  key_links:
    - from: "core/optimizer/vroom_adapter.py"
      to: "core/routing/osrm_adapter.py"
      via: "[How they connect]"
```

## Tasks

<!-- XML task format for precise execution. Each task is atomic. -->

<task type="auto">
  <name>[Task name]</name>
  <files>[Files to create or modify]</files>
  <action>
    [Specific implementation instructions]
    [Reference design doc sections where relevant]
    [Include WHY comments for educational value]
  </action>
  <verify>[Command to verify — prefer pytest]</verify>
  <done>[Acceptance criteria — what proves this works]</done>
</task>

<task type="auto">
  <name>[Next task]</name>
  <files>[Files]</files>
  <action>
    [Instructions]
  </action>
  <verify>[Verification command]</verify>
  <done>[Acceptance criteria]</done>
</task>

<!-- Use checkpoint only when human input is truly unavoidable -->
<task type="checkpoint:human-verify">
  <name>[What to verify visually]</name>
  <action>
    [What to show the user and what to ask]
  </action>
  <done>[What a passing confirmation looks like]</done>
</task>

## Constraints

<!-- Project-specific constraints that apply to this plan -->

- No countdown timers in any UI
- Minimum 30-minute delivery windows
- Speed alerts at 40 km/h urban
- 1.3× safety multiplier on travel time estimates
- Offline-capable driver interface
- PII stays in source spreadsheet only
- `core/` never imports from `apps/`
- Every function gets a docstring, every interface uses ABC/Protocol

## Scope Check

- **Tasks:** [N] (target: 2-3, warning at 4, blocker at 5+)
- **Files:** [N] (target: 5-8, warning at 10, blocker at 15+)
