# H3 — Multi-source upload: URL + local file_path + base64

**Status:** ✅ done  
**Branch:** `feat/h3-upload-multi-source`  
**Depends on:** G1, G3

---

## Context

The upload tool only works for local file paths (a demo workaround). For a hosted MCP
server, users need to share lab reports from wherever they store them — Google Drive,
Dropbox, S3, or local disk (Claude Desktop users).

The MCP protocol cannot transfer large binary files through LLM tool call arguments
(token limit), so base64-encoding a whole PDF via the LLM is not viable for large files.
The correct approach is to pass a reference (path or URL) and have the server fetch the
file directly.

### Why not base64 through the LLM?

When a user attaches a PDF in Claude.ai web (or ChatGPT), the LLM generates the tool call
as JSON text. A 2 MB PDF = ~2.7 MB of base64 text ≈ far more than the max output token
limit. The encoding gets truncated and corrupted. This is a protocol limitation, not a
Vitalog code bug.

### Why not a separate HTTP upload endpoint?

Users would have to leave the chat to upload the file and then come back — defeating the
purpose of an MCP app where everything happens in the chat interface.

### Why URL-based is the right answer now

The user pastes a Google Drive / Dropbox / S3 / any link in the chat. The server fetches
it directly — no size limits, works from any LLM client, no separate page. A future
story (H4) can add OAuth-based cloud folder integration (Option 3 from MCP research) for
a more seamless "drop file in folder" UX.

---

## Goal

Support three upload sources in priority order:
1. `url` — any HTTP/HTTPS link: S3, GCS, Dropbox, Google Drive, pre-signed URLs, etc.
2. `file_path` — absolute path on the server's local disk (for Claude Desktop local use)
3. `file_content_base64` — raw base64 bytes (for small images only)

Remove the `~/Downloads` auto-pick fallback and `filename` parameter entirely.

---

## Implementation Plan

### 1. `pyproject.toml`

Add `httpx` for URL fetching (not currently in dependencies):
```toml
"httpx>=0.27.0",
```
Run `uv sync` after adding.

### 2. `src/mcp_server/tools/upload.py`

Add generic URL fetch with best-effort normalization. Most URLs pass through unchanged.
Google Drive and Dropbox need rewriting because their share-page URLs return HTML, not
the file.

```python
def _fetch_url(url: str) -> bytes:
    """Download file bytes from any URL. Follows redirects."""
    import httpx
    normalized = _normalize_share_url(url)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(normalized)
        resp.raise_for_status()
        return resp.content


def _normalize_share_url(url: str) -> str:
    """Convert share-page URLs to direct-download URLs for known providers.

    Most URLs pass through unchanged. Only Google Drive and Dropbox share
    links need rewriting — their default share URLs serve HTML, not the file.
    """
    import re
    # Google Drive /file/d/{ID}/view or /open?id={ID} → uc?export=download
    m = re.match(r"https://drive\.google\.com/file/d/([^/?]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r"drive\.google\.com/open\?id=([^&]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    # Dropbox: dl=0 (view page) → dl=1 (direct download)
    if "dropbox.com" in url:
        url = re.sub(r"\bdl=0\b", "dl=1", url)
        if "dl=" not in url:
            url += ("&" if "?" in url else "?") + "dl=1"
    return url
```

Updated `run()` — remove `filename` param and Downloads logic:
```python
def run(
    file_content_base64: str | None,
    container: ServiceContainer,
    *,
    file_path: str | None = None,
    url: str | None = None,
) -> str:
    if url is not None:
        try:
            file_bytes = _fetch_url(url)
        except Exception as exc:
            return f"Error fetching file from URL: {exc}"
    elif file_path is not None:
        try:
            file_bytes = Path(file_path).read_bytes()
        except OSError as exc:
            return f"Error: could not read file at {file_path!r}: {exc}"
    elif file_content_base64 is not None:
        # ... existing base64 decode logic (unchanged)
    else:
        return (
            "No file provided. Share a Google Drive or Dropbox link, "
            "provide an absolute file path, or attach a small image."
        )
```

