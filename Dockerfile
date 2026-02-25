# Backend Docker Image
# Build: docker build -t my-community-backend:latest ./2-cho-community-be

FROM python:3.11-slim

ARG APP_VERSION=1.0.0
LABEL maintainer="corpseonthemission@icloud.com"
LABEL version="${APP_VERSION}"
LABEL description="my-community-be: A community platform backend API built with FastAPI and served by Uvicorn"

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create directories for uploads
RUN mkdir -p uploads/posts uploads/profiles

# Create non-root user for security
RUN groupadd -g 1000 app \
    && useradd -r -u 1000 -g app -d /home/app -s /usr/sbin/nologin app \
    && chown -R app:app /app

# Use the virtual environment created by uv
ENV PATH="/app/.venv/bin:$PATH"

# Run as non-root user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
