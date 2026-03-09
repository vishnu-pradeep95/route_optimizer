---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - README.md
  - SETUP.md
  - docker-compose.yml
  - scripts/start.sh
autonomous: true
requirements: [OSRM-DOC-01]
must_haves:
  truths:
    - "OSRM health check commands in docs use a real OSRM API endpoint, not the non-existent /health"
    - "VROOM depends_on OSRM with service_healthy (not service_started) so it waits for OSRM port"
    - "start.sh diagnose_failure tests OSRM readiness with an actual route query, not just container status"
    - "SETUP.md has a troubleshooting section explaining first-run OSRM download time and how to check progress"
  artifacts:
    - path: "README.md"
      provides: "Corrected OSRM health check in Docker Services table"
      contains: "nearest/v1/driving"
    - path: "SETUP.md"
      provides: "OSRM troubleshooting section and corrected verify command"
      contains: "nearest/v1/driving"
    - path: "docker-compose.yml"
      provides: "VROOM depends_on OSRM with service_healthy"
      contains: "service_healthy"
    - path: "scripts/start.sh"
      provides: "OSRM readiness test using real API call"
      contains: "nearest/v1/driving"
  key_links:
    - from: "docker-compose.yml"
      to: "OSRM healthcheck"
      via: "depends_on condition"
      pattern: "service_healthy"
---

<objective>
Fix incorrect OSRM health check documentation, upgrade Docker dependency conditions, and improve startup diagnostics.

Purpose: OSRM has no `/health` endpoint. Current docs and scripts give users incorrect commands, and Docker starts VROOM/API before OSRM is actually listening. This causes confusing failures on first-run setups where OSRM init takes ~15 minutes.

Output: Corrected docs (README.md, SETUP.md), upgraded docker-compose.yml dependencies, improved start.sh diagnostics.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@README.md (lines 409-416 — Docker Services table with wrong OSRM health check)
@SETUP.md (lines 321-325 — wrong OSRM verify command; lines 386-406 — new-laptop troubleshooting)
@docker-compose.yml (lines 137-149 — VROOM depends_on uses service_started; lines 217-225 — API depends_on)
@scripts/start.sh (lines 128-135 — OSRM diagnostic only checks container status)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix docker-compose.yml dependency conditions</name>
  <files>docker-compose.yml</files>
  <action>
In docker-compose.yml, change the VROOM service's depends_on for OSRM from `condition: service_started` to `condition: service_healthy`. This ensures VROOM waits until OSRM's healthcheck (TCP port 5000 open) passes before starting.

Also change the API service's depends_on for both OSRM and VROOM from `condition: service_started` to `condition: service_healthy`.

For VROOM, add a healthcheck since it currently has none — VROOM listens on port 3000:
```yaml
healthcheck:
  test: ["CMD-SHELL", "bash -c 'echo > /dev/tcp/localhost/3000'"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 5s
```

Summary of changes:
1. VROOM: add healthcheck for port 3000
2. VROOM depends_on osrm: service_started -> service_healthy
3. API depends_on osrm: service_started -> service_healthy
4. API depends_on vroom: service_started -> service_healthy
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && grep -A2 "condition: service_healthy" docker-compose.yml | head -20 && docker compose config --quiet 2>&1 && echo "VALID"</automated>
  </verify>
  <done>VROOM waits for OSRM healthcheck, API waits for both OSRM and VROOM healthchecks. docker compose config validates without errors.</done>
</task>

<task type="auto">
  <name>Task 2: Fix docs and improve start.sh OSRM diagnostics</name>
  <files>README.md, SETUP.md, scripts/start.sh</files>
  <action>
**README.md** (line 412): In the Docker Services table, change the OSRM health check from `curl http://localhost:5000/health` to `curl -sf http://localhost:5000/nearest/v1/driving/76.2846,9.9716`. Add a note after the table explaining that OSRM has no /health endpoint — you verify readiness by querying a real coordinate (the depot location in Kochi).

**SETUP.md** (line 324): Change `curl http://localhost:5000/health  # Should return {"status":"ok"}` to `curl http://localhost:5000/nearest/v1/driving/76.2846,9.9716` with a comment explaining this queries the nearest road segment to the depot coordinates.

**SETUP.md** (after line 406, at end of file): Add a new troubleshooting section:

