#!/usr/bin/env python3
"""
Black-box smoke runner for the ABAC cookbook example.

Usage:
  uv run python scripts/run_abac_cookbook_smoke.py
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = ROOT / "examples" / "abac_cookbook"
RESET_SCRIPT = EXAMPLE_DIR / "reset_test_env.py"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke_abac_cookbook.py"


def _env(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val else default


async def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None
    async for line in proc.stdout:
        sys.stdout.buffer.write(line)
        await asyncio.sleep(0)
    rc = await proc.wait()
    if rc != 0:
        raise RuntimeError(f"Command failed ({rc}): {' '.join(cmd)}")


async def _wait_ready(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    async with httpx.AsyncClient(base_url=base_url, timeout=2.0) as client:
        last_err: str | None = None
        while time.time() < deadline:
            try:
                r = await client.get("/health")
                if r.status_code == 200:
                    return
                last_err = f"/health -> {r.status_code}"
            except Exception as e:
                last_err = str(e)
            await asyncio.sleep(0.3)
        raise RuntimeError(f"Server not ready within {timeout_s}s: {last_err}")


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            return
        await proc.wait()


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    host = _env("HOST", "127.0.0.1")
    port = int(_env("PORT", "8005"))
    base_url = f"http://{host}:{port}"

    env = os.environ.copy()
    if database_url:
        env["DATABASE_URL"] = database_url

    print("\n==> Resetting example DB/seed data")
    await _run(["uv", "run", "python", str(RESET_SCRIPT)], cwd=EXAMPLE_DIR, env=env)

    print("\n==> Starting uvicorn")
    server_proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "uvicorn",
        "main:app",
        "--host",
        host,
        "--port",
        str(port),
        cwd=str(EXAMPLE_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        assert server_proc.stdout is not None

        async def _stream():
            async for line in server_proc.stdout:
                sys.stdout.buffer.write(line)
                await asyncio.sleep(0)

        stream_task = asyncio.create_task(_stream())

        print("\n==> Waiting for readiness")
        await _wait_ready(base_url, timeout_s=40.0)

        print("\n==> Running smoke script")
        smoke_env = env.copy()
        smoke_env["BASE_URL"] = f"{base_url}/v1"
        await _run(["uv", "run", "python", str(SMOKE_SCRIPT)], cwd=ROOT, env=smoke_env)

        print("\n==> Smoke OK")
    finally:
        print("\n==> Shutting down server")
        await _terminate(server_proc)
        if "stream_task" in locals():
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
