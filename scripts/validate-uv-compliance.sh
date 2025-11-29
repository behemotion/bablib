#!/bin/bash
# UV Compliance Validation Script for Bablib
# Usage: ./scripts/validate-uv-compliance.sh [--quiet] [--json] [--help]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Default options
QUIET=false
JSON_OUTPUT=false
SHOW_HELP=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quiet|-q)
            QUIET=true
            shift
            ;;
        --json|-j)
            JSON_OUTPUT=true
            shift
            ;;
        --help|-h)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Show help
if [ "$SHOW_HELP" = true ]; then
    echo "UV Compliance Validation Script for Bablib"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --quiet, -q      Suppress verbose output"
    echo "  --json, -j       Output results in JSON format"
    echo "  --help, -h       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run with full output"
    echo "  $0 --quiet           # Run with minimal output"
    echo "  $0 --json            # Output JSON for CI/CD"
    echo ""
    exit 0
fi

# Print header unless quiet
if [ "$QUIET" = false ]; then
    echo -e "${BLUE}${BOLD}Bablib UV Compliance Validation${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed or not in PATH${NC}"
    exit 1
fi

# Check if required Python packages are available
echo -n "Checking Python dependencies... "
if python3 -c "import httpx, rich, packaging" 2>/dev/null; then
    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓${NC}"
    fi
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: Required Python packages not found${NC}"
    echo "Install with: pip install httpx rich packaging"
    exit 1
fi

# Check if UV is available (warn if not, but don't fail)
if ! command -v uv &> /dev/null; then
    if [ "$QUIET" = false ]; then
        echo -e "${YELLOW}Warning: UV not found in PATH. Some tests may fail.${NC}"
        echo -e "${YELLOW}Install with: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
        echo ""
    fi
fi

# Change to project root
cd "$PROJECT_ROOT"

# Run the UV compliance validation
if [ "$QUIET" = true ]; then
    # Run quietly and capture exit code
    if python3 test_uv_compliance.py > /tmp/uv_compliance_output.log 2>&1; then
        # Extract just the summary
        COMPLIANCE_SCORE=$(grep -o "Passed: [0-9]*/[0-9]* ([0-9]*\.[0-9]*%)" /tmp/uv_compliance_output.log | tail -1)
        if [ -n "$COMPLIANCE_SCORE" ]; then
            echo -e "${GREEN}UV Compliance: $COMPLIANCE_SCORE${NC}"
        else
            echo -e "${YELLOW}UV Compliance: Tests completed (see log for details)${NC}"
        fi

        # Clean up
        rm -f /tmp/uv_compliance_output.log
        exit 0
    else
        echo -e "${RED}UV Compliance: Tests failed${NC}"
        if [ "$JSON_OUTPUT" = false ]; then
            echo "Run without --quiet to see detailed output"
        fi
        rm -f /tmp/uv_compliance_output.log
        exit 1
    fi
elif [ "$JSON_OUTPUT" = true ]; then
    # For JSON output, we'd need to modify the Python script
    # For now, just run normally and suggest using Python directly for JSON
    echo -e "${YELLOW}JSON output not yet implemented.${NC}"
    echo "For structured output, run: python3 test_uv_compliance.py"
    exit 1
else
    # Run with full output
    if python3 test_uv_compliance.py; then
        echo ""
        echo -e "${GREEN}${BOLD}UV Compliance validation completed successfully!${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}${BOLD}UV Compliance validation failed. Check output above for details.${NC}"
        exit 1
    fi
fi