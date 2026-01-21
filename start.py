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
    {"name": "simple      - SimpleRBAC API (port 8003)", "value": "simple"},
    {"name": "enterprise  - EnterpriseRBAC API (port 8004)", "value": "enterprise"},
    {"name": "ui          - Admin UI (port 3000)", "value": "ui"},
    {"name": "obs         - Start observability stack", "value": "obs"},
    {"name": "obs-stop    - Stop observability stack", "value": "obs-stop"},
]

ROOT = os.path.dirname(os.path.abspath(__file__))

CONFIGS = {
    "simple": {
        "cwd": os.path.join(ROOT, "examples", "simple_rbac"),
        "cmd": ["uv", "run", "uvicorn", "main:app", "--port", "8003", "--reload"],
        "env": {
            "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/blog_simple_rbac",
            "SECRET_KEY": "simple-rbac-secret-key-change-in-production",
            "REDIS_URL": "redis://localhost:6380",
        },
        "port": 8003,
    },
    "enterprise": {
        "cwd": os.path.join(ROOT, "examples", "enterprise_rbac"),
        "cmd": ["uv", "run", "uvicorn", "main:app", "--port", "8004", "--reload"],
        "env": {
            "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac",
            "SECRET_KEY": "enterprise-rbac-secret-key-change-in-production",
            "REDIS_URL": "redis://localhost:6380",
        },
        "port": 8004,
    },
    "ui": {
        "cwd": os.path.join(ROOT, "auth-ui"),
        "cmd": ["bun", "run", "dev"],
        "env": {},
    },
    "obs": {
        "cwd": ROOT,
        "cmd": [
            "docker",
            "compose",
            "-f",
            "docker-compose.observability.yml",
            "up",
            "-d",
        ],
        "env": {},
        "background": True,
    },
    "obs-stop": {
        "cwd": ROOT,
        "cmd": ["docker", "compose", "-f", "docker-compose.observability.yml", "down"],
        "env": {},
        "background": True,
    },
}


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

    # Run background tasks first
    for svc in background:
        cfg = CONFIGS[svc]
        print(f"\n→ Running {svc}...")
        subprocess.run(cfg["cmd"], cwd=cfg["cwd"], env={**os.environ, **cfg["env"]})

    if not foreground:
        return

    # Determine API port for UI (prefer simple over enterprise if both selected)
    api_port = None
    if "simple" in foreground:
        api_port = CONFIGS["simple"]["port"]
    elif "enterprise" in foreground:
        api_port = CONFIGS["enterprise"]["port"]

    # Start foreground services
    processes = []
    for svc in foreground:
        cfg = CONFIGS[svc]
        print(f"\n→ Starting {svc}...")
        env = {**os.environ, **cfg["env"]}

        # If starting UI and we have an API, set the API URL
        if svc == "ui" and api_port:
            env["NUXT_PUBLIC_API_BASE_URL"] = f"http://localhost:{api_port}"
            print(f"  (connecting to API on port {api_port})")

        p = subprocess.Popen(cfg["cmd"], cwd=cfg["cwd"], env=env)
        processes.append((svc, p))

    if processes:
        print(f"\n✓ Running: {', '.join(foreground)}")
        print("  Press Ctrl+C to stop all\n")

        def shutdown(sig, frame):
            print("\n\nShutting down...")
            for name, p in processes:
                p.terminate()
            for name, p in processes:
                p.wait()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Wait for all processes
        for name, p in processes:
            p.wait()


if __name__ == "__main__":
    main()
