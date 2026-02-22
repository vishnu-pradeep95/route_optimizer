FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY core/ core/
COPY apps/ apps/

# Serve the driver PWA as static files at /driver/
# The FastAPI app mounts this directory

EXPOSE 8000

CMD ["uvicorn", "apps.kerala_delivery.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
