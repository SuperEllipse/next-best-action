#!/usr/bin/env bash
# Diagnose why Agent Studio MCP init may hang while verify_bridge.sh passes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENTRY="irop-snowflake-mcp-bridge"

echo "=== Agent Studio MCP diagnostics ==="
echo

echo "1. Bridge source files"
for f in pyproject.toml bridge.py; do
  if [[ -f "$ROOT/$f" ]]; then echo "  OK  $ROOT/$f"; else echo "  MISSING $ROOT/$f"; fi
done
echo

echo "2. uvx availability"
if [[ -x /home/cdsw/.local/bin/uvx ]]; then
  echo "  OK  /home/cdsw/.local/bin/uvx"
else
  echo "  MISSING /home/cdsw/.local/bin/uvx — run: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
if env -i HOME=/home/cdsw PATH=/usr/bin:/bin command -v uvx >/dev/null 2>&1; then
  echo "  WARN uvx found on minimal PATH without .local/bin (unexpected)"
else
  echo "  NOTE uvx NOT on minimal PATH — registration JSON must set PATH in env"
fi
echo

echo "3. Broken legacy symlinks (can break uvx)"
for link in /home/cdsw/.local/bin/snowflake-hosted-mcp-bridge; do
  if [[ -L "$link" && ! -e "$link" ]]; then
    echo "  BROKEN $link"
    echo "        Fix: rm -f $link"
  elif [[ -e "$link" ]]; then
    echo "  LEGACY $link (safe to remove if unused)"
  fi
done
echo

echo "4. uvx cold-start timing (Agent Studio init timeout ~30s)"
export PATH="/home/cdsw/.local/bin:/usr/bin:/bin"
export HOME="/home/cdsw"
export UV_LINK_MODE=copy
export UV_NO_PROGRESS=1
export SNOWFLAKE_PAT=dummy
if [[ -z "${SNOWFLAKE_ACCOUNT_URL:-}" ]]; then
  echo "ERROR: Set SNOWFLAKE_ACCOUNT_URL in project .env before running diagnose."
  exit 1
fi
START=$(date +%s.%N)
timeout 45 uvx --from "$ROOT" "$ENTRY" </dev/null 2>/dev/null || true
END=$(date +%s.%N)
printf "  uvx --from startup probe: %.1fs\n" "$(echo "$END - $START" | bc)"
echo "  If >25s on first run, re-run install.sh to warm cache before Agent Studio registration"
echo

echo "5. Registration JSON to paste in Agent Studio"
echo "   File: $ROOT/../mcp_snowflake_agent_studio.json"
echo "   Must include PATH and HOME in env (see file)."
echo

echo "6. If MCP still hangs in Agent Studio"
echo "   - Delete old MCP registration and re-register with updated JSON"
echo "   - Enter REAL SNOWFLAKE_PAT on the workflow MCP instance (not dummy)"
echo "   - Try absolute uvx variant: mcp_snowflake_agent_studio_absolute_uvx.json"
echo "   - Fallback: use custom tool tools/fetch_passenger_profile (direct HTTP, no MCP bridge)"
