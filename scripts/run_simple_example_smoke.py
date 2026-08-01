#!/usr/bin/env python3
"""Seed, start, and exercise the repository-owned SimpleRBAC FastAPI example."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = ROOT / "examples" / "simple_rbac"
RESET_SCRIPT = EXAMPLE_DIR / "reset_test_env.py"
API_TESTS = EXAMPLE_DIR / "test_api.py"
UV_RUN = ["uv", "run", "--project", str(ROOT), "--extra", "all"]


async def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    async for line in process.stdout:
        sys.stdout.buffer.write(line)
    if await process.wait() != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


async def _wait_ready(base_url: str, timeout_seconds: float = 40.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(base_url=base_url, timeout=2.0) as client:
        last_error = "no response"
        while time.monotonic() < deadline:
            try:
                response = await client.get("/health")
                if response.status_code == 200:
                    return
                last_error = f"/health -> {response.status_code}"
            except httpx.HTTPError as error:
                last_error = str(error)
            await asyncio.sleep(0.3)
    raise RuntimeError(f"SimpleRBAC example was not ready within {timeout_seconds}s: {last_error}")


async def _terminate(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8003"))
    base_url = f"http://{host}:{port}"
    env = os.environ.copy()

    print("\n==> Resetting SimpleRBAC example DB/seed data")
    await _run([*UV_RUN, "python", str(RESET_SCRIPT)], cwd=EXAMPLE_DIR, env=env)

    print("\n==> Starting SimpleRBAC uvicorn")
    server = await asyncio.create_subprocess_exec(
        *UV_RUN,
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
    stream_task: asyncio.Task[None] | None = None
    try:
        assert server.stdout is not None

        async def _stream() -> None:
            async for line in server.stdout:
                sys.stdout.buffer.write(line)

        stream_task = asyncio.create_task(_stream())
        await _wait_ready(base_url)

        print("\n==> Running SimpleRBAC live API checks")
        await _run([*UV_RUN, "python", str(API_TESTS)], cwd=EXAMPLE_DIR, env=env)
        print("\n==> SimpleRBAC example checks OK")
    finally:
        await _terminate(server)
        if stream_task is not None:
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
