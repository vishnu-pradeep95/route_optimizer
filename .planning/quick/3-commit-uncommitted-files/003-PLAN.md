---
phase: quick
plan: 003
type: execute
wave: 1
depends_on: []
files_modified:
  - .gitignore
  - docker-compose.prod.yml
  - infra/Dockerfile.dashboard
  - package-lock.json
  - .planning/debug/geocode-api-key-missing.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Tooling artifact directories are gitignored and will not appear in future git status"
    - "VITE_API_KEY build arg changes are committed with a clear message"
    - "package-lock.json is tracked (matches root package.json with Playwright devDependency)"
    - "Debug doc for geocode API key issue is committed with .planning/"
  artifacts:
    - path: ".gitignore"
      provides: "Ignore rules for tooling artifacts"
      contains: ".claude/"
    - path: "docker-compose.prod.yml"
      provides: "VITE_API_KEY build arg passthrough"
    - path: "infra/Dockerfile.dashboard"
      provides: "VITE_API_KEY ARG and ENV for dashboard build"
    - path: "package-lock.json"
      provides: "Dependency lock for root package.json (Playwright)"
  key_links: []
---

<objective>
Commit all uncommitted work: two modified tracked files adding VITE_API_KEY support to the production Docker build, update .gitignore for tooling artifacts, and commit package-lock.json and debug docs.

Purpose: Clean up working tree so git status is clean. Tracked changes represent real production config (API key support in Docker build). Untracked tooling artifacts should be ignored permanently.
Output: Clean git status with 2-3 well-scoped commits.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update .gitignore for tooling artifacts</name>
  <files>.gitignore</files>
  <action>
Append a new section to .gitignore with a clear comment header. Add the following entries at the end of the existing .gitignore file:

```
# Claude Code / GSD tooling
.claude/

# Playwright MCP
.playwright-mcp/

# VS Code workspace settings
.vscode/

# Test artifacts
dashboard-test.png
playwright-report/
test-results/

# GSD template (local copy)
gsd-template/
```

Do NOT add package-lock.json (it should be committed since root package.json exists with Playwright as a devDependency).

Do NOT remove or modify any existing .gitignore entries.
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && grep -c ".claude/" .gitignore && grep -c ".playwright-mcp/" .gitignore && grep -c ".vscode/" .gitignore && grep -c "dashboard-test.png" .gitignore && grep -c "gsd-template/" .gitignore && grep -c "playwright-report/" .gitignore && grep -c "test-results/" .gitignore && echo "All 7 entries present"</automated>
  </verify>
  <done>All 7 tooling artifact patterns are in .gitignore. Existing entries unchanged.</done>
</task>

<task type="auto">
  <name>Task 2: Commit VITE_API_KEY Docker build changes</name>
  <files>docker-compose.prod.yml, infra/Dockerfile.dashboard</files>
  <action>
Stage and commit the two modified tracked files together in one commit:

1. `git add docker-compose.prod.yml infra/Dockerfile.dashboard`
2. Commit with message: "feat(infra): add VITE_API_KEY build arg to production Docker build

Pass API_KEY from .env through docker-compose build args into the
dashboard Dockerfile. Vite bakes it into the JS bundle at build time
via import.meta.env.VITE_API_KEY."

These changes add VITE_API_KEY as a build arg in docker-compose.prod.yml (sourced from ${API_KEY:-}) and as an ARG+ENV in infra/Dockerfile.dashboard with explanatory comments.
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && git log -1 --oneline | grep -q "VITE_API_KEY" && echo "Commit exists" || echo "MISSING"</automated>
  </verify>
  <done>docker-compose.prod.yml and infra/Dockerfile.dashboard committed together with descriptive message about VITE_API_KEY support.</done>
</task>

<task type="auto">
  <name>Task 3: Commit .gitignore, package-lock.json, and debug docs</name>
  <files>.gitignore, package-lock.json, .planning/debug/geocode-api-key-missing.md</files>
  <action>
Stage and commit the remaining files in one commit:

1. `git add .gitignore package-lock.json .planning/debug/geocode-api-key-missing.md`
2. Commit with message: "chore: add .gitignore rules for tooling artifacts, track package-lock.json

- .gitignore: ignore .claude/, .playwright-mcp/, .vscode/, test artifacts,
  gsd-template/, dashboard-test.png
- package-lock.json: lock file for root package.json (Playwright devDep)
- .planning/debug/geocode-api-key-missing.md: debug doc for API key issue"

After this commit, run `git status` to confirm the working tree is clean (only the remaining untracked directories that are now gitignored should be gone).
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && git status --porcelain | grep -v "^?? backups/" | wc -l | xargs test 0 -eq && echo "Working tree clean" || (echo "Still dirty:" && git status --short)</automated>
  </verify>
  <done>Working tree is clean. All tooling artifacts are gitignored. package-lock.json and debug docs are tracked. git status shows no untracked or modified files (except possibly backups/ which has its own .gitkeep rules).</done>
</task>

</tasks>

<verification>
Run `git status` — should show a clean working tree. Run `git log --oneline -3` — should show the two new commits with clear messages.
</verification>

<success_criteria>
- git status is clean (no modified, no untracked outside of gitignored paths)
- Two commits exist: one for VITE_API_KEY infra changes, one for .gitignore + housekeeping
- .gitignore covers all 7 tooling artifact patterns
- package-lock.json is tracked (not ignored)
</success_criteria>

<output>
After completion, create `.planning/quick/3-commit-uncommitted-files/003-SUMMARY.md`
</output>
