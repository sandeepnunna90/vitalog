# H5 — User Auth + Dynamic Patient ID

**Status:** ⬜ pending  
**Branch:** `feat/h5-user-auth`  
**Depends on:** H4

---

## Context

After H4, the server is deployed but open — anyone with the URL can call all tools and all requests resolve to Mark's patient ID. H5 adds Google OAuth via Supabase Auth, creates a patient record per user on first login, and issues a long-lived API key the user puts in their Claude Desktop MCP URL. The server resolves `patient_id` from the API key per-session using Python `contextvars`, replacing the env-var constant.

---

## Goal

- Users sign up via Google OAuth (Supabase Auth)
- First login auto-creates a patient row + generates an API key
- Claude Desktop connects with `?api_key=xxx` in the MCP URL
- Server resolves correct `patient_id` per connection; rejects missing/invalid keys
- Local stdio mode (Claude Desktop + env var) still works unchanged

---

## Implementation Plan

### 1. Supabase setup (dashboard — not code)

1. Enable **Google OAuth** provider in Supabase dashboard → Auth → Providers → Google
   - Create a Google Cloud OAuth 2.0 client (console.cloud.google.com)
   - Set authorised redirect URI to: `https://<project>.supabase.co/auth/v1/callback`
   - Paste Client ID + Secret into Supabase dashboard

2. Add redirect URL for the registration page:
   - Supabase dashboard → Auth → URL Configuration → Redirect URLs
   - Add: `https://vitalog-9z6b.onrender.com/register`

3. Run migration SQL in Supabase SQL editor:
```sql
ALTER TABLE patient ADD COLUMN auth_user_id text UNIQUE;
ALTER TABLE patient ADD COLUMN api_key uuid UNIQUE DEFAULT gen_random_uuid();
```

### 2. `src/persistence/models.py`

Add new fields to `PatientRow` and a new create model:

```python
class PatientRow(_Base):
    patient_id: uuid.UUID
    name: str
    dob: date | None
    created_at: datetime
    auth_user_id: str | None = None   # new
    api_key: uuid.UUID | None = None  # new

class PatientAuthCreate(_Base):
    patient_id: uuid.UUID
    name: str
    auth_user_id: str
    api_key: uuid.UUID
```

### 3. `src/persistence/patient_repository.py`

Add two methods:

```python
def get_by_api_key(self, api_key: uuid.UUID) -> PatientRow | None:
    data = (
        self._client.table(_TABLE)
        .select("*")
        .eq("api_key", str(api_key))
        .execute()
        .data
    )
    if not data:
        return None
    return PatientRow.model_validate(data[0], strict=False)

def upsert_from_auth(self, auth_user_id: str, name: str) -> PatientRow:
    # Check if already exists
    data = (
        self._client.table(_TABLE)
        .select("*")
        .eq("auth_user_id", auth_user_id)
        .execute()
        .data
    )
    if data:
        return PatientRow.model_validate(data[0], strict=False)
    # Create new
    new = PatientAuthCreate(
        patient_id=uuid.uuid4(),
        name=name,
        auth_user_id=auth_user_id,
        api_key=uuid.uuid4(),
    )
    result = (
        self._client.table(_TABLE)
        .insert(new.model_dump(mode="json"))
        .execute()
        .data
    )
    return PatientRow.model_validate(result[0], strict=False)
```

### 4. `src/mcp_server/tools/_guard.py`

Replace the module-level `PATIENT_ID` constant with a contextvar + getter:

```python
import contextvars
import os
import uuid

from src.reference_data.patient_profile import MARK_PATIENT_ID

_patient_id_var: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("patient_id")


def _load_env_patient_id() -> uuid.UUID | None:
    val = os.environ.get("VITALOG_PATIENT_ID")
    if val:
        return uuid.UUID(val)
    return None


def get_patient_id() -> uuid.UUID:
    try:
        return _patient_id_var.get()
    except LookupError:
        # Fallback for local stdio mode: env var → Mark hardcoded
        return _load_env_patient_id() or MARK_PATIENT_ID


def set_patient_id(patient_id: uuid.UUID) -> contextvars.Token[uuid.UUID]:
    return _patient_id_var.set(patient_id)
```

Remove the old `PATIENT_ID` constant and `validate_patient_id()` (no longer needed).

### 5. All 6 tool modules

In each of: `upload.py`, `list_biomarkers.py`, `get_trend.py`, `query.py`, `prepare_summary.py`, `export.py`

Change:
```python
from src.mcp_server.tools._guard import PATIENT_ID
```
To:
```python
from src.mcp_server.tools._guard import get_patient_id
```

Change every call site:
```python
# before
some_workflow(..., PATIENT_ID, ...)
# after
some_workflow(..., get_patient_id(), ...)
```

### 6. `src/mcp_server/auth.py` (new)

