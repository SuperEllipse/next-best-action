"""
This tool reads the latest STAGED_FOR_CONCIERGE audit record for Push-to-Concierge handoff.
Returns:
    str: staging audit record or not-found message
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
        spark = get_spark_session("ReadPushStaging", config.iceberg_jar)
        cid = sql_escape(args.customer_id)
        rows = collect_as_dicts(
            spark.sql(f"""
                SELECT * FROM {ICEBERG_NAMESPACE}.irop_execution_results
                WHERE customer_id = '{cid}' AND status = 'STAGED_FOR_CONCIERGE'
                ORDER BY executed_at DESC
                LIMIT 1
            """)
        )
        if not rows:
            return "No staging record found — Scenario A push may not have run yet."
        return f"Push staging record: {rows[0]}"


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
