# H5 — User Auth + Dynamic Patient ID

**Status:** ⬜ pending  
**Branch:** `feat/h5-user-auth`  
**Depends on:** H4

---

## Context

After H4, the server is deployed but open — anyone with the URL can call all tools and all requests resolve to Mark's patient ID. H5 adds proper MCP OAuth 2.0 authentication (the same flow used by GitHub and Slack MCP integrations). The user configures Claude Desktop with just the server URL — no credentials in the config. On first connection `mcp-remote` opens a browser window for Google login automatically. After login, a patient row is created and a bearer token is issued; `mcp-remote` stores it locally and sends it on every subsequent SSE connection. The server resolves `patient_id` from the bearer token per-session using Python `contextvars`.

---

## Goal

- Claude Desktop config contains only the server URL — no API keys, no headers
- First connection: browser opens automatically for Google login
- Patient row auto-created on first login; existing users get the same token
- Server resolves correct `patient_id` per connection from `Authorization: Bearer` header
- Invalid / missing token → 401; connection refused
- `patient_id` is always resolved from the DB — no env var fallback, no hardcoded IDs

---

## MCP OAuth 2.0 Flow

```
mcp-remote                  Our server              Supabase / Google
    │                           │                           │
    │── GET /sse ──────────────►│                           │
    │◄─ 401 (with metadata) ────│                           │
    │                           │                           │
    │  (opens browser)          │                           │
    │── GET /authorize?         │                           │
    │   code_challenge=...  ───►│                           │
    │   state=...               │── redirect to Google ────►│
    │   redirect_uri=localhost  │                           │
    │                           │◄── GET /auth/callback ────│
    │                           │    (Supabase code)        │
    │                           │── exchange code ─────────►│
    │                           │◄── user info + session ───│
    │                           │   (upsert patient row)    │
    │◄── redirect to localhost ─│                           │
    │    ?code=<auth_code>      │                           │
    │                           │                           │
    │── POST /token ───────────►│                           │
    │   code=<auth_code>        │                           │
    │   code_verifier=...       │                           │
    │◄── access_token ──────────│                           │
    │    (= patient api_key)    │                           │
    │                           │                           │
    │── GET /sse ───────────────│                           │
    │   Authorization: Bearer   │                           │
    │◄── 200 SSE stream ────────│                           │
```

`mcp-remote` stores the access token locally — subsequent connections are silent (no browser).

---

## Implementation Plan

### 1. Supabase setup (dashboard — not code)

1. Enable **Google OAuth** provider: Auth → Providers → Google
   - Create Google Cloud OAuth 2.0 client at console.cloud.google.com
   - Set authorised redirect URI to: `https://<supabase-project>.supabase.co/auth/v1/callback`
   - Paste Client ID + Secret into Supabase dashboard

2. Auth → URL Configuration → Redirect URLs → add both:
   - `https://vitalog-9z6b.onrender.com/auth/callback` (production)
   - `http://localhost:8000/auth/callback` (local dev)

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
    # lookup by api_key (used as bearer token)

def upsert_from_auth(self, auth_user_id: str, name: str) -> PatientRow:
    # return existing row if auth_user_id already present, else insert new
```

### 4. `src/mcp_server/tools/_guard.py`

Replace the module-level `PATIENT_ID` constant with a contextvar + getter. No fallback — if the contextvar is not set the call raises `LookupError`, which is the correct failure mode when a request reaches a tool without going through auth middleware.

```python
_patient_id_var: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("patient_id")

def get_patient_id() -> uuid.UUID:
    return _patient_id_var.get()  # raises LookupError if middleware didn't set it

def set_patient_id(patient_id: uuid.UUID) -> contextvars.Token[uuid.UUID]:
    return _patient_id_var.set(patient_id)
```

Remove: `PATIENT_ID` constant, `validate_patient_id()`, `_load_env_patient_id()`, any `MARK_PATIENT_ID` import, any `VITALOG_PATIENT_ID` reference.

### 5. All 6 tool modules

In each of `upload.py`, `list_biomarkers.py`, `get_trend.py`, `query.py`, `prepare_summary.py`, `export.py`:

```python
# before
from src.mcp_server.tools._guard import PATIENT_ID
# after
from src.mcp_server.tools._guard import get_patient_id
```

Change every call site: `PATIENT_ID` → `get_patient_id()`.

### 6. `src/mcp_server/auth.py` (new)

Three responsibilities:

**a) `BearerMiddleware`** — Pure ASGI middleware (not `BaseHTTPMiddleware`, which buffers SSE):
- On `/sse` requests: read `Authorization: Bearer <token>`, validate UUID, lookup patient via `get_by_api_key()`, set contextvar, yield to next handler, reset contextvar after
- Missing / invalid token → immediate 401

**b) OAuth 2.0 endpoints:**

`GET /.well-known/oauth-authorization-server` — metadata JSON built dynamically from `BASE_URL` env var (defaults to `http://localhost:8000`):
```json
{
  "issuer": "<BASE_URL>",
  "authorization_endpoint": "<BASE_URL>/authorize",
  "token_endpoint": "<BASE_URL>/token",
  "response_types_supported": ["code"],
  "code_challenge_methods_supported": ["S256"]
}
```

