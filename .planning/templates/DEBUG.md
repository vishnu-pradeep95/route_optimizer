# Debug Session: [TITLE]

**Created:** [YYYY-MM-DD HH:MM]
**Status:** ACTIVE | ROOT_CAUSE_FOUND | RESOLVED
**Mode:** find_root_cause_only | find_and_fix
**Severity:** critical | high | medium | low

---

## Symptoms

<!-- What the user reported or what was observed. Observable facts only. -->

- **Expected behavior:**
- **Actual behavior:**
- **Error messages:** (if any)
- **Reproducibility:** always | intermittent | once
- **Environment:** (Docker containers running, services up, etc.)

## Hypotheses

<!-- List all hypotheses with status. One at a time. -->

### H1: [Specific, falsifiable hypothesis]

- **Prediction:** If true, I will observe X
- **Test:** [What to do to test]
- **Result:** [What actually happened]
- **Status:** TESTING | CONFIRMED | REFUTED
- **Evidence:** [Concrete observations]

### H2: [Next hypothesis]

...

## Investigation Log

<!-- Chronological record of what was tried. APPEND only. -->

### [HH:MM] [Action taken]

- **What:** [Specific action]
- **Observed:** [Exact result]
- **Conclusion:** [What this tells us]

## Root Cause

<!-- Only fill when status = ROOT_CAUSE_FOUND or RESOLVED -->

- **Mechanism:** [Why the bug happens — the actual cause chain]
- **Location:** [File(s) and line(s)]
- **Category:** logic | config | integration | data | concurrency | dependency

## Fix

<!-- Only fill in find_and_fix mode -->

- **Changes made:** [Files modified with brief description]
- **Verification:** [How the fix was confirmed]
- **Regression test:** [Test added to prevent recurrence]
- **Side effects:** [Any other behavior affected]
