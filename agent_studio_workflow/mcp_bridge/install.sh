#!/usr/bin/env bash
# Prepare Snowflake MCP bridge for Agent Studio (uvx).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
ENTRY="irop-snowflake-mcp-bridge"

echo "=== Syncing bridge dependencies ==="
uv sync

echo "=== Installing uv tool (faster uvx startup for Agent Studio) ==="
export SNOWFLAKE_PAT=dummy
: "${SNOWFLAKE_ACCOUNT_URL:?Set SNOWFLAKE_ACCOUNT_URL in project .env}"
uv tool install --force --from "$ROOT" "$ENTRY" || {
  echo "WARN: uv tool install failed (NFS lock?). --from registration still works after verify_bridge.sh."
}

echo "=== Pre-warming uvx caches (stdio server exits on closed stdin) ==="
timeout 15 uvx --from "$ROOT" "$ENTRY" </dev/null 2>/dev/null || true
timeout 15 uvx "$ENTRY" </dev/null 2>/dev/null || true

echo ""
echo "=== Done ==="
echo "Verify: bash $ROOT/verify_bridge.sh"
echo "Register (path):  $ROOT/../mcp_snowflake_agent_studio.json"
echo "Register (fast):    $ROOT/../mcp_snowflake_agent_studio_fast.json  (after uv tool install succeeds)"
