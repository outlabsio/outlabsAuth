FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project
COPY . .

# Install the package in development mode
RUN pip install --no-cache-dir -e .

# Install additional runtime dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    motor \
    beanie \
    pydantic \
    python-multipart \
    structlog \
    prometheus-client \
    redis \
    makefun \
    argon2-cffi

# Expose port
EXPOSE 8004

# The command will be specified in docker-compose.yml for hot reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
