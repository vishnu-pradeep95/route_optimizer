# Environment Comparison: Development vs Production

> **Who this is for:** A developer setting up or debugging production vs development environments.

## Quick Reference

Development exposes all ports for debugging. Production locks down behind Caddy with TLS, requires a license key, and enforces resource limits.

- **Dev:** `docker compose up -d` (uses `docker-compose.yml` by default)
- **Prod:** `docker compose -f docker-compose.prod.yml --env-file .env.production up -d`

---

## Services Comparison

| Service | Dev (`docker-compose.yml`) | Prod (`docker-compose.prod.yml`) |
|---------|---------------------------|----------------------------------|
| **db** | Port 5432 exposed, default password (`routing_dev_pass`) | No exposed port, strong password required (`?` syntax errors if unset), `shm_size=256mb`, 1G memory / 1 CPU limit, backup volume mounted |
| **osrm-init** | Downloads + preprocesses Kerala OSM data if missing | Same behavior, 2G memory / 2 CPU limit |
| **osrm** | Port 5000 exposed | No exposed port, 1G memory / 1 CPU limit, data volume mounted read-only |
| **vroom** | Port 3000 exposed, no healthcheck | No exposed port, 512M memory / 1 CPU limit, healthcheck via `curl`, config volume read-only |
| **api** | Port 8000 exposed, `API_KEY` optional, `ENVIRONMENT` from `.env` | No exposed port (behind Caddy), `API_KEY` required (`?` syntax), `ENVIRONMENT=production` hardcoded, `LICENSE_KEY` set, `license.key` file mounted read-only, 1G memory / 2 CPU limit |
| **caddy** | N/A (not present) | Ports 80/443 exposed, auto-TLS via Let's Encrypt, serves dashboard static files, `DOMAIN` env var, 256M memory / 0.5 CPU limit |
| **dashboard-build** | Builds to shared volume, `VITE_BASE_PATH=/dashboard/` | Builds to shared volume, `VITE_API_URL=""` (same-origin behind Caddy) |
| **dashboard-dev** | Profile `dev` only, port 5173 (Vite hot-reload) | N/A (not available in prod) |
| **db-init** | Runs Alembic migrations, default DB credentials | Runs Alembic migrations, prod DB credentials, 512M memory / 1 CPU limit |

**Activation notes:**

- `dashboard-dev` requires the `dev` profile: `docker compose --profile dev up -d`
- `caddy` only exists in `docker-compose.prod.yml` -- it is the sole entry point for external traffic in production

---

## Environment Variables Comparison

Variables from `.env.example` (dev) and `.env.production.example` (prod):

| Variable | Dev (`.env.example`) | Prod (`.env.production.example`) |
|----------|---------------------|----------------------------------|
| **ENVIRONMENT** | `development` | `production` |
| **API_KEY** | Empty (optional -- no auth required) | Required (`CHANGE-ME-generate-with-openssl-rand-hex-32`). Generate with: `openssl rand -hex 32` |
| **GOOGLE_MAPS_API_KEY** | `your-key-here` (placeholder) | Required for geocoding. Free $200/month credit covers ~40,000 requests |
| **POSTGRES_USER** | `routing` | `routing` (same) |
| **POSTGRES_PASSWORD** | `change-me-in-production` (default fallback: `routing_dev_pass`) | Required -- compose file errors if unset. Generate with: `openssl rand -base64 24` |
| **POSTGRES_DB** | `routing_opt` | `routing_opt` (same) |
| **BACKEND_HOST** | `0.0.0.0` | N/A (set in Dockerfile) |
| **BACKEND_PORT** | `8000` | N/A (set in Dockerfile) |
| **OSRM_URL** | `http://localhost:5000` | Set in compose file: `http://osrm:5000` |
| **VROOM_URL** | `http://localhost:3000` | Set in compose file: `http://vroom:3000` |
| **CORS_ALLOWED_ORIGINS** | `http://localhost:8000,http://localhost:5173` | `https://delivery.example.com` (your actual domain) |
| **RATE_LIMIT_ENABLED** | `true` | `true` (same) |
| **DOMAIN** | N/A (no Caddy in dev) | Required (e.g., `delivery.example.com`). Caddy gets a TLS certificate for this domain |
| **BACKUP_DIR** | N/A | `./backups` (host directory for `pg_dump` files) |
| **RETAIN_COUNT** | N/A | `7` (days of daily backups to keep before rotating) |
| **LICENSE_KEY** | N/A (license enforcement skipped in development) | Required -- API returns 503 on all endpoints without a valid key. Alternative: place key in `./license.key` file |
| **COMPOSE_FILE** | N/A | Optional override for `scripts/deploy.sh` |
| **DB_CONTAINER** | N/A | Optional override for `scripts/backup_db.sh` |
| **ENV_FILE** | N/A | Optional override for script defaults |

