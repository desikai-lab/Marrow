# Marrow — Administration Manual

This document covers how to expose the Marrow MCP server to the internet and connect it to external clients such as Claude.ai, Cursor, or any MCP-compatible host.

---

## 1. Environment Configuration (`.env`)

Create a `.env` file in the `marrow_server/` root with the following content:

```env
SECRET_TOKEN=your_very_secret_token_at_least_16_chars
TASKS_DIR=C:/Path/To/Your/Marrow/Data
DECOUPLED_STORAGE_ENABLED=true

# Embedding models (pre-download required — HF_HUB_OFFLINE=1 is recommended)
EMBEDDING_MODEL_CODE=BAAI/bge-small-en-v1.5
EMBEDDING_MODEL_TEXT=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSIONS=384
MAX_EMBED_CHARS=2000
VECT_DEBOUNCE_SECONDS=0.5

MAINTENANCE_INTERVAL_SECONDS=1800
MCP_DEBUG_TRANSPORT=false
```

**Where to get a token?** Generate any random string of at least 16 characters. This acts as the password for all requests to your Marrow server.

---

## 2. Running the Server

```powershell
# From marrow_server/
$env:PYTHONPATH = "src"
python src/marrow_server.py
```

The server starts on `http://localhost:8000` by default.

---

## 3. Exposing the Server via HTTPS

Claude.ai and most external MCP clients require an **HTTPS URL**. The easiest approach is a tunnel.

### Option A: ngrok (Quick Start)

1. Download [ngrok](https://ngrok.com/download).
2. Start the tunnel:
   ```bash
   ngrok http 8000 --host-header="localhost:8000"
   ```
   > 💡 `--host-header` prevents the `Invalid Host header` error when running behind a proxy.
3. Copy the **Forwarding URL** (e.g. `https://abc-123.ngrok-free.app`).

### Option B: Cloudflare Tunnel (Persistent)

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/).
2. Authenticate: `cloudflared tunnel login`
3. Create tunnel: `cloudflared tunnel create marrow`
4. Configure DNS in your Cloudflare dashboard.
5. Run: `cloudflared tunnel run --url http://localhost:8000 marrow`

---

## 4. Connecting to Claude.ai

1. Open **Claude.ai**.
2. Go to **Settings** → **Connectors**.
3. Click **Add custom connector**.
4. Fill in:
   - **Name**: `Marrow`
   - **URL**: Your HTTPS URL with token: `https://abc-123.ngrok-free.app/sse?token=YOUR_SECRET_TOKEN`
   - **Authentication**: Leave as "None" (token is in the URL).
5. Click **Add**, then **Connect**.

---

## 5. Connecting via `mcp_config.json` (Local stdio mode)

For local clients (Cursor, Claude Desktop, Antigravity):

```json
{
  "mcpServers": {
    "marrow": {
      "command": "python",
      "args": ["D:/MCPs/marrow_server/src/mcp_local.py"],
      "env": {
        "PYTHONPATH": "D:/MCPs/marrow_server/src"
      }
    }
  }
}
```

---

## 6. Running the Marrow Worker (Code Skeleton Index)

The worker scans your source code and keeps the skeleton index synchronized in `marrow_server`.

```powershell
# From marrow_worker/
python main.py `
  --repo-dir "C:/Path/To/Your/Code" `
  --project-name "YourProject" `
  --target-url "http://localhost:8000" `
  --secret-token "your_secure_token" `
  --init        # Run a full initial scan on first launch
```

The worker uses a SQLite-backed outbox to ensure no updates are lost during network interruptions.

---

## 7. Health Check & Verification

| Endpoint | Description |
|---|---|
| `GET /health` | Returns `{"status": "ok"}` — no authentication required. |
| `GET /userinfo` | Returns server metadata and version info. |

If Claude reports the connector as unavailable, verify: `https://your-domain.com/health`

---

## 8. Running Tests

```powershell
# Unit tests
$env:PYTHONPATH = "src"
python -m pytest tests/unit/ -v

# Integration tests (requires running server)
$env:PYTHONPATH = "src"
python -m pytest tests/integration/ -v

# Full suite
$env:PYTHONPATH = "src"
python -m pytest tests/ -v
```

---

## 9. Maintenance & Operations

- **Logs**: `marrow_server/src/logs/server.log` (rotating, 10 MB max per file).
- **Worker Logs**: `marrow_worker/logs/worker.log`.
- **Maintenance**: Background compaction and cleanup runs every `MAINTENANCE_INTERVAL_SECONDS` (default: 30 min).
- **Code Quality**: Project uses `ruff`. Install hooks with `pre-commit install`.
- **Admin CLI**: `python src/cli/admin_cli.py --help` for manual maintenance operations.
