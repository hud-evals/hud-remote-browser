# hud-remote-browser

A HUD **v6** environment for **cloud browser** tasks, including **SheetBench-50**. On startup it
launches a browser at a provider (Anchor, Steel, Browserbase, or Hyperbrowser — auto-detected from
API keys) and publishes its DevTools endpoint as a **`cdp`** capability any browser agent can
drive. The environment attaches to the same browser with its own Playwright client, so tasks seed
state before the prompt and grade from the live page after — never the agent's self-report.

## Layout

```
env.py            Environment: provider launch + cdp capability; the task templates
                  (answer, fill-record, wiki-speedrun, sheet-from-file) live here
sheets.py         Google Sheets: xlsx -> Drive upload, navigation, clipboard grid grading
sheetbench.json   the 50 SheetBench tasks (hud-evals/SheetBench-50), vendored
tasks.py          task instances collected into the public `tasks` list (9 general + 50 SheetBench)
providers/        cloud browser providers (Anchor, Steel, Browserbase, Hyperbrowser)
Dockerfile.hud    image: uv-managed Python + the v6 control channel
```

## Run

Needs a provider API key (see `.env.example`), and GCP service-account credentials for the
SheetBench tasks (the sheet is created via the Drive API and shared world-writable):

```bash
cp .env.example .env
hud eval tasks.py claude --task-ids wiki-python-year        # one general task
hud eval tasks.py claude --task-ids sheetbench-6e4744c7     # one SheetBench task
```

Deploy and run hosted:

```bash
hud deploy    # build from Dockerfile.hud, publish as `remote-browser`
hud eval tasks.py claude --runtime hud --full
```

## Tasks

| Slug | Grading |
|------|---------|
| `wiki-python-year`, `json-extract-title`, `wiki-multi-hop`, `numeric-extraction` | browse and answer — binary |
| `httpbin-order-form`, `httpbin-complex-form` | form filling — per-field partial credit |
| `wiki-easy-hop`, `wiki-medium-hop`, `wiki-hard-hop` | Wikipedia link navigation — efficiency-scored |
| `sheetbench-<id>` × 50 | spreadsheet task from an xlsx; expected cell values checked on the ANSWER tab — per-cell partial credit |

## Test

```bash
uv run pytest -q
```