---

## Behavioral Differences

| Behavior | Development | Production |
|----------|-------------|------------|
| **License enforcement** | Skipped (`ENVIRONMENT=development`) | Required -- 503 on all endpoints without a valid key |
| **API docs (`/docs`)** | Available at `http://localhost:8000/docs` | Disabled |
| **CORS** | Permissive (`localhost:8000`, `localhost:5173`) | Strict (domain-specific, HTTPS only) |
| **TLS** | None (plain HTTP) | Auto-TLS via Caddy (HTTPS with Let's Encrypt) |
| **Log rotation** | None (logs grow unbounded) | 10 MB x 3 files per container (30 MB max each) |
| **Resource limits** | None (containers can use all host resources) | Per-container memory and CPU limits |
| **Ports exposed to host** | 8000 (API), 5432 (DB), 5000 (OSRM), 3000 (VROOM), 5173 (Vite dev) | 80 (HTTP), 443 (HTTPS) only |
| **Dashboard serving** | API serves from shared volume at `/dashboard/` | Caddy serves static files directly |
| **Database access** | Direct via `localhost:5432` | Docker internal network only. Debug via: `docker compose exec db psql -U routing routing_opt` |
| **HSTS headers** | Disabled | Enabled (via Secweb middleware) |
| **API key auth** | Optional (empty key allowed without warning) | Required (error if unset) |
| **Backup volume** | Not mounted | Mounted at `${BACKUP_DIR}:/backups` |
| **VROOM healthcheck** | None | `curl -f http://localhost:3000/health` every 30s |

---

## Docker Compose Files

| Command | When to Use |
|---------|-------------|
| `docker compose up -d` | Start dev environment (uses `docker-compose.yml` by default) |
| `docker compose --profile dev up -d` | Start dev environment with Vite hot-reload server on port 5173 |
| `docker compose -f docker-compose.prod.yml --env-file .env.production up -d` | Start production environment |
| `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build` | Rebuild and start production (after code changes) |

---

## Config Files

| File | Environment | Purpose |
|------|-------------|---------|
| `docker-compose.yml` | Dev | Service definitions with exposed ports for debugging |
| `docker-compose.prod.yml` | Prod | Locked-down services behind Caddy with resource limits |
| `.env.example` | Dev | Template for development `.env` file (copy to `.env`) |
| `.env.production.example` | Prod | Template for production `.env.production` file |
| `infra/caddy/Caddyfile` | Prod only | Reverse proxy + auto-TLS configuration |
| `license.key` | Prod only | Hardware-bound license key file (alternative to `LICENSE_KEY` env var) |

---

## Named Volumes

| Volume | Dev | Prod | Purpose |
|--------|-----|------|---------|
| `pgdata` | Yes | Yes | PostgreSQL data files |
| `dashboard_assets` | Yes | Yes | Built React dashboard static files |
| `caddy_data` | No | Yes | TLS certificates (Let's Encrypt) |
| `caddy_config` | No | Yes | Caddy runtime configuration cache |
