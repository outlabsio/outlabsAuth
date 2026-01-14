# ABAC Cookbook Example

This example demonstrates ABAC condition groups (AND/OR) and server-derived `resource.*` context.

## Run

1) Seed the DB:

`uv run python reset_test_env.py`

2) Start the server:

`uv run uvicorn main:app --host 127.0.0.1 --port 8005`

3) (Optional) Run the black-box smoke test:

`uv run python ../../scripts/smoke_abac_cookbook.py`

Or run the full reset → start → smoke → shutdown harness:

`uv run python ../../scripts/run_abac_cookbook_smoke.py`

