# Bablib MCP Server Connection Guide

## Quick Start

### Server URL
```
Read-Only Server: http://0.0.0.0:9383
Admin Server:     http://127.0.0.1:9384
```

### Start the Server
```bash
# Read-only server (safe, public access)
bablib serve

# Admin server (localhost only, full control)
bablib serve --admin

# Both servers concurrently
bablib serve &
bablib serve --admin &
```

---

## Important: MCP Protocol vs HTTP

### ⚠️ Critical Understanding

**MCP is NOT standard REST/HTTP!**

- ❌ Standard HTTP clients (curl, Postman, requests) **will fail**
- ❌ You'll get: `{"detail": "Invalid method"}`
- ✅ Only health endpoint supports standard HTTP: `GET /mcp/v1/health`
- ✅ All other endpoints require MCP protocol client

### Why Standard HTTP Fails

```bash
# This works (health check only)
curl http://0.0.0.0:9383/mcp/v1/health

# This fails (returns "Invalid method")
curl -X POST http://0.0.0.0:9383/mcp/v1/search -d '{"query":"test"}'
```

**Reason:** MCP protocol includes:
- Request/response framing
- Session management
- Capability negotiation
- Custom message format

---

## Connection Methods

### Method 1: Claude Desktop (Recommended)

**Best for:** Regular use, AI-assisted documentation access

**Setup:**
1. Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bablib": {
      "command": "bablib",
      "args": ["serve"],
      "env": {}
    }
  }
}
```

2. Restart Claude Desktop
3. Use natural language:
   - "Search my documentation for Docker security"
   - "List all my projects"
   - "Show me the README from project X"

**Files:**
- Configuration example: `mcp_config_examples.json`

---

### Method 2: Claude Code CLI

**Best for:** Command-line integration, automation

**Features:**
- Built-in MCP tools
- File access capabilities
- Command execution support

**Usage:**
```bash
# Claude Code automatically discovers MCP servers
# Use built-in tools to interact with Bablib
```

---

### Method 3: Python Client (Custom)

**Best for:** Custom integrations, programmatic access

**Requirements:**
```bash
pip install httpx asyncio
```

**Example:**
```python
from mcp_client_example import BablibMCPClient

# Health check (standard HTTP - works)
client = BablibMCPClient("http://0.0.0.0:9383")
health = await client.health_check()
print(health)

# MCP operations (requires full MCP protocol implementation)
# See: https://modelcontextprotocol.io
```

**Files:**
- Full example: `mcp_client_example.py`
- Run: `python3 mcp_client_example.py`

---

### Method 4: Manual Connection (Advanced)

**Best for:** Testing, debugging, understanding the protocol

**Steps:**

1. **Start Server:**
   ```bash
   bablib serve --foreground
   ```

2. **Health Check (HTTP works):**
   ```bash
   curl http://0.0.0.0:9383/mcp/v1/health
   ```

3. **MCP Operations:**
   - Implement MCP protocol from spec
   - Handle framing, sessions, capabilities
   - Or use existing MCP client library

**Spec:** https://modelcontextprotocol.io

---

## Available Operations

### Read-Only Server (Port 9383)

**Access:** Public (0.0.0.0)
**Security:** Safe, read-only operations

**Operations:**
- `list_projects` - List all documentation projects
- `search` - Semantic search across documents
- `get_file` - Read file contents (restricted by project type)
- `list_files` - List files in project
- `vector_search` - Search using embeddings

**Restrictions:**
- Crawling projects: Metadata only, no full file access
- Storage projects: Full file access

### Admin Server (Port 9384)

**Access:** Localhost only (127.0.0.1)
**Security:** Full control, localhost restriction

**Operations:**
- All read-only operations **plus:**
- `execute_command` - Run Bablib commands
- `create_project` - Create new projects
- `crawl` - Start crawling operations
- `batch_process` - Batch operations

**Blocked Operations (Security):**
- `uninstall` - System uninstall
- `reset` - System reset
- `delete_all_projects` - Mass deletion

---

## Testing Your Connection

### 1. Health Check (Standard HTTP)

```bash
# Read-only server
curl http://0.0.0.0:9383/mcp/v1/health

# Admin server
curl http://127.0.0.1:9384/mcp/v1/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "0.3.2",
  "server_type": "read-only"
}
```

### 2. MCP Protocol Test

**Using Claude Desktop:**
1. Configure MCP server (see Method 1)
2. Restart Claude Desktop
3. Ask: "List my Bablib projects"

**Using Python:**
```bash
python3 mcp_client_example.py
```

---

## Environment Variables

```bash
# Vector store selection
export BABLIB_VECTOR_STORE=sqlite_vec  # or qdrant

# Qdrant configuration (if using Qdrant)
export BABLIB_QDRANT_URL=http://localhost:6333

# Server configuration
export BABLIB_MCP_READ_ONLY_HOST=0.0.0.0
export BABLIB_MCP_READ_ONLY_PORT=9383
export BABLIB_MCP_ADMIN_HOST=127.0.0.1
export BABLIB_MCP_ADMIN_PORT=9384

# Start server with custom config
bablib serve
```

---

## Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -i :9383

# Use different port
bablib serve --port 9385
```

### "Invalid method" Error

**Cause:** Using standard HTTP for MCP endpoints

**Solution:** Use MCP-compliant client:
- Claude Desktop
- Claude Code
- Custom MCP implementation

**Remember:** Only `/mcp/v1/health` works with standard HTTP!

### Connection Refused

```bash
# Check if server is running
ps aux | grep bablib

# Check server logs
bablib serve --foreground
```

### Permission Denied (Admin Server)

**Cause:** Admin server only accepts localhost connections

**Solution:**
```bash
# Use localhost, not 0.0.0.0
curl http://127.0.0.1:9384/mcp/v1/health  # ✅ Works
curl http://0.0.0.0:9384/mcp/v1/health     # ❌ Fails
```

---

## Examples Files

### In This Directory

1. **`mcp_client_example.py`**
   - Python client implementation
   - Health check example
   - MCP protocol explanation
   - Run: `python3 mcp_client_example.py`

2. **`mcp_config_examples.json`**
   - Claude Desktop configurations
   - Various server setups
   - Environment variable examples
   - Testing instructions

3. **`MCP_CONNECTION_GUIDE.md`** (this file)
   - Complete connection guide
   - All methods explained
   - Troubleshooting tips

---

## Additional Resources

- **MCP Protocol Spec:** https://modelcontextprotocol.io
- **Bablib Documentation:** See CLAUDE.md in repository root
- **Claude Desktop:** https://claude.ai/download
- **Claude Code:** Official CLI from Anthropic

---

## Quick Reference

| Task | Command |
|------|---------|
| Start read-only server | `bablib serve` |
| Start admin server | `bablib serve --admin` |
| Health check | `curl http://0.0.0.0:9383/mcp/v1/health` |
| Test with Python | `python3 mcp_client_example.py` |
| Configure Claude Desktop | Edit `~/Library/Application Support/Claude/claude_desktop_config.json` |

---

**Last Updated:** 2025-10-01
**Bablib Version:** 0.3.2+
