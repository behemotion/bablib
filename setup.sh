#!/bin/bash
# Setup script for Bablib

set -e

echo "==================================="
echo "     Bablib Setup Script"
echo "==================================="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.10 or higher is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Check if pip is installed
echo "Checking pip..."
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ pip3 installed${NC}"

# Install Python dependencies
echo
echo "Installing Python dependencies..."
pip3 install -e . --quiet
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Check Docker
echo
echo "Checking Docker..."
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        echo -e "${GREEN}✓ Docker is installed and running${NC}"
        DOCKER_AVAILABLE=true
    else
        echo -e "${YELLOW}⚠ Docker is installed but not running${NC}"
        DOCKER_AVAILABLE=false
    fi
else
    echo -e "${YELLOW}⚠ Docker is not installed (required for Qdrant and Redis)${NC}"
    DOCKER_AVAILABLE=false
fi

# Start Docker services if available
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo
    echo "Starting Docker services..."

    # Create docker directory if it doesn't exist
    mkdir -p docker/qdrant docker/redis

    # Start services
    cd docker
    docker-compose up -d
    cd ..

    echo -e "${GREEN}✓ Docker services started${NC}"
    echo "  - Qdrant: http://localhost:6333"
    echo "  - Redis: redis://localhost:6379"
fi

# Check Ollama
echo
echo "Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama is installed${NC}"

    # Check if Ollama is running
    if curl -s http://localhost:11434/api/version &> /dev/null; then
        echo -e "${GREEN}✓ Ollama is running${NC}"

        # Pull required embedding model
        echo "Checking embedding model..."
        if ollama list | grep -q "mxbai-embed-large"; then
            echo -e "${GREEN}✓ mxbai-embed-large model is available${NC}"
        else
            echo -e "${YELLOW}Pulling mxbai-embed-large model...${NC}"
            ollama pull mxbai-embed-large
            echo -e "${GREEN}✓ Model downloaded${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Ollama is not running. Start it with: ollama serve${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Ollama is not installed (required for embeddings)${NC}"
    echo "  Install from: https://ollama.ai"
fi

# Create data directories
echo
echo "Creating data directories..."
mkdir -p data logs
echo -e "${GREEN}✓ Data directories created${NC}"

# Test installation
echo
echo "Testing Bablib installation..."
if python3 -c "from src.cli.main import main; print('CLI OK')" &> /dev/null; then
    echo -e "${GREEN}✓ Bablib CLI is working${NC}"
else
    echo -e "${RED}✗ Bablib CLI test failed${NC}"
    exit 1
fi

# Display next steps
echo
echo "==================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "==================================="
echo
echo "Next steps:"
echo "1. Make sure Ollama is running: ollama serve"
if [ "$DOCKER_AVAILABLE" = false ]; then
    echo "2. Install and start Docker for vector storage"
fi
echo "3. Create your first project: bablib create <name> --url <docs-url>"
echo "4. Start crawling: bablib crawl <name>"
echo "5. Search documentation: bablib search <query>"
echo
echo "For MCP integration:"
echo "  bablib serve --port 8000"
echo
echo "View all commands: bablib --help"
echo