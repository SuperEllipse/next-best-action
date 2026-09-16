"""
This tool places HELD status on pre-identified alternate flights for a passenger PNR in Iceberg inventory.
Returns:
    str: updated inventory rows after holds are placed
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


def run_tool(config: UserParameters, args: ToolParameters):
        spark = get_spark_session("PlaceFlightHolds", config.iceberg_jar)
        pnr = sql_escape(args.pnr)
        flights = ("EK372", "EK380")
        flight_list = ", ".join(f"'{f}'" for f in flights)
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
        return f"Inventory holds placed: {held}"


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
