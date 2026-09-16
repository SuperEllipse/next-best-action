"""
This tool retrieves flight disruption events and unstructured chat signals from Iceberg for a passenger.
Returns:
    str: operational events and chat signals for the customer
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
    customer_id: str = Field(description="Customer ID - unique passenger identifier")


def run_tool(config: UserParameters, args: ToolParameters):
        spark = get_spark_session("FetchOperationalContext", config.iceberg_jar)
        cid = sql_escape(args.customer_id)
        events = collect_as_dicts(
            spark.sql(f"SELECT * FROM {ICEBERG_NAMESPACE}.flight_operational_events WHERE customer_id = '{cid}'")
        )
        signals = collect_as_dicts(
            spark.sql(f"SELECT * FROM {ICEBERG_NAMESPACE}.unstructured_chat_signals WHERE customer_id = '{cid}'")
        )
        return f"Operational Events: {events}\nChat Signals: {signals}"


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