`GET /authorize?code_challenge=...&state=...&redirect_uri=...`:
- Store `{state → (code_challenge, redirect_uri)}` in in-memory dict (TTL ~10 min)
- Generate Supabase Google OAuth URL with our `/auth/callback` + encoded `state` as redirect
- Redirect browser there

`GET /auth/callback?code=...&state=...`:
- Supabase posts back here after Google login with a `code`
- Exchange code via `supabase.auth.exchange_code_for_session(code)`
- Get user info (`auth_user_id`, `name`/`email`)
- Upsert patient row → get `api_key`
- Generate short-lived `auth_code` UUID, store `{auth_code → api_key}` in memory
- Retrieve original `redirect_uri` from state, redirect to `redirect_uri?code=<auth_code>&state=<state>`

`POST /token` (form body: `code=...`, `code_verifier=...`):
- Look up `api_key` by `auth_code` (single-use, delete after lookup)
- Validate `code_verifier` against stored `code_challenge` (S256)
- Return `{"access_token": str(api_key), "token_type": "bearer"}`

**c) In-memory state store** — simple `dict` for `authorize_state` and `auth_codes`. These are short-lived (minutes); no persistence needed. Add TTL cleanup on lookup.

### 7. `render.yaml`

- Remove `VITALOG_PATIENT_ID` — no longer needed after H5.
- Add `BASE_URL` with value `https://vitalog-9z6b.onrender.com` (used to build OAuth metadata and callback URLs dynamically). Set it in the Render dashboard too.

Local dev: set `BASE_URL=http://localhost:8000` in `.env` (or omit — `auth.py` defaults to `http://localhost:8000`).

### 8. `scripts/run_mcp_server.py`

In SSE mode, wrap the app and mount OAuth routes:

```python
from src.mcp_server.auth import (
    BearerMiddleware,
    oauth_metadata_handler,
    authorize_handler,
    auth_callback_handler,
    token_handler,
)

app = mcp.sse_app()
app.add_route("/.well-known/oauth-authorization-server", oauth_metadata_handler)
app.add_route("/authorize", authorize_handler)
app.add_route("/auth/callback", auth_callback_handler)
app.add_route("/token", token_handler, methods=["POST"])
app.add_route("/health", health)
# Wrap with pure-ASGI bearer middleware
app = BearerMiddleware(app)

uvicorn.run(app, host="0.0.0.0", port=port)
```

### 9. `src/orchestration/container.py`

Verify `patient_repo` is accessible on `ServiceContainer` (likely already present — check during implementation).

---

## Files to create/modify

| File | Change |
|------|--------|
| Supabase dashboard | Enable Google OAuth; add callback redirect URL; run migration SQL |
| `src/persistence/models.py` | Add `auth_user_id`, `api_key` to `PatientRow`; add `PatientAuthCreate` |
| `src/persistence/patient_repository.py` | Add `get_by_api_key`, `upsert_from_auth` |
| `src/mcp_server/tools/_guard.py` | Replace `PATIENT_ID` constant with contextvar + `get_patient_id()` |
| `upload.py`, `list_biomarkers.py`, `get_trend.py`, `query.py`, `prepare_summary.py`, `export.py` | `PATIENT_ID` → `get_patient_id()` |
| `src/mcp_server/auth.py` | New — `BearerMiddleware` + 4 OAuth route handlers |
| `render.yaml` | Remove `VITALOG_PATIENT_ID`; add `BASE_URL=https://vitalog-9z6b.onrender.com` |
| `scripts/run_mcp_server.py` | Mount OAuth routes + wrap with `BearerMiddleware` |

---

## Claude Desktop config

Remote (Render):
```json
{
  "mcpServers": {
    "vitalog": {
      "command": "npx",
      "args": ["mcp-remote", "https://vitalog-9z6b.onrender.com/sse"]
    }
  }
}
```

Local dev (run `MCP_TRANSPORT=sse PORT=8000 uv run python scripts/run_mcp_server.py` first):
```json
{
  "mcpServers": {
    "vitalog": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/sse"]
    }
  }
}
```

