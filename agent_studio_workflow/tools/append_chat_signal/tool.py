"""
This tool writes the latest passenger chat message to Iceberg unstructured_chat_signals.
Returns:
    str: metadata for the appended chat signal
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
    pnr: str = Field(description="Passenger PNR record locator")
    message_text: str = Field(description="Passenger chat message text")
    sentiment: str = Field(default="CALM", description="Detected sentiment label")


def run_tool(config: UserParameters, args: ToolParameters):
        import datetime

        spark = get_spark_session("AppendChatSignal", config.iceberg_jar)
        cid = sql_escape(args.customer_id)
        pnr = sql_escape(args.pnr)
        sentiment = sql_escape(args.sentiment)
        message = sql_escape(args.message_text)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        signal_id = f"SIG-{now.replace(' ', '-').replace(':', '')}-{args.customer_id}"
        spark.sql(f"""
            INSERT INTO {ICEBERG_NAMESPACE}.unstructured_chat_signals VALUES
            ('{signal_id}', '{pnr}', '{cid}', cast('{now}' as timestamp),
             '{sentiment}', '{message}')
        """)
        meta = {"signal_id": signal_id, "message_text": args.message_text, "signal_timestamp": now}
        return f"Chat signal appended: {meta}"


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
