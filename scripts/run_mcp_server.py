"""Entry point for the Vitalog MCP server.

SSE mode (local dev):
    MCP_TRANSPORT=sse PORT=8000 uv run python scripts/run_mcp_server.py

SSE mode (Render — set via render.yaml):
    MCP_TRANSPORT=sse (PORT provided by Render)

Claude Desktop config (remote or local SSE):
    {
      "mcpServers": {
        "vitalog": {
          "command": "npx",
          "args": ["mcp-remote", "https://vitalog-9z6b.onrender.com/sse"]
        }
      }
    }

    For local dev, replace the URL with http://localhost:8000/sse.
    First connection opens a browser for Google login (MCP OAuth 2.0).
    Subsequent connections are silent — token cached by mcp-remote.

Required env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY
Optional env vars: MCP_TRANSPORT (sse, default sse), PORT (default 8000),
                   BASE_URL (default http://localhost:8000), AWS_REGION
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

_log = logging.getLogger(__name__)

# PyMuPDF prints MuPDF error messages to C-level stdout, which corrupts the
# stdio JSON-RPC channel used by Claude Desktop. Suppress before any imports
# that may trigger fitz.
import fitz  # noqa: E402

fitz.TOOLS.mupdf_display_errors(False)

from starlette.requests import Request  # noqa: E402
from starlette.responses import PlainTextResponse, Response  # noqa: E402

from src.mcp_server.auth import (  # noqa: E402
    BearerMiddleware,
    auth_callback_handler,
    authorize_handler,
    oauth_metadata_handler,
    registration_handler,
    token_handler,
)
from src.mcp_server.server import mcp  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))

    app = mcp.sse_app()

    async def health(_: Request) -> Response:
        return PlainTextResponse("ok")

    app.add_route("/health", health)
    app.add_route("/.well-known/oauth-authorization-server", oauth_metadata_handler)
    app.add_route("/register", registration_handler, methods=["POST"])
    app.add_route("/authorize", authorize_handler)
    app.add_route("/auth/callback", auth_callback_handler)
    app.add_route("/token", token_handler, methods=["POST"])

    wrapped = BearerMiddleware(app)

    import uvicorn  # noqa: PLC0415

    uvicorn.run(wrapped, host="0.0.0.0", port=port)  # noqa: S104
