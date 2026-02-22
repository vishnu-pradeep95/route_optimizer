FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY core/ core/
COPY apps/ apps/

# SECURITY: Run as non-root user.
# By default, Docker containers run as root. If an attacker exploits a vulnerability
# in the application, they get root access to the container (and potentially the host
# via container escapes). Running as a non-root user limits blast radius.
# See: https://docs.docker.com/engine/security/#linux-kernel-capabilities
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "apps.kerala_delivery.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
