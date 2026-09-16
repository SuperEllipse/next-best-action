"""
stdio MCP bridge → Snowflake-managed hosted MCP server (streamable-http + PAT).

Compatible with MCP SDK 1.x (Agent Studio MCP client). tools/list is static so
registration works with dummy SNOWFLAKE_PAT. Real PAT required at workflow runtime.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import httpx
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

MCP_PATH = "/api/v2/databases/CUSTOMER_DB/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER"


def _account_url() -> str:
    url = os.environ.get("SNOWFLAKE_ACCOUNT_URL", "").strip()
    if not url:
        raise ValueError("SNOWFLAKE_ACCOUNT_URL is not set. See project .env.example.")
    return url.rstrip("/")

STATIC_SQL_TOOL = types.Tool(
    name="sql_exec_tool",
    description=(
        "Execute SQL queries against CUSTOMER_DB to retrieve passenger profile data. "
        "Example: SELECT * FROM CUSTOMER_DB.PROFILES.PASSENGER_PROFILES WHERE customer_id = 'CUST-404'"
    ),
    inputSchema={
        "type": "object",
        "description": "Tool to execute a SQL query.",
        "properties": {
            "sql": {
                "description": "Single SQL query to execute.",
                "type": "string",
            }
        },
        "required": ["sql"],
    },
)

server = Server("irop-snowflake-mcp-bridge")


def _mcp_url() -> str:
    return f"{_account_url()}{MCP_PATH}"


def _pat() -> str:
    raw = os.environ.get("SNOWFLAKE_PAT", "").strip()
    if raw.lower() in {"", "dummy", "placeholder", "changeme", "your_pat_here", "<pat>"}:
        return ""
    return raw


def _headers() -> dict[str, str]:
    pat = _pat()
    if not pat:
        raise RuntimeError(
            "SNOWFLAKE_PAT is not set. Enter your real PAT on the workflow MCP instance."
        )
    return {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
    }


def _rpc(method: str, params: dict | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    resp = httpx.post(_mcp_url(), headers=_headers(), json=payload, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"]))
    return data.get("result", data)


@server.list_tools()
async def handle_list_tools(_request: types.ListToolsRequest) -> types.ListToolsResult:
    # Static catalog — no Snowflake call; works with dummy PAT at MCP registration.
    return types.ListToolsResult(tools=[STATIC_SQL_TOOL])


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    rpc_params = {"name": name, "arguments": arguments or {}}
    try:
        result = await asyncio.to_thread(_rpc, "tools/call", rpc_params)
    except Exception as exc:
        return [
            types.TextContent(
                type="text",
                text=f"Snowflake MCP call failed: {exc}. Set SNOWFLAKE_PAT on the workflow MCP instance.",
            )
        ]

    if isinstance(result, dict) and "content" in result:
        chunks: list[str] = []
        for item in result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
            else:
                chunks.append(json.dumps(item, default=str))
        text = "\n".join(chunks) if chunks else json.dumps(result, default=str)
    else:
        text = json.dumps(result, default=str, indent=2)
    return [types.TextContent(type="text", text=text)]


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="irop-snowflake-mcp-bridge",
                server_version="0.3.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    print("irop-snowflake-mcp-bridge starting (stdio MCP)", file=sys.stderr, flush=True)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
