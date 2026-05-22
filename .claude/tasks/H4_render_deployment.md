# H4 — Render Deployment

**Status:** ⬜ pending  
**Branch:** `feat/h4-render-deployment`  
**Depends on:** G1, H3

---

## Context

The MCP server currently runs locally via stdio (Claude Desktop). To share Vitalog with other users and support remote access, the server needs to be deployed to a hosted platform. Render is the chosen platform. The SSE transport code already exists in `scripts/run_mcp_server.py` — this story is purely infrastructure: containerise, configure, and deploy.

Patient identity remains env-var based (Mark hardcoded) for this story. Auth and dynamic patient ID are H5.

---

## Goal

Deploy the Vitalog MCP server to Render so any Claude Desktop user can connect to it remotely via `mcp-remote`.

---

## Implementation Plan

### 1. `Dockerfile`

Python 3.11 slim image with uv. Steps:
- Install uv
- Copy `pyproject.toml`, `uv.lock` and sync dependencies (produces `.venv`)
- Copy source
- Expose port (Render provides `$PORT`)
- `CMD ["uv", "run", "python", "scripts/run_mcp_server.py"]`

Use multi-stage or layer caching so `uv sync` is not re-run on every code change.

### 2. `render.yaml`

Render Blueprint file:
```yaml
services:
  - type: web
    name: vitalog-mcp
    runtime: docker
    healthCheckPath: /health
    envVars:
      - key: MCP_TRANSPORT
        value: sse
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: AWS_ACCESS_KEY_ID
        sync: false
      - key: AWS_SECRET_ACCESS_KEY
        sync: false
      - key: AWS_REGION
        sync: false
      - key: VITALOG_PATIENT_ID
        sync: false
```

`sync: false` means the value is set in the Render dashboard (not committed to the repo).

### 3. `/health` endpoint

Render's health check hits `GET /health` and expects HTTP 200. FastMCP uses Starlette internally. In `scripts/run_mcp_server.py`, before calling `mcp.run()` in SSE mode, mount a health route on the FastMCP ASGI app.

FastMCP exposes the underlying app via `mcp.sse_app()`. Wrap it with a Starlette `Router` or use `mcp.custom_route()` if available, otherwise add a lightweight Starlette `Route` at `/health` returning `PlainTextResponse("ok")`.

Research the exact FastMCP API during implementation — `mcp.sse_app()` vs `mcp.starlette_app()` — and use whichever is available in the installed version.

### 4. Render dashboard setup (manual steps, documented here)

1. Create a new Render Web Service, connect GitHub repo
2. Select "Docker" runtime
3. Set all env vars marked `sync: false` in the Render dashboard:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
   - `ANTHROPIC_API_KEY`
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
   - `VITALOG_PATIENT_ID` (Mark's UUID)
4. Choose plan: **Starter ($7/month)** — free tier sleeps after 15 min, which breaks persistent SSE connections

### 5. Claude Desktop config (remote)

After deploy:
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

---

## Files to create/modify

| File | Change |
|------|--------|
| `Dockerfile` | New — Python 3.11 + uv container |
| `render.yaml` | New — Render Blueprint config |
| `scripts/run_mcp_server.py` | Add `/health` route in SSE mode |

---

## Verification

1. `docker build -t vitalog .` — succeeds locally
2. `docker run -e MCP_TRANSPORT=sse -e PORT=8000 -e SUPABASE_URL=... -p 8000:8000 vitalog` — server starts, `/health` returns 200
3. Deploy to Render — health check passes, service stays green
4. Update Claude Desktop config with the Render URL, restart Claude Desktop — Vitalog tools appear
5. Run `list_biomarkers` tool — returns Mark's data from remote server

---

## Render tier note

Free tier: sleeps after 15 min inactivity → cold starts break SSE connections.  
Starter ($7/month): always-on → required for a reliable MCP server.

---

### Implementation (2026-05-22)

**Files created/modified:**
- `Dockerfile` — Python 3.11-slim + uv; two-stage `uv sync` for layer caching (deps layer cached separately from source); exposes port 8000; CMD runs `scripts/run_mcp_server.py`
- `render.yaml` — Render Blueprint; `runtime: docker`; `healthCheckPath: /health`; all secrets marked `sync: false` (set in Render dashboard)
- `pyproject.toml` — added `uvicorn>=0.29.0` as direct dependency (was transitive via mcp)
- `scripts/run_mcp_server.py` — in SSE mode: calls `mcp.sse_app()` (returns a Starlette app), mounts `/health` route via `app.add_route()`, runs via `uvicorn.run()` instead of `mcp.run()`; stdio mode unchanged

**Key design decisions:**
- `mcp.sse_app()` returns a plain `starlette.applications.Starlette` object — can call `add_route()` directly without wrapping in a new app
- `/health` is a simple `PlainTextResponse("ok")` — no dependency checks; Render just needs HTTP 200
- `uvicorn` added as explicit dep since we call `uvicorn.run()` directly (was previously only a transitive dep from the `mcp` package)
- Docker layer order: copy lock files → `uv sync --frozen --no-install-project` → copy source → `uv sync --frozen` — ensures the expensive dependency install layer is cached on code-only changes
