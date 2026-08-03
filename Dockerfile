# Gatekeyp - Privacy-preserving federated event toolkit
# Multi-stage build for minimal production image

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /usr/sbin/nologin gatekeyp

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY src/ ./src/
COPY pyproject.toml uv.lock ./

# Set environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER gatekeyp

# Expose API port (when gateway is run as a service)
EXPOSE 8000

# Default command (override as needed)
CMD ["python", "-m", "src.api.gateway"]