Remove: `Path.home()`, Downloads glob, `filename` param, `filename or detected.name`.

### 3. `src/mcp_server/server.py`

```python
@mcp.tool(
    description=(
        "Upload a lab report to Vitalog. "
        "Preferred: pass any cloud storage link (Google Drive, Dropbox, S3, etc.) as url. "
        "For local use: pass file_path (absolute path on this machine). "
        "For small images only: pass file_content_base64 (base64-encoded bytes). "
        "Returns a summary of extracted biomarker records."
    )
)
def upload_document(
    url: str | None = None,
    file_path: str | None = None,
    file_content_base64: str | None = None,
) -> str:
    return _upload.run(file_content_base64, _get_container(), file_path=file_path, url=url)
```

### 4. `tests/mcp_server/test_tools_smoke.py`

- **Remove** `test_upload_tool_no_input` (tested Downloads fallback — deleted).
- **Add** `test_upload_tool_no_source` — all None → error message with "attach" hint.
- **Add** `test_upload_tool_url_fetch` — patches `_fetch_url`, verifies bytes forwarded.
- **Add** `test_upload_tool_base64_content` — base64 round-trip to workflow.
- **Add** `test_normalize_share_url_gdrive` — `/file/d/{ID}/view` → `uc?export=download`.
- **Add** `test_normalize_share_url_dropbox` — `dl=0` → `dl=1`.
- **Add** `test_normalize_share_url_passthrough` — S3/direct URL unchanged.

---

## Files to modify

| File | Change |
|------|--------|
| `pyproject.toml` | Add `httpx>=0.27.0` |
| `src/mcp_server/tools/upload.py` | Add `_fetch_url` + `_normalize_share_url`; remove Downloads; update `run()` |
| `src/mcp_server/server.py` | Add `url` param; remove `filename`; update description |
| `tests/mcp_server/test_tools_smoke.py` | Remove Downloads test; add URL + base64 + no-source tests |

## Verification

1. `uv sync` — picks up httpx
2. `make test` — all tests pass
3. `make lint` — ruff clean
4. `make typecheck` — mypy --strict passes
5. Manual: share a Google Drive PDF link in chat → Claude calls `upload_document(url=...)` → processes correctly

---

### Implementation (2026-05-22)

**Files modified:**
- `pyproject.toml` — added `httpx>=0.27.0`
- `uv.lock` — updated after `uv sync`
- `src/mcp_server/tools/upload.py` — added `_fetch_url` + `_normalize_share_url`; SSRF guard (HTTPS-only); 50 MB streaming OOM cap; removed `~/Downloads` fallback and `filename` param; moved `httpx` import to module level
- `src/mcp_server/server.py` — added `url` + `file_path` params to `upload_document` tool; updated description with explicit routing instructions and trigger phrases for local paths
- `tests/mcp_server/test_tools_smoke.py` — added URL fetch, file_path, base64, no-source, and URL normalization tests; removed Downloads test; fixed `tmp_path` type annotation

**Key design decisions:**
- URL-based is the primary path: user pastes a share link in chat, server fetches directly — no size limits, works from any LLM client
- Google Drive and Dropbox share URLs rewritten to direct-download equivalents; all other URLs pass through unchanged
- SSRF guard: HTTPS-only check applied before normalization so `http://169.254.169.254/` is rejected
- OOM guard: streaming with 50 MB cap matches Textract file-size limit

**PR review fixes (PR #37):**
- SSRF: added `url.lower().startswith("https://")` check in `_fetch_url`
- OOM: replaced `resp.content` buffer with chunked streaming and 50 MB cap
- Style: moved `import httpx` from inside `_fetch_url` to module-level imports
- Test: fixed `tmp_path` annotation from `pytest.TempPathFactory` → `pathlib.Path`

**Post-merge fix:**
- Updated `upload_document` tool description to add explicit routing instructions so Claude Desktop's model uses `file_path` for local path strings instead of refusing them

---

## Future work (H4)

OAuth-based cloud folder integration — user configures Google Drive / Dropbox once with
API credentials, drops files into a watched folder, references by filename only. Better
UX than pasting URLs; out of scope for this story.
