FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Cache dependency layer — only re-runs when pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy source
COPY . .

# Install the project itself (editable-equivalent for the src/ package)
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "python", "scripts/run_mcp_server.py"]
