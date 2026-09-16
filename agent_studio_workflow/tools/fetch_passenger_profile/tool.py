"""
This tool fetches passenger profile data from Snowflake via the hosted MCP HTTP endpoint
(or direct SQL over the Snowflake REST API pattern). Use this INSTEAD of registering
Snowflake MCP in Agent Studio (which only supports uvx/npx local processes).
Returns:
    str: passenger profile summary for IROP decisioning
"""

import argparse
import json
import os

import httpx
from pydantic import BaseModel, Field

PROFILE_TABLE = "CUSTOMER_DB.PROFILES.PASSENGER_PROFILES"


class UserParameters(BaseModel):
    snowflake_pat: str = Field(
        default="",
        description="Snowflake Programmatic Access Token (falls back to SNOWFLAKE_PAT env)",
    )
    snowflake_account_url: str = Field(
        default="",
        description="Snowflake account URL (falls back to SNOWFLAKE_ACCOUNT_URL env)",
    )


class ToolParameters(BaseModel):
    customer_id: str = Field(description="Customer ID - unique passenger identifier")


def _mcp_url(account_url: str) -> str:
    base = account_url.rstrip("/")
    return (
        f"{base}/api/v2/databases/CUSTOMER_DB"
        f"/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER"
    )


def _headers(pat: str) -> dict:
    return {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
    }


def run_tool(config: UserParameters, args: ToolParameters):
    pat = config.snowflake_pat or os.environ.get("SNOWFLAKE_PAT", "")
    account_url = (config.snowflake_account_url or os.environ.get("SNOWFLAKE_ACCOUNT_URL", "")).strip()
    if not pat:
        raise ValueError("SNOWFLAKE_PAT is required in UserParameters or environment.")
    if not account_url:
        raise ValueError("SNOWFLAKE_ACCOUNT_URL is required in UserParameters or environment.")

    url = _mcp_url(account_url)
    sql = (
        f"SELECT * FROM {PROFILE_TABLE} WHERE customer_id = '{args.customer_id.replace(chr(39), chr(39)+chr(39))}'"
    )

    # Call Snowflake hosted MCP tools/call (JSON-RPC over streamable-http)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "sql_exec_tool",
            "arguments": {"sql": sql},
        },
    }
    resp = httpx.post(url, headers=_headers(pat), json=payload, timeout=30.0)

    if resp.status_code != 200:
        # Fallback: list tools and return connection info for agent debugging
        list_resp = httpx.post(
            url,
            headers=_headers(pat),
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            timeout=15.0,
        )
        return (
            f"MCP call failed ({resp.status_code}): {resp.text[:500]}. "
            f"tools/list status={list_resp.status_code}. "
            f"Query intended: {sql}"
        )

    data = resp.json()
    result = data.get("result") or data
    return json.dumps(result, default=str)


OUTPUT_KEY = "tool_output"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True, help="JSON string for tool configuration")
    parser.add_argument("--tool-params", required=True, help="JSON string for tool arguments")
    cli = parser.parse_args()

    config = UserParameters(**json.loads(cli.user_params))
    params = ToolParameters(**json.loads(cli.tool_params))
    output = run_tool(config, params)
    print(OUTPUT_KEY, output)