```markdown
---

## Troubleshooting

### OSRM Not Ready

On **first startup**, OSRM needs to download and preprocess Kerala map data (~150 MB download, ~10-15 minutes processing). During this time, route optimization will fail.

**How to check OSRM init progress:**
```bash
# Watch the init container logs (will show download/preprocessing progress)
docker compose logs osrm-init -f

# Check if init is complete (should show "Exited (0)")
docker compose ps osrm-init
```

**How to verify OSRM is ready to serve routes:**
```bash
# Check Docker healthcheck status
docker inspect --format='{{.State.Health.Status}}' osrm-kerala

# Test with a real routing query (depot coordinates in Kochi)
curl -sf http://localhost:5000/nearest/v1/driving/76.2846,9.9716
```

**Common OSRM issues:**
- **Container exits with code 137:** Out of memory. OSRM preprocessing needs ~4 GB RAM. Increase WSL memory (see above).
- **"file not found" errors:** The `osrm-init` container hasn't finished. Wait for it to exit with code 0.
- **OSRM starts but returns errors:** Map data may be corrupted. Delete `data/osrm/` and restart: `rm -rf data/osrm && docker compose up -d`
```

**scripts/start.sh** (diagnose_failure function, lines 128-135): Replace the OSRM check block. Instead of only checking container status, also test OSRM readiness with a real API call:

```bash
# Check OSRM
local osrm_status
osrm_status=$(docker inspect --format='{{.State.Status}}' osrm-kerala 2>/dev/null || echo "not found")
local osrm_health
osrm_health=$(docker inspect --format='{{.State.Health.Status}}' osrm-kerala 2>/dev/null || echo "unknown")
if [ "$osrm_status" != "running" ]; then
    error "OSRM routing engine (osrm-kerala): status=$osrm_status"
    # Check if osrm-init is still running (first-time setup)
    local init_status
    init_status=$(docker inspect --format='{{.State.Status}}' osrm-init 2>/dev/null || echo "not found")
    if [ "$init_status" = "running" ]; then
        warn "OSRM init is still downloading/preprocessing Kerala map data."
        echo "  This takes ~10-15 minutes on first startup."
        echo "  Watch progress: docker compose logs osrm-init -f"
    else
        echo "  Try: docker compose logs osrm --tail=20"
    fi
    all_running=false
elif [ "$osrm_health" != "healthy" ]; then
    warn "OSRM (osrm-kerala): running but not healthy yet (health=$osrm_health)"
    echo "  OSRM may still be loading map data into memory."
    echo "  Test manually: curl -sf http://localhost:5000/nearest/v1/driving/76.2846,9.9716"
    all_running=false
fi
```

Remove the comment "(no reliable healthcheck per research)" since we now use the Docker healthcheck.
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && grep -c "nearest/v1/driving" README.md SETUP.md scripts/start.sh && grep "Troubleshooting" SETUP.md && grep "osrm_health" scripts/start.sh && echo "ALL CHECKS PASSED"</automated>
  </verify>
  <done>README.md and SETUP.md show correct OSRM health check command using nearest/v1/driving endpoint. SETUP.md has new troubleshooting section with OSRM first-run guidance. start.sh diagnose_failure checks OSRM healthcheck status and detects osrm-init still running on first setup.</done>
</task>

</tasks>

<verification>
1. `docker compose config --quiet` validates without errors
2. `grep "service_healthy" docker-compose.yml` shows OSRM and VROOM dependency conditions
3. `grep "nearest/v1/driving" README.md SETUP.md scripts/start.sh` confirms all three files use correct endpoint
4. `grep -A3 "OSRM Not Ready" SETUP.md` confirms troubleshooting section exists
5. `bash -n scripts/start.sh` confirms no syntax errors
</verification>

<success_criteria>
- docker-compose.yml: VROOM depends on OSRM with service_healthy, API depends on both with service_healthy
- README.md: Docker Services table shows correct OSRM readiness check command
- SETUP.md: Step 9 verify command is correct; new troubleshooting section covers first-run OSRM wait
- scripts/start.sh: diagnose_failure checks OSRM healthcheck status and detects running osrm-init
- All files pass syntax validation (docker compose config, bash -n)
</success_criteria>

<output>
After completion, create `.planning/quick/2-document-osrm-readiness-check-and-add-tr/2-SUMMARY.md`
</output>
