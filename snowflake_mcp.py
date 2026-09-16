"""Snowflake MCP integration — pattern from test_crewai_mcp.ipynb."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

import httpx
from crewai_tools import MCPServerAdapter

PROFILE_TABLE = "CUSTOMER_DB.PROFILES.PASSENGER_PROFILES"


def get_mcp_server_url(account_url: Optional[str] = None) -> str:
    base = (account_url or os.environ.get("SNOWFLAKE_ACCOUNT_URL", "")).strip()
    if not base:
        raise ValueError(
            "SNOWFLAKE_ACCOUNT_URL is not set. Copy .env.example to .env and set your account URL."
        )
    return (
        f"{base.rstrip('/')}/api/v2/databases/CUSTOMER_DB"
        f"/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER"
    )


def get_mcp_headers() -> dict:
    pat = os.environ.get("SNOWFLAKE_PAT", "")
    if not pat:
        raise ValueError("SNOWFLAKE_PAT environment variable is not set.")
    return {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
    }


def verify_mcp_connection() -> bool:
    url = get_mcp_server_url()
    resp = httpx.post(
        url,
        headers=get_mcp_headers(),
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        timeout=15.0,
    )
    return resp.status_code == 200


@contextmanager
def mcp_adapter(connect_timeout: int = 20) -> Generator[MCPServerAdapter, None, None]:
    adapter = MCPServerAdapter(
        {
            "url": get_mcp_server_url(),
            "transport": "streamable-http",
            "headers": get_mcp_headers(),
        },
        connect_timeout=connect_timeout,
    )
    try:
        yield adapter
    finally:
        adapter.stop()


def fetch_passenger_profile(customer_id: str, verbose: bool = False) -> str:
    """Fetch passenger profile from Snowflake via MCP — never from Iceberg."""
    from crewai import Agent, Crew, Task

    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    with mcp_adapter() as adapter:
        analyst = Agent(
            role="Airline Customer Profile Analyst",
            goal="Retrieve passenger profile data from Snowflake for IROP decisioning",
            backstory=(
                "You query Snowflake passenger profiles for airline irregular operations. "
                f"Profiles are in {PROFILE_TABLE}. Never invent data — only return query results."
            ),
            tools=adapter.tools,
            verbose=verbose,
        )
        task = Task(
            description=(
                f"Query {PROFILE_TABLE} for customer_id = '{customer_id}'. "
                "Select exactly these columns: CUSTOMER_ID, FULL_NAME, LOYALTY_TIER, "
                "LIFETIME_SPEND_USD, LIFETIME_FLIGHTS, PREFERRED_SEAT, PREFERRED_LOUNGE, "
                "PAST_DISRUPTIONS_COUNT, LAST_DISRUPTION_OUTCOME, BASE_RETENTION_PROPENSITY. "
                "Return one line per column in the form 'column_name: value' using the exact "
                "Snowflake column names. Do not invent fields."
            ),
            expected_output=(
                f"All ten columns for {customer_id}, each on its own line as "
                "'COLUMN_NAME: value'. Use exact Snowflake column names from PASSENGER_PROFILES."
            ),
            agent=analyst,
        )
        crew = Crew(agents=[analyst], tasks=[task], verbose=verbose)
        return str(crew.kickoff())
