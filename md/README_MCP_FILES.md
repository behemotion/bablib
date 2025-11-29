# MCP Connection Files - Quick Start

This directory contains everything you need to connect to the Bablib MCP server.

## 📁 Files in This Directory

### 1. **MCP_CONNECTION_GUIDE.md** 📖
Complete connection guide with all methods explained.

**Contents:**
- Quick start instructions
- All connection methods (Claude Desktop, Claude Code, Python, Manual)
- Available operations for each server
- Troubleshooting guide
- Environment variables

**Start here if:** You want comprehensive documentation.

---

### 2. **mcp_client_example.py** 🐍
Python client implementation with working examples.

**Usage:**
```bash
# Install dependencies
pip install httpx asyncio

# Run the example
python3 mcp_client_example.py
```

**What it does:**
- ✅ Tests health endpoint (works - standard HTTP)
- ❌ Attempts MCP endpoint (fails - requires MCP protocol)
- 📝 Shows Claude Desktop configuration
- 📚 Explains why standard HTTP doesn't work

**Start here if:** You want to code a custom integration.

---

### 3. **mcp_config_examples.json** ⚙️
Configuration examples for Claude Desktop and other MCP clients.

**Contains:**
- Read-only server config
- Admin server config
- Both servers concurrently
- Custom host/port settings
- Qdrant vector store config

**Usage:**
```bash
# For Claude Desktop
cp mcp_config_examples.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
# (Edit to keep only the config you want)
```

**Start here if:** You're configuring Claude Desktop.

---

### 4. **test_mcp_connection.sh** 🧪
Automated test script for verifying server connectivity.

**Usage:**
```bash
# Make executable (already done)
chmod +x test_mcp_connection.sh

# Run the tests
./test_mcp_connection.sh
```

**What it tests:**
1. ✓ Dependencies (curl, bablib)
2. ✓ Server process running
3. ✓ Ports in use (9383, 9384)
4. ✓ Health endpoints reachable
5. ✓ MCP protocol behavior (expected to fail)

**Output:**
- Color-coded results
- Troubleshooting suggestions
- Next steps guidance

**Start here if:** You want to test your setup.

---

## 🚀 Quick Start Guide

### Step 1: Start the Server

```bash
# Read-only server (safe, public access)
bablib serve

# Or admin server (localhost only, full control)
bablib serve --admin

# Or both
bablib serve &
bablib serve --admin &
```

### Step 2: Verify Connection

```bash
# Run the test script
./test_mcp_connection.sh

# Or manually check health
curl http://0.0.0.0:9383/mcp/v1/health
```

### Step 3: Choose Your Client

#### Option A: Claude Desktop (Easiest)
1. See `mcp_config_examples.json` for configuration
2. Add config to `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Restart Claude Desktop
4. Use natural language: "Search my docs for..."

#### Option B: Python Client (Custom)
1. See `mcp_client_example.py` for implementation
2. Install: `pip install httpx asyncio`
3. Run: `python3 mcp_client_example.py`
4. Adapt code for your needs

#### Option C: Manual Connection (Advanced)
1. Read `MCP_CONNECTION_GUIDE.md`
2. Implement MCP protocol from https://modelcontextprotocol.io
3. Handle framing, sessions, capabilities

---

## ⚠️ Important Notes

### MCP is NOT Standard HTTP

**This will NOT work:**
```bash
curl -X POST http://0.0.0.0:9383/mcp/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}'
# Returns: {"detail": "Invalid method"}
```

**Why?** MCP protocol requires:
- Request/response framing
- Session management
- Capability negotiation
- Custom message format

**Only health endpoint works with standard HTTP:**
```bash
curl http://0.0.0.0:9383/mcp/v1/health  # ✅ This works
```

### Server URLs

```
Read-Only Server: http://0.0.0.0:9383
Admin Server:     http://127.0.0.1:9384 (localhost only)
```

**Security:**
- Read-only: Safe, public access, no destructive operations
- Admin: Localhost only, full control, blocked critical ops

---

## 📚 Available Operations

### Read-Only Server (Port 9383)

```
✓ list_projects    - List all documentation projects
✓ search          - Semantic search across documents
✓ get_file        - Read file contents (restrictions apply)
✓ list_files      - List files in project
✓ vector_search   - Search using embeddings
```

### Admin Server (Port 9384)

```
✓ All read-only operations plus:
✓ execute_command - Run Bablib commands
✓ create_project  - Create new projects
✓ crawl          - Start crawling operations
✓ batch_process  - Batch operations

✗ Blocked (Security):
✗ uninstall      - System uninstall
✗ reset          - System reset
✗ delete_all     - Mass deletion
```

---

## 🔧 Troubleshooting

### Server Won't Start
```bash
# Check if port is in use
lsof -i :9383

# Use different port
bablib serve --port 9385
```

### Connection Refused
```bash
# Check if server is running
ps aux | grep bablib

# Start server in foreground to see errors
bablib serve --foreground
```

### "Invalid method" Error
**Cause:** Using standard HTTP for MCP endpoints

**Solution:** Use MCP-compliant client (Claude Desktop, Claude Code, etc.)

**Remember:** Only `/mcp/v1/health` works with standard HTTP!

---

## 📊 File Summary Table

| File | Purpose | Best For |
|------|---------|----------|
| `MCP_CONNECTION_GUIDE.md` | Complete documentation | Understanding all options |
| `mcp_client_example.py` | Python implementation | Custom integrations |
| `mcp_config_examples.json` | Configuration examples | Claude Desktop setup |
| `test_mcp_connection.sh` | Automated testing | Verifying setup |
| `README_MCP_FILES.md` | This file | Getting started |

---

## 🎯 Recommended Reading Order

1. **Just want to test?** → Run `./test_mcp_connection.sh`
2. **Using Claude Desktop?** → Read `mcp_config_examples.json`
3. **Building integration?** → Read `mcp_client_example.py`
4. **Want all details?** → Read `MCP_CONNECTION_GUIDE.md`

---

## 🔗 Additional Resources

- **MCP Protocol Spec:** https://modelcontextprotocol.io
- **Bablib Docs:** See `../CLAUDE.md` in repository root
- **Claude Desktop:** https://claude.ai/download
- **Manual Test Results:** See `manual_test_m.md` for testing session

---

## 📝 Quick Commands Cheat Sheet

```bash
# Start servers
bablib serve                      # Read-only server
bablib serve --admin              # Admin server

# Test connection
./test_mcp_connection.sh          # Automated tests
curl http://0.0.0.0:9383/mcp/v1/health  # Manual health check

# Python client
pip install httpx asyncio         # Install deps
python3 mcp_client_example.py     # Run example

# Check server status
ps aux | grep bablib              # Find process
lsof -i :9383                     # Check port
bablib health --system            # System health
```

---

**Last Updated:** 2025-10-01
**Bablib Version:** 0.3.2+
**All Tests Passing:** ✅

---

## 💡 Pro Tips

1. **Start with the test script** - It diagnoses most issues automatically
2. **Use Claude Desktop** - Easiest way to get started with MCP
3. **Check health endpoint first** - If it works, server is up
4. **Remember: MCP ≠ HTTP** - Don't waste time with curl on MCP endpoints
5. **Read the guide** - Comprehensive answers to all questions

**Happy connecting! 🚀**
