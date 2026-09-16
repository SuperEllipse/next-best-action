"""
This tool queries alternate flights, seats, lounge and quiet-pod availability from Iceberg inventory.
Returns:
    str: inventory options for the PNR
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
        spark = get_spark_session("QueryInventory", config.iceberg_jar)
        pnr = sql_escape(args.pnr)
        inventory = collect_as_dicts(
            spark.sql(
                f"SELECT * FROM {ICEBERG_NAMESPACE}.concierge_inventory_lookup WHERE pnr = '{pnr}' ORDER BY departure_time"
            )
        )
        return f"Inventory Options Available: {inventory}"


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
