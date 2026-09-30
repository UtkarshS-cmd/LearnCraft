# =============================================================================
# LearnCraft - Docker Image
# Flask-based offline-first learning platform
# =============================================================================

# Use Python 3.11 slim for smaller image size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=5000 \
    APP_ENV=production

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for any packages)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt ./backend/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code, preserving the repo layout (backend/ + frontend/).
# This matters: app.main resolves templates/static/DB from the project root
# (parents[2] of backend/app/main.py == /app), exactly like a local checkout.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Run from backend/ so `server`, `app` and `data` import exactly as locally.
WORKDIR /app/backend

# Create necessary directories
RUN mkdir -p /app/backend/data

# Set proper permissions
RUN chmod +x server.py

# Expose port (APP_PORT may remap it at runtime; compose maps ${APP_PORT:-5000})
EXPOSE 5000

# Health check (uses APP_PORT inside the container, defaults to 5000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('APP_PORT','5000')+'/api/health')" || exit 1

# Run with gunicorn for production. The dev server (server.py / app.main) is
# never exposed to the Internet: gunicorn binds 0.0.0.0 inside the container
# and a reverse proxy (see docs/deployment/production.md) terminates HTTPS.
# ${APP_PORT:-5000} keeps frontend/backend same-origin without rebuilding.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${APP_PORT:-5000} --workers 4 --timeout 120 server:app"]

