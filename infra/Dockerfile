# =============================================================================
# Multi-stage Dockerfile for the Kerala Delivery Route Optimizer API
# =============================================================================
# Why multi-stage?
# Stage 1 ("builder") installs all Python packages (which may need compilers/headers).
# Stage 2 ("runtime") copies only the installed packages + source code.
# Result: ~60% smaller image (no gcc, no pip cache, no build files).
# A smaller image = faster deploys, smaller attack surface, less disk on the VPS.
# See: https://docs.docker.com/build/building/multi-stage/
#
# This image supports two entrypoints:
#   - Default: run the FastAPI API server (uvicorn)
#   - Override: run Alembic migrations (alembic upgrade head)
# The deploy script runs migrations before starting the API.
# =============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
# Installs Python dependencies into a virtual environment.
# We use a venv so we can copy ONLY the venv to the runtime stage
# (instead of the entire site-packages mixed with system packages).
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies some Python packages need (e.g. asyncpg needs gcc)
# Why --no-install-recommends? Skips optional packages, keeps layer smaller.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Create a venv and install into it.
# Why a venv in Docker? It gives us a clean, self-contained directory to COPY
# to the runtime stage. Without it, packages scatter across /usr/local/lib/
# and it's hard to separate build deps from runtime deps.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
# Minimal image with only what's needed to run the application.
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install only the runtime C library that asyncpg/psycopg need.
# gcc is NOT needed at runtime — only libpq (PostgreSQL client lib).
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Put the venv's Python and pip on PATH so they're the default.
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code.
# Why copy these specific directories (not COPY . .)?
# - Avoids copying .git/, node_modules/, data/ (large, not needed)
# - Makes Docker layer caching more effective: source changes don't
#   invalidate the pip-install layer
# - Keeps the image minimal and auditable
COPY core/ core/
COPY apps/ apps/
COPY scripts/ scripts/

# Copy Alembic config + migration scripts.
# These are needed inside the container so the deploy script can run
# `alembic upgrade head` before starting the API server.
# alembic.ini must be at /app/ (WORKDIR) because it references
# script_location = %(here)s/infra/alembic (relative to its own location).
COPY alembic.ini alembic.ini
COPY infra/alembic/ infra/alembic/

# SECURITY: Run as non-root user.
# By default, Docker containers run as root. If an attacker exploits a vulnerability
# in the application, they get root access to the container (and potentially the host
# via container escapes). Running as a non-root user limits blast radius.
# See: https://docs.docker.com/engine/security/#linux-kernel-capabilities
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# Create a data directory the non-root user can write to.
# The API writes uploaded CSVs to /app/data temporarily.
RUN mkdir -p /app/data && chown appuser:appgroup /app/data

USER appuser

# Health check — Docker (and Compose/Swarm/K8s) uses this to determine
# if the container is ready to accept traffic. Caddy/Nginx won't route
# to an unhealthy upstream.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Default command: run the API server.
# --workers 2: two uvicorn workers handle concurrent requests.
#   Why 2? Our VPS target is 2-4 vCPU. Rule of thumb: (2 × CPU) + 1
#   but we keep it conservative since OSRM/VROOM also need CPU.
#   Adjust via UVICORN_WORKERS env var in production.
# --proxy-headers: trust X-Forwarded-For from Caddy reverse proxy
#   so rate limiting sees real client IPs, not 172.x.x.x (Docker network).
# --forwarded-allow-ips="*": allow any Docker-internal IP to set forwarded
#   headers. Safe because Caddy is the only entry point in production.
# See: https://www.uvicorn.org/deployment/
CMD ["uvicorn", "apps.kerala_delivery.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
