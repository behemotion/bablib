#!/bin/bash

# Bablib MCP Global Installation Script for Claude Desktop
# This script installs the Bablib MCP server configuration globally

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BABLIB_PATH="${SCRIPT_DIR}/bablib"
CONFIG_SOURCE="${SCRIPT_DIR}/claude_desktop_config.json"

# Claude Desktop config paths for different OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CLAUDE_CONFIG_FILE="${CLAUDE_CONFIG_DIR}/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CLAUDE_CONFIG_DIR="$HOME/.config/Claude"
    CLAUDE_CONFIG_FILE="${CLAUDE_CONFIG_DIR}/claude_desktop_config.json"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash, Cygwin)
    CLAUDE_CONFIG_DIR="$APPDATA/Claude"
    CLAUDE_CONFIG_FILE="${CLAUDE_CONFIG_DIR}/claude_desktop_config.json"
else
    echo -e "${RED}Unsupported operating system: $OSTYPE${NC}"
    exit 1
fi

echo "Bablib MCP Server Global Installation"
echo "======================================"
echo ""

# Check if Bablib CLI exists
if [ ! -f "$BABLIB_PATH" ]; then
    echo -e "${RED}Error: Bablib CLI not found at $BABLIB_PATH${NC}"
    echo "Please ensure you're running this script from the Bablib repository directory."
    exit 1
fi

# Make Bablib executable
chmod +x "$BABLIB_PATH"
echo -e "${GREEN}✓${NC} Bablib CLI is executable"

# Check if Claude config directory exists
if [ ! -d "$CLAUDE_CONFIG_DIR" ]; then
    echo -e "${YELLOW}Claude Desktop config directory doesn't exist. Creating it...${NC}"
    mkdir -p "$CLAUDE_CONFIG_DIR"
fi

# Backup existing configuration if it exists
if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    BACKUP_FILE="${CLAUDE_CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}Backing up existing configuration to:${NC}"
    echo "  $BACKUP_FILE"
    cp "$CLAUDE_CONFIG_FILE" "$BACKUP_FILE"
fi

# Function to merge JSON configurations
merge_configs() {
    if [ -f "$CLAUDE_CONFIG_FILE" ]; then
        # Use Python to merge JSON configs
        python3 - <<EOF
import json
import sys

# Read existing config
with open('$CLAUDE_CONFIG_FILE', 'r') as f:
    existing = json.load(f)

# Read new Bablib config
with open('$CONFIG_SOURCE', 'r') as f:
    new_config = json.load(f)

# Merge mcpServers
if 'mcpServers' not in existing:
    existing['mcpServers'] = {}

# Update Bablib configuration with correct path
new_config['mcpServers']['bablib']['command'] = '$BABLIB_PATH'
existing['mcpServers']['bablib'] = new_config['mcpServers']['bablib']

# Write merged config
with open('$CLAUDE_CONFIG_FILE', 'w') as f:
    json.dump(existing, f, indent=2)

print("Configuration merged successfully")
EOF
    else
        # No existing config, create new one with correct path
        python3 - <<EOF
import json

# Read template config
with open('$CONFIG_SOURCE', 'r') as f:
    config = json.load(f)

# Update with correct path
config['mcpServers']['bablib']['command'] = '$BABLIB_PATH'

# Write new config
with open('$CLAUDE_CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)

print("Configuration created successfully")
EOF
    fi
}

# Merge or create configuration
echo -e "${YELLOW}Installing Bablib MCP configuration...${NC}"
if merge_configs; then
    echo -e "${GREEN}✓${NC} Configuration installed successfully"
else
    echo -e "${RED}Failed to install configuration${NC}"
    exit 1
fi

# Verify Docker services
echo ""
echo "Checking prerequisites..."

# Check Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker is installed"

    # Check if containers are running
    if docker ps | grep -q "qdrant-crawling-data"; then
        echo -e "${GREEN}✓${NC} Qdrant container is running"
    else
        echo -e "${YELLOW}!${NC} Qdrant container is not running"
        echo "  Run: docker-compose -f ${SCRIPT_DIR}/docker/docker-compose.yml up -d"
    fi

    if docker ps | grep -q "redis-cash"; then
        echo -e "${GREEN}✓${NC} Redis container is running"
    else
        echo -e "${YELLOW}!${NC} Redis container is not running"
        echo "  Run: docker-compose -f ${SCRIPT_DIR}/docker/docker-compose.yml up -d"
    fi
else
    echo -e "${YELLOW}!${NC} Docker is not installed"
fi

# Check Ollama
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓${NC} Ollama is installed"

    # Check if model is available
    if ollama list | grep -q "mxbai-embed-large"; then
        echo -e "${GREEN}✓${NC} Embedding model (mxbai-embed-large) is available"
    else
        echo -e "${YELLOW}!${NC} Embedding model not found"
        echo "  Run: ollama pull mxbai-embed-large"
    fi
else
    echo -e "${YELLOW}!${NC} Ollama is not installed"
fi

# Test MCP server
echo ""
echo "Testing MCP server..."
if timeout 5 "$BABLIB_PATH" serve --port 9382 > /dev/null 2>&1 & then
    sleep 2
    if curl -s http://localhost:9382/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} MCP server test successful"
        pkill -f "bablib serve" 2>/dev/null || true
    else
        echo -e "${YELLOW}!${NC} MCP server started but health check failed"
    fi
else
    echo -e "${YELLOW}!${NC} Could not test MCP server"
fi

# Final instructions
echo ""
echo "========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "========================================="
echo ""
echo "Configuration installed at:"
echo "  $CLAUDE_CONFIG_FILE"
echo ""
echo "Next steps:"
echo "1. Restart Claude Desktop completely (Quit and reopen)"
echo "2. The Bablib MCP server will be available in all conversations"
echo "3. Test with: 'Can you check Bablib status?'"
echo ""
echo "To start services manually:"
echo "  docker-compose -f ${SCRIPT_DIR}/docker/docker-compose.yml up -d"
echo "  ollama serve"
echo ""
echo "For more information, see INSTALL_MCP.md"