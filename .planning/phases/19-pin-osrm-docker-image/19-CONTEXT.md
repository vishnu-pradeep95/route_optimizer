# Phase 19: Pin OSRM Docker Image - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix osrm-init container failure (exit 127) that blocks all fresh deployments. The upstream `osrm/osrm-backend:latest` image dropped `/bin/bash`, breaking the entrypoint. Pin the image version and switch to POSIX-compatible shell.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- Fix scope: Apply both version pin and shell fix to `docker-compose.yml` (dev). Also fix `/bin/bash` -> `/bin/sh` in `docker-compose.prod.yml` for consistency (prod already pins v5.27.1 but is vulnerable to the same shell issue)
- OSRM service pinning: Pin the `osrm` service image in dev to `v5.27.1` as well (currently `:latest`), matching prod for consistency
- Version choice: Use `v5.27.1` to match existing prod configuration -- no reason to evaluate newer versions for a bug fix phase
- Entrypoint scripts already use POSIX-compatible syntax (`[ ]`, `set -e`, no bashisms) so `/bin/sh` swap is safe with no script modifications needed

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- None -- this is a Docker configuration fix, no application code involved

### Established Patterns
- `docker-compose.prod.yml` already pins `osrm/osrm-backend:v5.27.1` -- dev should match
- Both compose files use identical entrypoint script structure (idempotent init with POSIX-compatible conditionals)

### Integration Points
- `docker-compose.yml` lines 71, 75, 107: osrm-init image tag, entrypoint shell, osrm service image tag
- `docker-compose.prod.yml` line 92: entrypoint shell (image already pinned at line 88)
- `start.sh` and `bootstrap.sh` depend on `docker compose up` succeeding -- this fix unblocks them

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- straightforward infrastructure fix with clear success criteria from roadmap.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 19-pin-osrm-docker-image*
*Context gathered: 2026-03-07*
