"""
This tool writes the agent decision and explanation to the Iceberg irop_execution_results audit table.
Returns:
    str: confirmation with exec_id and case_id
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
    customer_id: str = Field(description="Customer ID - unique passenger identifier")
    scenario: str = Field(description="Scenario code, e.g. PUSH_NBA or PULL_CONCIERGE")
    action: str = Field(description="Action code taken, e.g. HOLD_AND_PROMPT")
    reasoning: str = Field(description="JSON or text reasoning for the decision")
    status: str = Field(description="Execution status, e.g. SUCCESS or STAGED_FOR_CONCIERGE")
    case_id: str = Field(default="", description="Optional case ID; generated if blank")


def run_tool(config: UserParameters, args: ToolParameters):
        import datetime

        spark = get_spark_session("LogExecutionResult", config.iceberg_jar)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exec_id = f"EXEC-{now.replace(' ', '-').replace(':', '')}-{args.customer_id}"
        cid = sql_escape(args.case_id) if args.case_id else f"CASE-{args.customer_id}-{now.replace(' ', '').replace(':', '')}"
        pnr = sql_escape(args.pnr)
        customer_id = sql_escape(args.customer_id)
        scenario = sql_escape(args.scenario)
        action = sql_escape(args.action)
        reasoning = sql_escape(args.reasoning)
        status = sql_escape(args.status)
        spark.sql(f"""
            INSERT INTO {ICEBERG_NAMESPACE}.irop_execution_results VALUES
            ('{exec_id}', '{cid}', '{pnr}', '{customer_id}', '{scenario}', '{action}',
             '{reasoning}', '{status}', true, cast('{now}' as timestamp))
        """)
        return f"Logged execution {exec_id} (case {cid}) to Iceberg audit table."


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
