# Use our HUD base browser image with Playwright and uv pre-installed
FROM  hudevals/hud-browser-base

# Create app-specific working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY environment/ ./environment/
COPY server/ ./server/

RUN uv sync

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

ENV DISPLAY_WIDTH=1448
ENV DISPLAY_HEIGHT=944

ENV ENV_SERVER_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV_SERVER_URL=http://localhost:8000 \
    PYTHONPATH=/app
    PATH=/app/.venv/bin:$PATH

# Note: Environment variables for browser providers should be set at runtime:
# - BROWSER_PROVIDER: anchorbrowser, steel, browserbase, hyperbrowser, kernel
# - Provider-specific API keys: ANCHOR_API_KEY, STEEL_API_KEY, etc.
# - GCP_CREDENTIALS_JSON: For Google Sheets functionality (if needed)

CMD ["sh", "-c", "\
    if [ \"${HUD_DEV:-0}\" = \"1\" ]; then \
      uvicorn environment.server:app --host 0.0.0.0 --port $ENV_SERVER_PORT --reload --log-level warning >&2 & \
      sleep 5 && cd /app/server && exec hud dev server.main --stdio; \
    else \
      uvicorn environment.server:app --host 0.0.0.0 --port $ENV_SERVER_PORT --log-level warning >&2 & \
      sleep 5 && cd /app/server && exec python3 -m server.main; \
    fi\
"]
