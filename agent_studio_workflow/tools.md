# Agent Studio Custom Tools
Each tool folder contains `tool.py`, `spark_helpers.py`, and `requirements.txt`.
Upload each folder to the Agent Studio **Tools Catalog**.

---

## append_chat_signal

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## confirm_passenger_choice

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## fetch_operational_context

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## log_execution_result

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## place_flight_holds

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## query_inventory

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## query_uplift_and_actions

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## re_hold_alternate_flights

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## read_prior_concierge_audit

### `tool.py`

```python
"""
This tool returns prior Scenario B fulfillment audit rows for multi-turn concierge context.
Returns:
    str: prior concierge audit decisions
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
    case_id: str = Field(default="", description="Optional case ID to scope prior decisions")


def run_tool(config: UserParameters, args: ToolParameters):
        spark = get_spark_session("ReadPriorConciergeAudit", config.iceberg_jar)
        cid = sql_escape(args.customer_id)
        where = f"customer_id = '{cid}' AND scenario = 'PULL_CONCIERGE'"
        if args.case_id:
            where += f" AND case_id = '{sql_escape(args.case_id)}'"
        rows = collect_as_dicts(
            spark.sql(f"""
                SELECT * FROM {ICEBERG_NAMESPACE}.irop_execution_results
                WHERE {where}
                ORDER BY executed_at DESC
                LIMIT 5
            """)
        )
        if not rows:
            return "No prior concierge audit rows for this passenger."
        return f"Prior concierge decisions: {rows}"


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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```

---

## read_push_staging

### `tool.py`

```python
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

```

### `requirements.txt`

```
pydantic>=2.0
pyspark>=3.5.0
```
