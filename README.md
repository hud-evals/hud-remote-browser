# Remote Browser Environment

A cloud browser environment for web agent evaluation. Agents interact with real websites through Playwright and computer-use tools, powered by a cloud browser provider (AnchorBrowser, Steel, BrowserBase, HyperBrowser, or Kernel).

## Quick Start

```bash
uv sync                                              # install dependencies
hud deploy . --build-arg YOUR_API_KEY=$YOUR_API_KEY  # build and deploy to HUD platform
hud sync tasks <name>                                # upload task definitions
```

## Scenarios

| Scenario | Key Args | Description |
|----------|----------|-------------|
| `answer` | `url`, `question`, `expected`, `compare` | Navigate to a URL and extract an answer |
| `fill-record` | `url`, `record`, `selectors` | Fill out a form and verify field values |
| `wiki-speedrun` | `start_page`, `target_page`, `max_clicks` | Navigate Wikipedia from start to target using only links |
| `sheet-from-file` | `file_url`, `expected_cells` | Create a Google Sheet from an Excel file |

## Configuration

A cloud browser provider API key is required as a build argument. Set at least one of:

- `ANCHOR_API_KEY`
- `STEEL_API_KEY`
- `BROWSERBASE_API_KEY` (also requires `BROWSERBASE_PROJECT_ID`)
- `HYPERBROWSER_API_KEY`
- `KERNEL_API_KEY`

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
