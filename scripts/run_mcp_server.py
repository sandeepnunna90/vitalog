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

Claude Desktop / claude.ai config (remote):
    {
      "mcpServers": {
        "vitalog": { "url": "https://vitalog.yourdomain.com/sse" }
      }
    }

Required env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY
Optional env vars: MCP_TRANSPORT (stdio|sse), PORT (default 8000), AWS_REGION
"""

from __future__ import annotations

import os

from src.mcp_server.server import mcp

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        port = int(os.environ.get("PORT", "8000"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)  # noqa: S104
    else:
        mcp.run()
