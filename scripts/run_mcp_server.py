"""Entry point for the Vitalog MCP server.

Local (Claude Desktop stdio):
    uv run python scripts/run_mcp_server.py

Remote (deployed SSE):
    MCP_TRANSPORT=sse PORT=8000 uv run python scripts/run_mcp_server.py

Claude Desktop config (local):
    {
      "mcpServers": {
        "vitalog": {
          "command": "uv",
          "args": ["run", "python", "scripts/run_mcp_server.py"],
          "cwd": "/absolute/path/to/vitalog"
        }
      }
    }

Claude Desktop config (remote, via mcp-remote):
    {
      "mcpServers": {
        "vitalog": {
          "command": "npx",
          "args": ["mcp-remote", "https://vitalog.onrender.com/sse"]
        }
      }
    }

Required env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY
Optional env vars: MCP_TRANSPORT (stdio|sse), PORT (default 8000), AWS_REGION

SECURITY NOTE (SSE mode):
    The SSE endpoint has no built-in authentication — any caller who knows the URL
    can invoke all tools. H5 adds API-key auth; until then keep the URL private.
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)

# PyMuPDF prints MuPDF error messages to C-level stdout, which corrupts the
# stdio JSON-RPC channel used by Claude Desktop. Suppress before any imports
# that may trigger fitz.
import fitz  # noqa: E402

fitz.TOOLS.mupdf_display_errors(False)

from starlette.requests import Request  # noqa: E402
from starlette.responses import PlainTextResponse  # noqa: E402

from src.mcp_server.server import mcp  # noqa: E402

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        _log.warning(
            "SSE mode: no built-in authentication. "
            "Keep the SSE URL private until H5 API-key auth is deployed."
        )
        port = int(os.environ.get("PORT", "8000"))

        app = mcp.sse_app()

        async def health(_: Request) -> PlainTextResponse:
            return PlainTextResponse("ok")

        app.add_route("/health", health)  # type: ignore[arg-type]

        import uvicorn  # noqa: PLC0415

        uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
    else:
        mcp.run()
