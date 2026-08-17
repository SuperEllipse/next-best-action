# Airline IROP Agentic Demo

Demonstration application for Airline Irregular Operations (IROP) using **CrewAI**, **Apache Iceberg** on Cloudera Data Platform, and **Snowflake MCP** for passenger profiles.

## Architecture

- **Snowflake MCP** — sole source for passenger profiles (CUST-101, 202, 303, 404)
- **Iceberg on CDP** — operational events, chat signals, uplift history, inventory, audit log
- **CrewAI** — 3-agent pipeline: Context & Signal → Uplift & Strategy → Fulfillment & Guardrail
- **Flask dashboard** — executive view + David (CUST-404) concierge view

## Prerequisites

1. CML session with Spark add-on enabled
2. Iceberg catalog access (`spark_catalog.airline_irop`)
3. Snowflake MCP server: `CUSTOMER_DB.PROFILES.CUSTOMER_MCP_SERVER`
4. Copy `.env.example` to `.env` and fill in:
   - `OPENAI_API_KEY`
   - `SNOWFLAKE_PAT`
   - `SNOWFLAKE_ACCOUNT_URL`
   - `ICEBERG_JAR` (Spark 3.3 runtime jar path)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your keys
```

Keys are loaded automatically from `.env` when you run `run_demo.py` or the dashboard. (`.env` is gitignored.)

## Run

```bash
# 1. Quick INSERT smoke test (run this first after session restart)
python test_iceberg_insert.py
# or: python run_demo.py test-insert

# 2. Full setup (after insert test passes)
python run_demo.py setup

# Run Scenario A (Push/NBA) for CUST-101, 202, 303
python run_demo.py scenario-a

# Run Scenario B (Pull/Concierge) for David (CUST-404)
python run_demo.py scenario-b

# Launch Flask dashboard (binds to CDSW_APP_PORT on 127.0.0.1)
python run_demo.py dashboard
```

### Accessing the dashboard on Cloudera AI

Cloudera AI exposes embedded web apps via the `CDSW_APP_PORT` environment variable.
The Flask app binds to `127.0.0.1` on that port — do not use port 5000.

1. Start the dashboard from a CML session: `python run_demo.py dashboard`
2. Click the **grid icon** in the upper-right corner of the Cloudera AI UI
3. Select the embedded web app to open `/executive` or navigate to `/concierge`

See [Cloudera AI embedded web applications](https://docs.cloudera.com/machine-learning/cloud/projects/topics/ml-embedded-web-apps.html).

## Scenarios

| Scenario | Mode | Passengers | Description |
|---|---|---|---|
| A — Push (NBA) | Proactive | CUST-101, 202, 303 | System decides before passenger asks |
| B — Pull (Concierge) | Reactive | CUST-404 (David) | Passenger initiates via chat |

## Reference Files

All connection patterns come from tested samples in [`code_sample/`](code_sample/):

- [`Iceberg_PySpark_Quickstart_ADLS.ipynb`](code_sample/Iceberg_PySpark_Quickstart_ADLS.ipynb) — Spark/Iceberg session, CREATE, INSERT
- [`test_crewai_mcp.ipynb`](code_sample/test_crewai_mcp.ipynb) — Snowflake MCP adapter

## Data Placement

| Table | Platform |
|---|---|
| `passenger_profiles` | Snowflake only (MCP) |
| All other tables | Iceberg (`spark_catalog.airline_irop`) |
