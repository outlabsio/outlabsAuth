# /// script
# requires-python = ">=3.10"
# dependencies = ["questionary"]
# ///
"""Interactive service starter for OutlabsAuth development."""

import os
import signal
import subprocess
import sys

import questionary

SERVICES = [
    {"name": "simple      - SimpleRBAC API (port 8000)", "value": "simple"},
    {"name": "enterprise  - EnterpriseRBAC API (port 8000)", "value": "enterprise"},
    {
        "name": "obs         - Observability stack (Grafana, Prometheus, Loki)",
        "value": "obs",
    },
]

ROOT = os.path.dirname(os.path.abspath(__file__))
OBSERVABILITY_DIR = os.path.join(ROOT, "observability")

CONFIGS = {
    "simple": {
        "cwd": os.path.join(ROOT, "examples", "simple_rbac"),
        "cmd": ["uv", "run", "uvicorn", "main:app", "--port", "8000", "--reload"],
        "env": {
            "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/blog_simple_rbac",
            "SECRET_KEY": "simple-rbac-secret-key-change-in-production",
            "REDIS_URL": "redis://localhost:6380",
        },
        "port": 8000,
    },
    "enterprise": {
        "cwd": os.path.join(ROOT, "examples", "enterprise_rbac"),
        "cmd": ["uv", "run", "uvicorn", "main:app", "--port", "8000", "--reload"],
        "env": {
            "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac",
            "SECRET_KEY": "enterprise-rbac-secret-key-change-in-production",
            "REDIS_URL": "redis://localhost:6380",
        },
        "port": 8000,
    },
    "obs": {
        "cwd": OBSERVABILITY_DIR,
        "cmd": ["docker", "compose", "up", "-d"],
        "env": {},
        "background": True,
        "setup_required": True,
    },
}


def setup_observability(api_port=None):
    """Ensure observability stack is configured before starting."""
    env_file = os.path.join(OBSERVABILITY_DIR, ".env")
    prometheus_config = os.path.join(OBSERVABILITY_DIR, "prometheus", "prometheus.yml")

    # Check if .env exists, create from example if not
    if not os.path.exists(env_file):
        example_file = os.path.join(OBSERVABILITY_DIR, ".env.example")
        if os.path.exists(example_file):
            print("  Creating observability/.env from .env.example...")
            with open(example_file) as f:
                content = f.read()
            # Update API_PORT if we know it
            if api_port:
                content = content.replace("API_PORT=8000", f"API_PORT={api_port}")
            with open(env_file, "w") as f:
                f.write(content)

    # Update API_PORT in .env if we have one
    if api_port and os.path.exists(env_file):
        with open(env_file) as f:
            content = f.read()
        # Update API_PORT line
        import re

        new_content = re.sub(r"API_PORT=\d+", f"API_PORT={api_port}", content)
        if new_content != content:
            with open(env_file, "w") as f:
                f.write(new_content)
            print(f"  Updated observability API_PORT to {api_port}")

    # Run setup.sh if prometheus.yml doesn't exist
    if not os.path.exists(prometheus_config):
        print("  Running observability setup...")
        subprocess.run(["./setup.sh"], cwd=OBSERVABILITY_DIR, check=True)


def main():
    print("\n  OutlabsAuth Service Starter\n")

    selected = questionary.checkbox(
        "Select services (space=toggle, enter=confirm):",
        choices=[questionary.Choice(s["name"], value=s["value"]) for s in SERVICES],
    ).ask()

    if not selected:
        print("Nothing selected, exiting.")
        return

    # Separate background tasks (obs, obs-stop) from foreground services
    background = [s for s in selected if CONFIGS[s].get("background")]
    foreground = [s for s in selected if not CONFIGS[s].get("background")]

    # Determine API port (prefer simple over enterprise if both selected)
    api_port = None
    if "simple" in foreground:
        api_port = CONFIGS["simple"]["port"]
    elif "enterprise" in foreground:
        api_port = CONFIGS["enterprise"]["port"]

    # Run background tasks first
    for svc in background:
        cfg = CONFIGS[svc]
        print(f"\n→ Running {svc}...")

        # Setup observability if needed
        if cfg.get("setup_required"):
            setup_observability(api_port)

        subprocess.run(cfg["cmd"], cwd=cfg["cwd"], env={**os.environ, **cfg["env"]})

    if not foreground:
        return

    # Start foreground services
    processes = []
    for svc in foreground:
        cfg = CONFIGS[svc]
        print(f"\n→ Starting {svc}...")
        env = {**os.environ, **cfg["env"]}

        p = subprocess.Popen(cfg["cmd"], cwd=cfg["cwd"], env=env)
        processes.append((svc, p))

    if processes:
        print(f"\n✓ Running: {', '.join(foreground)}")
        print("  Press Ctrl+C to stop all\n")

        def shutdown(sig, frame):
            print("\n\nStopping services...")
            for name, p in processes:
                print(f"  Stopping {name}...")
                p.terminate()
            for name, p in processes:
                p.wait()
            print("All services stopped.")
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Wait for all processes
        for name, p in processes:
            p.wait()


if __name__ == "__main__":
    main()
