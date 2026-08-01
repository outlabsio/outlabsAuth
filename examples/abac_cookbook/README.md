# ABAC Cookbook Example

This example demonstrates **Attribute-Based Access Control (ABAC)** using server-derived resource context.

## Wrapper Scenario

**Goal**: "Editors can update documents ONLY if they are in `draft` or `review` status. They cannot update `published` documents."

**Implementation**:
1.  **Server-Derived Context**: The API endpoint middleware (`main.py`) fetches the document from the DB and passes its `status` to the permission check. The client cannot forge this.
2.  **Condition Group**: A persistent rule is added to the `document:update` permission:
    -   `resource.status == 'draft'` OR `resource.status == 'review'`

## How to Run

### 1. Setup & Start
Seed the database with users (Admin, Editor) and documents (Draft, Review, Published):

```bash
uv run python reset_test_env.py
```

Start the API server:

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8005
```

### 2. Configure & Test (The "Smoke" Test)
The smoke script acts as the **Admin** to configure the ABAC rules via the API, and then acts as the **Editor** to verify them.

```bash
uv run python ../../scripts/smoke_abac_cookbook.py
```

**What this script does:**
1.  **Admin Login**: Authenticates as superuser.
2.  **Configuration**: Adds the ABAC conditions (`status=draft OR status=review`) to the `document:update` permission via the HTTP API.
3.  **Verification**:
    -   ✅ Log in as Editor.
    -   ✅ Update a `draft` document -> **ALLOWED (200)**.
    -   ❌ Update a `published` document -> **DENIED (403)**.