Contains:
- `ApiKeyMiddleware` — Starlette `BaseHTTPMiddleware` that intercepts SSE connections at `/sse`, reads `?api_key=`, validates against DB, sets contextvar
- `auth_callback_handler` — ASGI handler for `GET /auth/callback?token=...` that validates the Supabase session token, upserts patient, returns the API key as JSON

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.mcp_server.tools._guard import set_patient_id
from src.orchestration import build_container


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/sse":
            raw = request.query_params.get("api_key")
            if not raw:
                return Response("Missing api_key", status_code=401)
            try:
                api_key = uuid.UUID(raw)
            except ValueError:
                return Response("Invalid api_key", status_code=401)
            container = build_container()
            row = container.patient_repo.get_by_api_key(api_key)
            if row is None:
                return Response("Unknown api_key", status_code=401)
            token = set_patient_id(row.patient_id)
            try:
                return await call_next(request)
            finally:
                # Reset contextvar after request completes
                _patient_id_var.reset(token)
        return await call_next(request)


async def auth_callback_handler(request: Request) -> JSONResponse:
    token = request.query_params.get("token")
    if not token:
        return JSONResponse({"error": "missing token"}, status_code=400)
    container = build_container()
    user = container.supabase.auth.get_user(token)
    if not user or not user.user:
        return JSONResponse({"error": "invalid token"}, status_code=401)
    auth_user_id = user.user.id
    name = user.user.user_metadata.get("full_name") or user.user.email or "User"
    row = container.patient_repo.upsert_from_auth(auth_user_id, name)
    return JSONResponse({"api_key": str(row.api_key)})
```

Note: `_patient_id_var` import needs to be added to auth.py — import from `_guard`.

### 7. `src/mcp_server/static/register.html` (new)

Minimal single-page HTML:
- Supabase JS SDK (CDN)
- "Sign in with Google" button
- After OAuth callback: POST token to `/auth/callback`, display API key
- Show ready-to-paste Claude Desktop config snippet

### 8. `scripts/run_mcp_server.py`

In SSE mode, wrap the FastMCP ASGI app with middleware and mount extra routes:

```python
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from src.mcp_server.auth import ApiKeyMiddleware, auth_callback_handler

if transport == "sse":
    # Get the FastMCP ASGI app (exact API TBD — check mcp.sse_app() or similar)
    fastmcp_app = mcp.sse_app()
    
    app = Starlette(routes=[
        Route("/health", lambda r: PlainTextResponse("ok")),
        Route("/auth/callback", auth_callback_handler),
        Mount("/register", StaticFiles(directory="src/mcp_server/static", html=True)),
        Mount("/", fastmcp_app),
    ])
    app.add_middleware(ApiKeyMiddleware)
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**Implementation note:** The exact FastMCP API for extracting the ASGI app must be confirmed during implementation by checking the installed `mcp` package version. Look for `mcp.sse_app()`, `mcp.starlette_app()`, or similar. If FastMCP doesn't expose this, use `uvicorn` directly on the wrapped app.

### 9. `src/orchestration/container.py`

Add `patient_repo` to `ServiceContainer` if not already present, so `auth.py` can access it via `container.patient_repo`.

---

## Files to create/modify

| File | Change |
|------|--------|
| Supabase dashboard | Enable Google OAuth; add migration SQL |
| `src/persistence/models.py` | Add `auth_user_id`, `api_key` to PatientRow; add PatientAuthCreate |
| `src/persistence/patient_repository.py` | Add `get_by_api_key`, `upsert_from_auth` |
| `src/mcp_server/tools/_guard.py` | Replace PATIENT_ID constant with contextvar + `get_patient_id()` |
| `upload.py`, `list_biomarkers.py`, `get_trend.py`, `query.py`, `prepare_summary.py`, `export.py` | Update PATIENT_ID → get_patient_id() |
| `src/mcp_server/auth.py` | New — middleware + auth callback handler |
| `src/mcp_server/static/register.html` | New — registration page |
| `scripts/run_mcp_server.py` | Wrap app with middleware, mount /health, /auth/callback, /register |

---

## Claude Desktop config (remote + auth)

```json
{
  "mcpServers": {
    "vitalog": {
      "command": "npx",
      "args": ["mcp-remote", "https://vitalog-9z6b.onrender.com/sse?api_key=YOUR_KEY"]
    }
  }
}
```

Local stdio mode (unchanged):
```json
{
  "mcpServers": {
    "vitalog": {
      "command": "uv",
      "args": ["run", "python", "scripts/run_mcp_server.py"],
      "cwd": "/absolute/path/to/vitalog"
    }
  }
}
```

---

## Verification

1. Visit `https://vitalog-9z6b.onrender.com/register` → "Sign in with Google" → redirected to Google → back to page with API key displayed
2. Check Supabase `patient` table — new row with `auth_user_id` + `api_key` populated
3. Claude Desktop config updated with `?api_key=xxx` — restart Claude Desktop — Vitalog tools appear
4. `list_biomarkers` returns the correct user's data (not Mark's)
5. Second user registers → gets a different API key → different patient row → tools isolated
6. Invalid API key in URL → Claude Desktop shows connection error (server returns 401)
7. Local stdio mode: `VITALOG_PATIENT_ID` env var still resolves correctly without API key
8. `make test` passes — no regressions
9. `make typecheck` passes
