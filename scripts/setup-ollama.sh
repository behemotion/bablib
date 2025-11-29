#!/bin/bash
# Ollama local installation script for Bablib

set -e

echo "🤖 Setting up Ollama for Bablib..."

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is already installed"
    ollama --version
else
    echo "📦 Installing Ollama..."

    # Detect OS and install accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ollama
        else
            echo "Installing via curl..."
            curl -fsSL https://ollama.ai/install.sh | sh
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl -fsSL https://ollama.ai/install.sh | sh
    else
        echo "❌ Unsupported OS. Please install Ollama manually from https://ollama.ai"
        exit 1
    fi
fi

# Start Ollama service (if not running)
echo "🚀 Starting Ollama service..."
if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &
    sleep 5
fi

# Pull required embedding models
echo "📥 Pulling embedding models..."
echo "Pulling mxbai-embed-large (default model)..."
ollama pull mxbai-embed-large

echo "Pulling nomic-embed-text (alternative model)..."
ollama pull nomic-embed-text

# Test installation
echo "🧪 Testing Ollama installation..."
if ollama list | grep -E "(mxbai-embed-large|nomic-embed-text)"; then
    echo "✅ Ollama setup complete! Models ready for Bablib."
else
    echo "❌ Model installation failed. Please check Ollama setup."
    exit 1
fi

echo "🎉 Ollama is ready for Bablib!"
echo "Available models:"
ollama list