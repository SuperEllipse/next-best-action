#!/usr/bin/env bash
# Verify Snowflake MCP bridge: direct HTTP, bridge _rpc, and stdio MCP via uvx.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
cd "$ROOT"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

if [[ -z "${SNOWFLAKE_PAT:-}" || "${SNOWFLAKE_PAT}" == "dummy" ]]; then
  echo "ERROR: Set SNOWFLAKE_PAT in $PROJECT_ROOT/.env before running verify."
  exit 1
fi

if [[ ! -f "$ROOT/pyproject.toml" || ! -f "$ROOT/bridge.py" ]]; then
  echo "ERROR: Missing $ROOT/pyproject.toml or bridge.py — uvx will fail and Agent Studio will time out."
  exit 1
fi

if [[ -z "${SNOWFLAKE_ACCOUNT_URL:-}" ]]; then
  echo "ERROR: Set SNOWFLAKE_ACCOUNT_URL in $PROJECT_ROOT/.env before running verify."
  exit 1
fi
SQL="SELECT customer_id, full_name, loyalty_tier FROM CUSTOMER_DB.PROFILES.PASSENGER_PROFILES WHERE customer_id = 'CUST-404'"
export SQL
ENTRY="irop-snowflake-mcp-bridge"

echo "=== 0. Bridge project files ==="
if ! uv sync --check >/dev/null 2>&1; then
  echo "WARN: uv sync --check failed; running uv sync..."
  uv sync
fi
echo "OK — pyproject.toml and bridge.py present; uv project resolves"

echo ""
echo "=== 1. Direct HTTP to Snowflake MCP (no bridge) ==="
SQL="$SQL" "$ROOT/.venv/bin/python" - <<'PY'
import os, time, httpx
url = os.environ["SNOWFLAKE_ACCOUNT_URL"].rstrip("/") + "/api/v2/databases/CUSTOMER_DB/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER"
headers = {
    "Authorization": f"Bearer {os.environ['SNOWFLAKE_PAT']}",
    "Content-Type": "application/json",
    "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
}
sql = os.environ["SQL"]
t0 = time.time()
r = httpx.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {"name": "sql_exec_tool", "arguments": {"sql": sql}},
}, timeout=120)
r.raise_for_status()
print(f"OK in {time.time()-t0:.1f}s —", r.json()["result"]["content"][0]["text"][:120], "...")
PY

echo ""
echo "=== 2. Bridge _rpc (HTTP layer only) ==="
SQL="$SQL" "$ROOT/.venv/bin/python" - <<'PY'
import os, time
from bridge import _rpc
sql = os.environ["SQL"]
t0 = time.time()
r = _rpc("tools/call", {"name": "sql_exec_tool", "arguments": {"sql": sql}})
print(f"OK in {time.time()-t0:.1f}s —", str(r)[:120], "...")
PY

echo ""
echo "=== 3. Full stdio MCP via uvx --from (workbench shell env) ==="
SQL="$SQL" ROOT="$ROOT" ENTRY="$ENTRY" "$ROOT/.venv/bin/python" - <<'PY'
import asyncio, os, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.environ["ROOT"]
ENTRY = os.environ["ENTRY"]
SQL = os.environ["SQL"]

async def main():
    params = StdioServerParameters(
        command="/home/cdsw/.local/bin/uvx",
        args=["--from", ROOT, ENTRY],
        env=os.environ.copy(),
    )
    t0 = time.time()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)
            tools = await session.list_tools()
            print(f"initialize+list_tools OK in {time.time()-t0:.1f}s — tools: {[t.name for t in tools.tools]}")
            result = await asyncio.wait_for(
                session.call_tool("sql_exec_tool", {"sql": SQL}), timeout=120
            )
            text = result.content[0].text if result.content else str(result)
            print(f"call_tool OK in {time.time()-t0:.1f}s — {text[:120]}...")

asyncio.run(main())
PY

echo ""
echo "=== 4. Agent Studio simulation (registration env only, command=uvx) ==="
SQL="$SQL" ROOT="$ROOT" ENTRY="$ENTRY" "$ROOT/.venv/bin/python" - <<'PY'
import asyncio, os, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.environ["ROOT"]
ENTRY = os.environ["ENTRY"]
SQL = os.environ["SQL"]

# Matches mcp_snowflake_agent_studio.json — no inherited shell PATH.
REGISTRATION_ENV = {
    "PATH": "/home/cdsw/.local/bin:/usr/local/bin:/usr/bin:/bin",
    "HOME": "/home/cdsw",
    "UV_LINK_MODE": "copy",
    "UV_NO_PROGRESS": "1",
    "SNOWFLAKE_PAT": os.environ["SNOWFLAKE_PAT"],
    "SNOWFLAKE_ACCOUNT_URL": os.environ["SNOWFLAKE_ACCOUNT_URL"],
}

async def main():
    params = StdioServerParameters(
        command="uvx",
        args=["--from", ROOT, ENTRY],
        env=REGISTRATION_ENV,
    )
    t0 = time.time()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)
            tools = await session.list_tools()
            print(f"initialize+list_tools OK in {time.time()-t0:.1f}s — tools: {[t.name for t in tools.tools]}")
            result = await asyncio.wait_for(
                session.call_tool("sql_exec_tool", {"sql": SQL}), timeout=120
            )
            text = result.content[0].text if result.content else str(result)
            print(f"call_tool OK in {time.time()-t0:.1f}s — {text[:120]}...")

asyncio.run(main())
PY

echo ""
echo "=== ALL CHECKS PASSED ==="
echo "Use mcp_snowflake_agent_studio.json in Agent Studio (includes PATH/HOME/UV env)."
