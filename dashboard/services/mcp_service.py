"""Snowflake MCP profile access for Flask dashboard."""

from snowflake_mcp import fetch_passenger_profile, verify_mcp_connection

DEMO_PASSENGERS = ["CUST-101", "CUST-202", "CUST-303", "CUST-404"]


def get_passenger_profile(customer_id: str) -> str:
    """Always fetch profile from Snowflake MCP — never Iceberg."""
    return fetch_passenger_profile(customer_id, verbose=False)


def check_mcp_health() -> dict:
    try:
        ok = verify_mcp_connection()
        return {"status": "ok" if ok else "error", "message": "MCP connection verified"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
