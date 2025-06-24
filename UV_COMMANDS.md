# UV Commands Reference

This project now uses [uv](https://github.com/astral-sh/uv) for dependency management and virtual environments.

## Common Commands

### Setup and Installation

```bash
# Install all dependencies (run this after cloning)
uv sync

# Install additional packages
uv add package_name

# Install development dependencies
uv add --dev package_name

# Install stress testing dependencies
uv sync --extra stress
```

### Running the Application

```bash
# Run the FastAPI server
uv run uvicorn api.main:app --reload

# Run the seeding script
uv run python scripts/seed_test_environment.py

# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_auth_routes.py
```

### Development Tools

```bash
# Format code with black
uv run black .

# Sort imports with isort
uv run isort .

# Run linting with flake8
uv run flake8 .

# Type checking with mypy
uv run mypy .
```

### Stress Testing

```bash
# Install stress testing dependencies
uv sync --extra stress

# Run stress tests
uv run python stress_test/ddos_stress_test.py
```

### Environment Management

```bash
# Show current environment info
uv info

# Show installed packages
uv tree

# Update lock file
uv lock

# Clean cache
uv cache clean
```

## Migration Notes

- Migrated from traditional venv + pip setup
- All dependencies are now managed in `pyproject.toml`
- Lock file `uv.lock` ensures reproducible installs
- Much faster dependency resolution and installation than pip
