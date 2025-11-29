#!/bin/bash

# Bablib MCP Server Connection Test Script
#
# This script tests the connection to Bablib MCP servers
# and provides helpful debugging information.
#
# Usage:
#   chmod +x test_mcp_connection.sh
#   ./test_mcp_connection.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Server URLs
READ_ONLY_URL="http://0.0.0.0:9383"
ADMIN_URL="http://127.0.0.1:9384"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Bablib MCP Server Connection Test                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to test endpoint
test_endpoint() {
    local url=$1
    local name=$2

    echo -e "${BLUE}Testing ${name}...${NC}"
    echo "URL: ${url}"

    if curl -s -f -m 5 "${url}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ ${name} is reachable${NC}"

        # Get and display response
        response=$(curl -s "${url}")
        echo "Response:"
        echo "${response}" | python3 -m json.tool 2>/dev/null || echo "${response}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ ${name} is not reachable${NC}"
        echo ""
        return 1
    fi
}

# Function to check if server is running
check_server_process() {
    echo -e "${BLUE}Checking if Bablib server is running...${NC}"

    if pgrep -f "bablib serve" > /dev/null; then
        echo -e "${GREEN}✓ Bablib server process found${NC}"
        echo "Process details:"
        ps aux | grep "bablib serve" | grep -v grep
        echo ""
        return 0
    else
        echo -e "${YELLOW}⚠ No Bablib server process found${NC}"
        echo "Server may not be running. Start with: bablib serve"
        echo ""
        return 1
    fi
}

# Function to check port availability
check_port() {
    local port=$1
    local name=$2

    echo -e "${BLUE}Checking if port ${port} is in use...${NC}"

    if command_exists lsof; then
        if lsof -i ":${port}" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Port ${port} is in use (${name})${NC}"
            lsof -i ":${port}" | grep LISTEN
            echo ""
            return 0
        else
            echo -e "${YELLOW}⚠ Port ${port} is not in use${NC}"
            echo ""
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ lsof not available, skipping port check${NC}"
        echo ""
        return 1
    fi
}

# Main tests
echo "═══════════════════════════════════════════════════════════════"
echo "1. Dependency Checks"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check dependencies
if ! command_exists curl; then
    echo -e "${RED}✗ curl is not installed${NC}"
    echo "Install with: brew install curl"
    exit 1
fi
echo -e "${GREEN}✓ curl is available${NC}"

if ! command_exists bablib; then
    echo -e "${RED}✗ bablib is not installed${NC}"
    echo "Install with: uv tool install git+https://github.com/behemotion/doc-bro"
    exit 1
fi
echo -e "${GREEN}✓ bablib is available${NC}"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "2. Server Process Check"
echo "═══════════════════════════════════════════════════════════════"
echo ""

server_running=0
check_server_process && server_running=1

echo "═══════════════════════════════════════════════════════════════"
echo "3. Port Availability Check"
echo "═══════════════════════════════════════════════════════════════"
echo ""

port_9383_used=0
port_9384_used=0
check_port 9383 "Read-Only Server" && port_9383_used=1
check_port 9384 "Admin Server" && port_9384_used=1

echo "═══════════════════════════════════════════════════════════════"
echo "4. Health Endpoint Tests (Standard HTTP)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

read_only_ok=0
admin_ok=0

test_endpoint "${READ_ONLY_URL}/mcp/v1/health" "Read-Only Server Health" && read_only_ok=1
test_endpoint "${ADMIN_URL}/mcp/v1/health" "Admin Server Health" && admin_ok=1

echo "═══════════════════════════════════════════════════════════════"
echo "5. MCP Protocol Test (Will Fail - Expected)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo -e "${BLUE}Testing MCP endpoint with standard HTTP (should fail)...${NC}"
echo "URL: ${READ_ONLY_URL}/mcp/v1/search"
echo ""

response=$(curl -s -X POST "${READ_ONLY_URL}/mcp/v1/search" \
    -H "Content-Type: application/json" \
    -d '{"query":"test"}' 2>/dev/null || echo "Connection failed")

if echo "${response}" | grep -q "Invalid method"; then
    echo -e "${GREEN}✓ Expected error received: 'Invalid method'${NC}"
    echo "This is CORRECT - MCP endpoints don't work with standard HTTP"
else
    echo -e "${YELLOW}⚠ Unexpected response:${NC}"
    echo "${response}"
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "Test Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ $read_only_ok -eq 1 ] && [ $admin_ok -eq 1 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo ""
    echo "Both servers are running and reachable:"
    echo "  • Read-Only Server: ${READ_ONLY_URL}"
    echo "  • Admin Server:     ${ADMIN_URL}"
    echo ""
    echo "Next steps:"
    echo "  1. Use Claude Desktop with MCP configuration"
    echo "  2. Use Claude Code CLI"
    echo "  3. Implement custom MCP client"
    echo ""
    echo "See MCP_CONNECTION_GUIDE.md for details"
elif [ $read_only_ok -eq 1 ] || [ $admin_ok -eq 1 ]; then
    echo -e "${YELLOW}⚠ PARTIAL SUCCESS${NC}"
    echo ""
    [ $read_only_ok -eq 1 ] && echo -e "${GREEN}✓ Read-Only Server: OK${NC}" || echo -e "${RED}✗ Read-Only Server: NOT REACHABLE${NC}"
    [ $admin_ok -eq 1 ] && echo -e "${GREEN}✓ Admin Server: OK${NC}" || echo -e "${RED}✗ Admin Server: NOT REACHABLE${NC}"
    echo ""
    echo "Troubleshooting:"
    [ $read_only_ok -eq 0 ] && echo "  • Start read-only: bablib serve"
    [ $admin_ok -eq 0 ] && echo "  • Start admin: bablib serve --admin"
else
    echo -e "${RED}❌ TESTS FAILED${NC}"
    echo ""
    echo -e "${RED}✗ Neither server is reachable${NC}"
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Start the server: bablib serve"
    echo "  2. Check for errors: bablib serve --foreground"
    echo "  3. Verify installation: bablib --version"
    echo "  4. Check system health: bablib health --system"
    echo ""
    [ $server_running -eq 0 ] && echo "  ⚠ Server process not found - server may not be running"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Documentation"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "For more information:"
echo "  • Connection Guide: ./MCP_CONNECTION_GUIDE.md"
echo "  • Python Example:   ./mcp_client_example.py"
echo "  • Config Examples:  ./mcp_config_examples.json"
echo ""
