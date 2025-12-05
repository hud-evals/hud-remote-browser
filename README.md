# HUD Remote Browser

This MCP server provides browser automation capabilities using various remote browser providers.

## Quick Start

```bash
# Build the Docker image
# Add provider-specific environment variables here
hud build . -e BROWSER_PROVIDER=

# Start hot-reload development server
# Make sure that you have a .env file with the required environment variables
hud dev

# Run the sample tasks
hud eval test_task.json
```

## Deploy

When you're ready to use this environment in production:

1. Push your code to GitHub
2. Connect your repo at [hud.ai](https://hud.ai/environments/new)
3. Builds will trigger automatically on each push

## Browser Providers

| Provider | Required Variables |
|----------|-------------------|
| anchorbrowser | `ANCHOR_API_KEY` |
| browserbase | `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` |
| hyperbrowser | `HYPERBROWSER_API_KEY` |
| steel | `STEEL_API_KEY` |
| kernel | None |

### Optional Browser Settings

| Variable | Description |
|----------|-------------|
| `HEADLESS` | Whether to run browser in headless mode |
| `DEFAULT_TIMEOUT` | Default timeout for browser operations |
| `WINDOW_WIDTH` | Browser window width |
| `WINDOW_HEIGHT` | Browser window height |
| `PROXY_URL` | HTTP proxy URL |

### Proxy Configuration

The remote browser environment supports multiple proxy providers:

| Variable | Description | Default |
|----------|-------------|---------|
| `PROXY_PROVIDER` | Proxy provider type (auto, decodo, standard, residential, none) | auto |

#### Options:

- **`auto`** (default): Let the browser use its default proxy
- **`decodo`**: Use Decodo proxy service
  - Requires: `DECODO_USERNAME`, `DECODO_PASSWORD`
  - Optional: `DECODO_ROTATING` (false=port 10000, true=test ports 10001-11000)
- **`standard`**: Use any HTTP/SOCKS proxy
  - Requires: `PROXY_SERVER`
  - Optional: `PROXY_USERNAME`, `PROXY_PASSWORD`
- **`none`**: Force direct connection (no proxy)

Example:
```bash
# Use Decodo proxy
export PROXY_PROVIDER=decodo
export DECODO_USERNAME=username
export DECODO_PASSWORD=password
```

### Google Cloud Platform (GCP) Credentials

For Google Sheets functionality, you have multiple options to provide GCP credentials:

#### Option 1: JSON String (now more lenient)
```bash
# Supports standard JSON, single-quoted, or Python dict format
-e GCP_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","private_key":"..."}'
```

#### Option 2: Base64 Encoded (recommended for complex credentials)
```bash
# First encode your credentials file
base64 < service-account.json
# Then set the environment variable
-e GCP_CREDENTIALS_BASE64='eyJ0eXBlIjoic2VydmljZV9hY2NvdW50IiwicHJvamVjdF9pZCI6Li4ufQ=='
```

#### Option 3: File Path
```bash
# Mount the credentials file and reference it
-v /path/to/service-account.json:/app/creds.json \
-e GCP_CREDENTIALS_FILE='/app/creds.json'
```

#### Option 4: Individual Environment Variables
```bash
-e GCP_TYPE='service_account' \
-e GCP_PROJECT_ID='your-project-id' \
-e GCP_PRIVATE_KEY_ID='your-key-id' \
-e GCP_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----' \
-e GCP_CLIENT_EMAIL='your-service-account@project.iam.gserviceaccount.com' \
-e GCP_CLIENT_ID='1234567890' \
-e GCP_AUTH_URI='https://accounts.google.com/o/oauth2/auth' \
-e GCP_TOKEN_URI='https://oauth2.googleapis.com/token' \
-e GCP_AUTH_PROVIDER_X509_CERT_URL='https://www.googleapis.com/oauth2/v1/certs' \
-e GCP_CLIENT_X509_CERT_URL='https://www.googleapis.com/robot/v1/metadata/x509/...'
```

## Learn More

For complete documentation on building environments and running evaluations, visit [docs.hud.ai](https://docs.hud.ai).
