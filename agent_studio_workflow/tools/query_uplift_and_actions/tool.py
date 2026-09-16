"""
This tool retrieves historical uplift experiments and the gesture action shelf from Iceberg.
Returns:
    str: uplift history and available actions for the customer
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
        spark = get_spark_session("QueryUpliftActions", config.iceberg_jar)
        cid = sql_escape(args.customer_id)
        uplift = collect_as_dicts(
            spark.sql(f"SELECT * FROM {ICEBERG_NAMESPACE}.historical_uplift_experiments WHERE customer_id = '{cid}'")
        )
        actions = collect_as_dicts(spark.sql(f"SELECT * FROM {ICEBERG_NAMESPACE}.action_gesture_shelf"))
        return f"Uplift History: {uplift}\nAction Shelf: {actions}"


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
