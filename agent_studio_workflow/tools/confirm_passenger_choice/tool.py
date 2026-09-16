"""
This tool confirms the chosen alternate flight in Iceberg inventory and releases other holds.
Returns:
    str: updated inventory after confirmation
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
    chosen_flight: str = Field(description="Alternate flight code to confirm, e.g. EK372")
    release_flights: str = Field(default="", description="Comma-separated flight codes to release")


def run_tool(config: UserParameters, args: ToolParameters):
        spark = get_spark_session("ConfirmPassengerChoice", config.iceberg_jar)
        pnr = sql_escape(args.pnr)
        chosen = sql_escape(args.chosen_flight)
        release = tuple(f.strip() for f in args.release_flights.split(",") if f.strip()) if args.release_flights else ()
        if not release:
            all_flights = collect_as_dicts(
                spark.sql(f"SELECT * FROM {ICEBERG_NAMESPACE}.concierge_inventory_lookup WHERE pnr = '{pnr}'")
            )
            release = tuple(
                r.get("alternate_flight") for r in all_flights if r.get("alternate_flight") and r.get("alternate_flight") != args.chosen_flight
            )
        spark.sql(f"""
            UPDATE {ICEBERG_NAMESPACE}.concierge_inventory_lookup
            SET hold_status = 'CONFIRMED', inventory_status = 'CONFIRMED'
            WHERE pnr = '{pnr}' AND alternate_flight = '{chosen}'
        """)
        if release:
            release_list = ", ".join(f"'{sql_escape(f)}'" for f in release)
            spark.sql(f"""
                UPDATE {ICEBERG_NAMESPACE}.concierge_inventory_lookup
                SET hold_status = 'RELEASED'
                WHERE pnr = '{pnr}' AND alternate_flight IN ({release_list})
            """)
        updated = collect_as_dicts(
            spark.sql(f"SELECT * FROM {ICEBERG_NAMESPACE}.concierge_inventory_lookup WHERE pnr = '{pnr}'")
        )
        return f"Confirmed {args.chosen_flight}; inventory now: {updated}"


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
