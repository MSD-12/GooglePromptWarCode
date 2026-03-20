# Poison Guard MCP — Client Configuration Guide

## ⚠️ Important: This is an SSE (HTTP) server, NOT a stdio/npx server
Do NOT configure it with `npx` or `command`. Use `url` instead.

---

## Local Development (before Cloud Run deploy)
Server runs at: `http://localhost:8080/sse`

## Production (after Cloud Run deploy)
Server runs at: `https://<YOUR-CLOUD-RUN-URL>/sse`

---

## Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "poison-guard": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

---

## Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "poison-guard": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

---

## Windsurf (`~/.codeium/windsurf/mcp_config.json`)

```json
{
  "mcpServers": {
    "poison-guard": {
      "serverUrl": "http://localhost:8080/sse"
    }
  }
}
```

---

## After Cloud Run Deploy
Replace `http://localhost:8080` with your Cloud Run service URL in any of the configs above.

## Health Check
```
curl http://localhost:8080/health
```
