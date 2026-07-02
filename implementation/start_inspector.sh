#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(command -v python3 || command -v python)

echo "=================================================="
echo " MCP Inspector — SQLite Lab"
echo "=================================================="
echo " Server : $SCRIPT_DIR/mcp_server.py"
echo " Python : $PYTHON"
echo ""
echo " Open the URL printed below in your browser."
echo "=================================================="
echo ""

mkdir -p "$SCRIPT_DIR/../.npm-cache"
NPM_CONFIG_CACHE="$SCRIPT_DIR/../.npm-cache" \
  npx -y @modelcontextprotocol/inspector \
  "$PYTHON" "$SCRIPT_DIR/mcp_server.py"