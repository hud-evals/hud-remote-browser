# Remote Browser Environment

A cloud browser environment for web agent evaluation. Agents interact with real websites through Playwright and computer-use tools, powered by a cloud browser provider (AnchorBrowser, Steel, BrowserBase, or HyperBrowser).

## Setup

```bash
uv sync
cp .env.example .env                # Optional
hud set HUD_API_KEY=your-key-here   # CLI auth, get one at hud.ai/project/api-keys
```

## Deploy & Run

```bash
hud deploy .                                          # deploy the environment (once)
hud sync tasks <taskset-name>                         # push tasks to a taskset (fast, re-run on every task change)
hud eval <taskset-name> --remote --full
```

**Iteration loop:** `hud deploy` is the slow step — run it once. After that, edit `tasks.py` and re-run `hud sync tasks` (takes seconds). Only redeploy when `env.py` or the Dockerfile changes.

See [Deploy & Go Remote](https://docs.hud.ai/building/running-at-scale) for deploy flags, secrets, and auto-deploy options.

## Scenarios

| Scenario | Key Args | Description |
|----------|----------|-------------|
| `answer` | `url`, `question`, `expected`, `compare` | Navigate to a URL and extract an answer |
| `fill-record` | `url`, `record`, `selectors` | Fill out a form and verify field values |
| `wiki-speedrun` | `start_page`, `target_page`, `max_clicks` | Navigate Wikipedia from start to target using only links |
| `sheet-from-file` | `file_url`, `expected_cells` | Create a Google Sheet from an Excel file |

## Configuration

A cloud browser provider API key is required as an environment variable. Set at least one of:

- `ANCHOR_API_KEY`
- `STEEL_API_KEY`
- `BROWSERBASE_API_KEY` (also requires `BROWSERBASE_PROJECT_ID`)
- `HYPERBROWSER_API_KEY`

The `sheet-from-file` scenario additionally requires GCP credentials via one of:

```bash
# Option 1: JSON string
GCP_CREDENTIALS_JSON='{"type":"service_account",...}'

# Option 2: Base64 encoded
GCP_CREDENTIALS_BASE64='eyJ0eXBlIjoic2VydmljZV9hY2NvdW50...'

# Option 3: File path
GCP_CREDENTIALS_FILE='/path/to/service-account.json'
```

## Documentation

To learn more about tasks, evaluations, and running at scale see the [full docs](https://docs.hud.ai).
