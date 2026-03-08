---
description: "Checkpoint protocols for plan execution — when to pause for human verification or decisions"
applyTo: "**/*.md,**/*PLAN*"
---

# Checkpoints

Checkpoints formalize interaction points where human verification or decisions are needed during plan execution.

## Core Principle

**Copilot automates everything with CLI/API. Checkpoints are for verification and decisions, not manual work.**

Golden rules:
1. **If Copilot can run it, Copilot runs it** — Never ask user to execute CLI commands
2. **Copilot sets up the verification environment** — Start servers, seed databases, configure .env
3. **User only does what requires human judgment** — Visual checks, UX evaluation, "does this feel right?"
4. **Secrets come from user, automation comes from Copilot** — Ask for API keys, then Copilot uses them

## Checkpoint Types

### checkpoint:human-verify (Most Common)

Copilot completed work, human confirms it works.

**Use for:**
- Visual UI checks (dashboard layout, driver app screens)
- Interactive flows (test order import → geocode → optimize → route display)
- Functional verification (API returns correct data)

**Structure:**

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <what-built>[What Copilot automated]</what-built>
  <how-to-verify>
    [Exact steps — URLs, commands, expected behavior]
  </how-to-verify>
  <resume-signal>[How to continue — "approved", "yes", or describe issues]</resume-signal>
</task>
```

**Example — OSRM Routing Verification:**

```xml
<task type="auto">
  <name>Start OSRM Docker container with Kerala data</name>
  <files>docker-compose.yml</files>
  <action>docker compose up -d osrm && wait for healthy</action>
  <verify>curl http://localhost:5000/route/v1/driving/76.2673,9.9312;76.2733,9.9352 returns valid JSON</verify>
  <done>OSRM responds with routes for Kochi coordinates</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>OSRM running with Kerala road network data</what-built>
  <how-to-verify>
    1. Open http://localhost:9966 (OSRM debug map)
    2. Click two points in Kochi area
    3. Verify route follows actual roads (not straight lines)
    4. Check the distance/duration look reasonable (~5km should be ~15-20min)
  </how-to-verify>
  <resume-signal>Type "approved" if routes look correct, or describe issues</resume-signal>
</task>
```

### checkpoint:decision

User must make a choice that affects implementation.

**Use for:**
- Technology choice (VROOM vs OR-Tools for a specific constraint)
- Architecture decision (single vs multi-depot)
- Scope decision (include time windows in Phase 1 or defer to Phase 2)

**Structure:**

```xml
<task type="checkpoint:decision" gate="blocking">
  <question>[Decision to make]</question>
  <options>
    [Option A: description + tradeoffs]
    [Option B: description + tradeoffs]
  </options>
  <recommendation>[Your recommendation and why]</recommendation>
  <resume-signal>[What to say for each option]</resume-signal>
</task>
```

### checkpoint:secret

User must provide a secret value.

**Use for:**
- API keys (Google Maps, etc.)
- Database passwords
- Deployment credentials

**Structure:**

```xml
<task type="checkpoint:secret" gate="blocking">
  <what-needed>[Which secret and where to get it]</what-needed>
  <how-to-provide>Paste the key, Copilot will add it to .env</how-to-provide>
  <resume-signal>Paste the API key</resume-signal>
</task>
```

## Automation Before Checkpoints

Before presenting a human-verify checkpoint, Copilot MUST:

1. **Start any needed services:**

```bash
# Start Docker services
docker compose up -d osrm vroom postgres

# Wait for healthy
docker compose ps --format json | python3 -c "import sys,json; [print(s['State']) for s in json.loads(sys.stdin.read())]"

# Start FastAPI dev server
cd /home/vishnu/projects/routing_opt
source .venv/bin/activate
uvicorn apps.kerala_delivery.api.main:app --reload --port 8000 &
```

2. **Seed test data if needed:**

```bash
python scripts/import_orders.py --file data/sample_orders.csv
```

3. **Verify environment is working before presenting checkpoint:**

```bash
curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.loads(sys.stdin.read()))"
```

## Project-Specific Checkpoint Contexts

| What to Verify | Services Needed | How to Check |
|---|---|---|
| OSRM routing | Docker (osrm container) | curl route endpoint with Kochi coords |
| VROOM optimization | Docker (vroom container + osrm) | POST job to VROOM API |
| Geocoding | Google API key in .env | python scripts/geocode_batch.py --dry-run |
| Database | Docker (postgres container) | psql connection test |
| Full pipeline | All Docker services | python scripts/import_orders.py + compare_routes.py |
| Dashboard | FastAPI + all services | Open http://localhost:8000 in browser |
| Driver app (PWA) | FastAPI + all services | Open on mobile or responsive mode |
