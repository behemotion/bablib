# Bablib MCP Server Configurations

This directory contains MCP (Model Context Protocol) server configurations for AI assistants.

## Available Configurations

### bablib.json (Read-Only Server)
- **Port**: 9383
- **Access**: Read-only operations
- **Security**: Safe for external access
- **Features**:
  - Project listing and search
  - File metadata access (project-type dependent)
  - Vector search across documentation
  - Health monitoring

### bablib-admin.json (Admin Server)
- **Port**: 9384
- **Access**: Full administrative control
- **Security**: Localhost-only (127.0.0.1) for security
- **Features**:
  - Complete Bablib command execution (with security restrictions)
  - Project creation and management
  - Crawling operations
  - Full file access for storage projects
  - **BLOCKED**: Uninstall, reset, and delete-all-projects operations

## Setup Instructions

### For Claude Desktop
1. Copy the desired configuration to your Claude Desktop configuration
2. Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bablib": {
      "command": "uvx",
      "args": ["bablib", "serve", "--port", "9383", "--foreground"],
      "env": {
        "BABLIB_LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

### For Other MCP Clients
Use the configuration files as templates for your specific MCP client setup.

## Security Notes

- **Read-Only Server**: Safe for general use, provides read access to projects
- **Admin Server**: Use only when full control is needed, restricted to localhost
- **Network Access**: Admin server only accepts connections from 127.0.0.1
- **File Access**: Varies by project type (crawling=metadata, storage=full content)
- **Operation Restrictions**: Admin server blocks uninstall, reset, and delete-all operations for safety

## Prerequisites

- Bablib installed via `uv tool install git+https://github.com/behemotion/bablib`
- At least one Bablib project created
- Ports 9383/9384 available

## Testing

```bash
# Test read-only server
curl http://localhost:9383/mcp/v1/health

# Test admin server (localhost only)
curl http://127.0.0.1:9384/mcp/v1/health
```

## Troubleshooting

- **Server won't start**: Check port availability with `lsof -i :9383`
- **Permission denied**: Ensure admin server connects to 127.0.0.1 only
- **File access errors**: Verify project exists and type allows requested access