FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy the entire project
COPY . /app

# Install Python dependencies using uv
RUN cd /app && uv sync

# Install outlabs-auth in editable mode for hot reload
RUN cd /app && uv pip install -e .

# Install additional dependencies for running the example
RUN cd /app && uv pip install uvicorn[standard] redis

# Expose port
EXPOSE 8002

# Add the virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# The command will be specified in docker-compose.yml for flexibility
CMD ["uvicorn", "examples.enterprise_rbac.main:app", "--host", "0.0.0.0", "--port", "8002"]