First connection: browser opens automatically for Google login. Subsequent connections: silent (token cached by `mcp-remote`). SSE + OAuth is the only supported mode after H5.

---

## Verification

1. Claude Desktop config has only the URL — no API key, no header
2. First connection → browser opens → Google login → lands back on a success page
3. Supabase `patient` table has new row with `auth_user_id` + `api_key` populated
4. Claude Desktop tools appear — `list_biomarkers` returns the correct user's data
5. Second user logs in → gets a different `api_key` → different patient row → tools isolated
6. Tampered / missing bearer token → 401 → Claude Desktop shows connection error
7. `make test` passes; `make typecheck` passes

---

## Security notes

- Bearer token = patient `api_key` UUID (128-bit random) — not a Supabase JWT
- In-memory OAuth state has TTL; auth codes are single-use
- Pure ASGI middleware avoids `BaseHTTPMiddleware` SSE buffering issue
- HTTPS enforced by Render; bearer token never travels over plain HTTP
- H5 is still "you have the token" not "you prove you own the token per-request" — full JWT validation is v1+ scope

---

### Implementation (2026-05-22)

**PR:** #39 — `feat(auth): MCP OAuth 2.0 + per-request patient_id via contextvar (H5)`  
**Branch:** `feat/h5-user-auth` → merged to `main`

**Files created:**
- `src/mcp_server/auth.py` — `BearerMiddleware` (pure ASGI) + 4 OAuth route handlers (`oauth_metadata_handler`, `authorize_handler`, `auth_callback_handler`, `token_handler`) + RFC 7591 `registration_handler`
- `migrations/004_add_auth_columns.sql` — `ALTER TABLE patient ADD COLUMN auth_user_id text UNIQUE; ALTER TABLE patient ADD COLUMN api_key uuid UNIQUE DEFAULT gen_random_uuid();`
- `tests/mcp_server/test_auth.py` — 16 tests covering metadata shape, redirect_uri allowlist, single-use auth codes, 401 on invalid bearer, middleware passthrough

**Files modified:**
- `src/mcp_server/tools/_guard.py` — replaced `PATIENT_ID` module-level constant with `ContextVar[uuid.UUID]`; added `get_patient_id()` and `set_patient_id()`; removed env-var fallback (LookupError if middleware didn't set it)
- `src/persistence/models.py` — added `auth_user_id: str | None`, `api_key: uuid.UUID | None` to `PatientRow`; added `PatientAuthCreate` model
- `src/persistence/patient_repository.py` — added `get_by_api_key()` and `upsert_from_auth()`
- All 6 tool modules (upload, list_biomarkers, get_trend, query, prepare_summary, export) — `PATIENT_ID` → `get_patient_id()`
- `scripts/run_mcp_server.py` — added `load_dotenv()`, mounted all OAuth routes + `/register`
- `render.yaml` — removed `VITALOG_PATIENT_ID`; added `BASE_URL`, `RENDER_MAX_INSTANCES=1`
- `.gitignore` — added `docs/demo_queries.md`

**Key design decisions:**
- Pure ASGI `BearerMiddleware` (not `BaseHTTPMiddleware`) — avoids SSE response buffering
- RFC 7591 `/register` endpoint required by mcp-remote before OAuth flow starts
- Dual PKCE: mcp-remote↔server and server↔Supabase use independent verifier/challenge pairs
- PKCE re-validation skipped at `/token` — UUID4 `auth_code` is single-use and unguessable (documented inline as v1+ hardening item)
- `_RENDER_MAX_INSTANCES=1` in render.yaml documents that in-memory OAuth state (`_authorize_state`, `_auth_codes`) breaks in multi-instance deployments

**PR review findings addressed:**
1. Open redirect — validated `redirect_uri` against localhost allowlist in `authorize_handler`
2. Auth tests — added `tests/mcp_server/test_auth.py` with 16 tests
3. DB migration — `migrations/004_add_auth_columns.sql` tracks the schema change in git

**Testing:**
- Deployed to Render (`https://vitalog-9z6b.onrender.com`)
- Full OAuth flow verified: Claude Desktop → mcp-remote → `/register` → `/authorize` → Google login → `/auth/callback` → `/token` → Bearer on `/sse`
- Uploaded two lab reports via Google Drive URLs; biomarkers extracted and stored
- Trend queries, NLQ handler, and summary generator all working per `docs/demo_queries.md`
- Guardrails confirmed: out-of-scope queries (medications, diet, appointments) return safe refusal without calling LLM
