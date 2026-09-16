"""
This tool re-applies HELD status on named alternate flights after a passenger change of mind.
Returns:
    str: inventory rows after re-hold
"""

import argparse
import json
import os
import sys

from pydantic import BaseModel, Field

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from spark_helpers import ICEBERG_NAMESPACE, collect_as_dicts, get_spark_session, sql_escape


class UserParameters(BaseModel):
    iceberg_jar: str = Field(
        default="",
        description="Optional override path to Iceberg Spark runtime jar",
    )


class ToolParameters(BaseModel):
    pnr: str = Field(description="Passenger PNR record locator")
    flights: str = Field(default="EK372,EK380", description="Comma-separated alternate flight codes")


def run_tool(config: UserParameters, args: ToolParameters):
        spark = get_spark_session("ReHoldAlternateFlights", config.iceberg_jar)
        pnr = sql_escape(args.pnr)
        flight_tuple = tuple(f.strip() for f in args.flights.split(",") if f.strip())
        flight_list = ", ".join(f"'{sql_escape(f)}'" for f in flight_tuple)
        spark.sql(f"""
            UPDATE {ICEBERG_NAMESPACE}.concierge_inventory_lookup
            SET hold_status = 'HELD', inventory_status = 'AVAILABLE'
            WHERE pnr = '{pnr}' AND alternate_flight IN ({flight_list})
        """)
        held = collect_as_dicts(
            spark.sql(
                f"SELECT * FROM {ICEBERG_NAMESPACE}.concierge_inventory_lookup WHERE pnr = '{pnr}' AND alternate_flight IN ({flight_list})"
            )
        )
        return f"Re-held flights {flight_tuple}: {held}"


OUTPUT_KEY = "tool_output"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True, help="JSON string for tool configuration")
    parser.add_argument("--tool-params", required=True, help="JSON string for tool arguments")
    cli = parser.parse_args()

    config_dict = json.loads(cli.user_params)
    params_dict = json.loads(cli.tool_params)

    config = UserParameters(**config_dict)
    params = ToolParameters(**params_dict)

    output = run_tool(config, params)
    print(OUTPUT_KEY, output)
