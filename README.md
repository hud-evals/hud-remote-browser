# Remote Browser Environment

A HUD environment for browser automation using cloud browser providers.

## 1. Deploy to Platform

If you haven't already, connect this repo to hud.ai:

1. Push to GitHub
2. Go to [hud.ai](https://hud.ai) → **New** → **Environment**
3. Connect your GitHub repo
4. Set required environment variables (see Configuration below)
5. Your environment builds automatically on each push

Once deployed, your environment is accessible by its slug (e.g., `my-org/remote-browser`).

## 2. Define Tools and Scenarios

Tools are functions agents can call. Scenarios define the evaluation lifecycle.

### Available Tools

- **PlaywrightTool** - High-level browser actions (navigate, click, type)
- **HudComputerTool** - Screenshot and coordinate-based interactions
- **AnthropicComputerTool**, **OpenAIComputerTool**, **GeminiComputerTool** - Provider-specific computer tools

### Available Scenarios

| Scenario | Description |
|----------|-------------|
| `complete-sheet-task` | Complete a task in Google Sheets, verify cell values |
| `sheet-from-file` | Create sheet from Excel file and complete a task |
| `navigate-to-goal` | Navigate from start URL to reach a target |
| `form-submit` | Fill and submit a form |
| `find-information` | Find specific content on a website |

## 3. Create Tasks from Scenarios

Tasks are scenario instances with specific arguments.

**In Code:**
```python
tasks = [
    env("complete-sheet-task",
        prompt="Sum cells A1:A5 and put result in A6",
        sheet_url="https://docs.google.com/spreadsheets/d/.../edit",
        expected_cells={"A6": "15"}
    ),
    env("navigate-to-goal",
        start_url="https://wikipedia.org",
        prompt="Navigate to the English Wikipedia main page",
        target_url="en.wikipedia.org"
    ),
]
```

**From JSON:**
```json
[
  {
    "env": {"name": "my-org/remote-browser"},
    "scenario": "complete-sheet-task",
    "args": {
      "prompt": "Sum cells A1:A5 and put result in A6",
      "sheet_url": "https://docs.google.com/spreadsheets/d/.../edit",
      "expected_cells": {"A6": "15"}
    }
  }
]
```

**On Platform:**
After deploying, create tasks from your scenarios on hud.ai. Access them by slug:
```python
from hud.datasets import load_tasks
tasks = load_tasks("my-org/sheets-tasks")
```

## 4. Run Evaluations

Run tasks and see results on hud.ai. You have three options:

**On Platform:**
Run evaluations at scale directly on [hud.ai](https://hud.ai) with parallel execution and automatic tracing.

**CLI:**
```bash
hud eval ./remote_tasks.json --model gpt-4o --remote  # https://hud.ai/models
hud eval my-org/sheets-tasks --model gpt-4o --remote --group 5
```

**Python:**
```python
import hud
from hud.agents import OpenAIChatAgent  # See all models: https://hud.ai/models

async with hud.eval(tasks) as ctx:
    agent = OpenAIChatAgent.create(model="gpt-4o")  # Uses inference.hud.ai
    await agent.run(ctx)

# Results are automatically traced to hud.ai
```

**With Variants (A/B Testing):**

```python
tasks = [
    env("complete-sheet-task", prompt="Sum A1:A5", sheet_url="...", expected_cells={"A6": "15"}),
    env("navigate-to-goal", start_url="https://wikipedia.org", prompt="Go to main page", target_url="en.wikipedia.org"),
]
variants = {"model": ["gpt-4o-mini", "gpt-4o"]}

async with hud.eval(tasks, variants=variants, group=2) as ctx:
    agent = OpenAIChatAgent.create(model=ctx.variants["model"])
    await agent.run(ctx)
```

## Configuration

### Required Variables

| Variable | Description |
|----------|-------------|
| `BROWSER_PROVIDER` | Provider to use: `anchorbrowser`, `browserbase`, `hyperbrowser`, `steel` |

### Provider API Keys

| Provider | Required Variables |
|----------|-------------------|
| anchorbrowser | `ANCHOR_API_KEY` |
| browserbase | `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` |
| hyperbrowser | `HYPERBROWSER_API_KEY` |
| steel | `STEEL_API_KEY` |

### Google Sheets (Optional)

For Sheet scenarios, provide GCP credentials via one of:

```bash
# Option 1: JSON string
GCP_CREDENTIALS_JSON='{"type":"service_account",...}'

# Option 2: Base64 encoded
GCP_CREDENTIALS_BASE64='eyJ0eXBlIjoic2VydmljZV9hY2NvdW50...'

# Option 3: File path
GCP_CREDENTIALS_FILE='/path/to/service-account.json'
```

## Local Development

Use `hud dev` with hot-reload for fast iteration:

```bash
# 1. Build the Docker image (first time only)
hud build

# 2. Start with hot-reload on scenarios/evaluate
hud dev -w scenarios -w evaluate -w setup --port 8765

# 3. Test locally
python local_test.py
```

### Hot-Reload

| Component | Reloaded? |
|-----------|-----------|
| `scenarios/*.py` | ✅ Yes |
| `evaluate/*.py` | ✅ Yes (if watched) |
| `setup/*.py` | ✅ Yes (if watched) |
| `tools/*.py` | ✅ Yes (if watched) |
| Browser provider connection | ❌ No (persist) |

**When to rebuild:** Dockerfile changes, provider changes.

### Without Docker

```bash
# Set environment variables
export BROWSER_PROVIDER=anchorbrowser
export ANCHOR_API_KEY=your-key

# Run context server (maintains browser session)
python context.py &

# Test locally
python local_test.py

# Test with remote tasks
python remote_test.py
```

## Structure

```
hud-remote-browser/
├── env.py              # Environment definition
├── context.py          # Persistent browser context
├── tools/              # Browser and computer tools
├── scenarios/          # Scenario definitions
│   ├── sheets.py       # Google Sheets scenarios
│   └── general.py      # Navigation/form scenarios
├── setup/              # Setup helpers (navigate, cookies, etc.)
├── evaluate/           # Evaluation helpers (url_match, page_contains, etc.)
├── providers/          # Cloud browser providers
├── local_test.py       # Local testing examples
├── remote_test.py      # Platform integration examples
├── remote_tasks.json   # Task definitions
├── Dockerfile.hud
└── pyproject.toml
```

## Documentation

Full documentation: [docs.hud.ai](https://docs.hud.ai)
