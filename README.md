# Airline IROP — Next Best Action (NBA) Agentic Demo

Demonstration of **Airline Irregular Operations (IROP)** decisioning on **Cloudera AI**, combining **CrewAI** multi-agent orchestration, **Apache Iceberg** operational data, and **Snowflake MCP** for passenger profiles.

### At a glance

| | |
|---|---|
| **What** | Proactive NBA + human-in-the-loop concierge for airline disruptions |
| **Why** | Same misconnect event — four passengers, four optimal actions (propensity vs uplift) |
| **How** | 3-agent CrewAI workflow over Iceberg + Snowflake MCP, with Flask dashboard |
| **Runtime** | ~15–20 min for `scenario-a`; `scenario-b` is a focused chat follow-up |

**Live dashboard:** deploy as a **Cloudera AI Application** (see [Run the dashboard](#run-the-dashboard-cloudera-ai-application)). Run `setup` offline in a workbench session first.

### Who should read what

| Audience | Start here |
|----------|------------|
| **Executives / business** | Problem → Complication → Solution → [Presenter talk track](#presenter-talk-track) |
| **Demo operators** | [Setup (offline)](#setup-offline--workbench-session) → [Application](#run-the-dashboard-cloudera-ai-application) → [How to run](#how-to-run-the-demo) |
| **Engineers / architects** | [Architecture](#architecture) → [Snowflake profiles](#snowflake-passenger-profiles-external) → [Project layout](#project-layout) |

---

## Problem

An inbound delay cuts connection time on a busy international hub (e.g. LHR → DXB → SIN). Passengers on the same misconnect event need different treatment:

- Some are loyal **sure things** — they will rebook regardless of a gesture.
- Some are **persuadables** — a timely offer measurably improves retention.
- Some are **sleeping dogs** — a generic voucher can backfire when they only want a fast rebook.
- **High-value, choice-oriented** travelers expect white-glove service: options held, constraints respected, and human-in-the-loop (HILT) concierge when they engage.

A one-size-fits-all rules engine cannot reconcile propensity, uplift, inventory, and passenger context in real time.

---

## Complication

| Challenge | Why it matters |
|-----------|----------------|
| **Propensity vs uplift** | High loyalty ≠ high uplift. Spending on the wrong segment wastes budget or damages trust. |
| **Structured + unstructured signals** | Operational events (delay, misconnect flag) must be combined with chat tone, silence, and stated constraints (“must land before 6 PM”). |
| **Split data estate** | Golden **passenger profiles** live in Snowflake; **operational lakehouse** tables (events, inventory, uplift history, audit) live on Cloudera in Iceberg. |
| **Push vs pull** | **NBA (push)** must decide proactively; **concierge (pull)** must fulfill when the passenger initiates — same context layer, two directions. |
| **Explainability & audit** | Executives need metrics and a reasoning trail; regulators and ops need immutable decision logs. |

---

## Solution

**Next Best Action with Human-in-the-Loop (HILT)** via an agentic workflow:

1. **scenario-a — Push / NBA (proactive)**  
   For each affected passenger, a 3-agent CrewAI crew assembles context, classifies archetype using uplift history, validates inventory, applies guardrails, and logs the outcome. High-value choice-oriented passengers receive **hold-and-prompt** instead of a blind auto-rebook.

2. **scenario-b — Pull / Concierge (reactive, HILT)**  
   David Vance (CUST-404) opens chat with constraints. The same agent stack reads prior staging, re-holds inventory, and executes his preference with a full **brain log** for explainability.

3. **Flask dashboard**  
   Executive metrics, segment profiles (Snowflake MCP), disruption context (Iceberg), scenario triggers, and rules-vs-agentic contrast.

---

## Architecture

### System integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Cloudera AI (Python 3.12)                           │
│  ┌──────────────┐    ┌─────────────────┐    ┌────────────────────────────┐  │
│  │  run_demo.py │───▶│ CrewAI 3-agent  │───▶│ Flask dashboard            │  │
│  │  scenario-a/b│   │ workflow        │    │ (CDSW_APP_PORT)            │  │
│  └──────┬───────┘    └────────┬────────┘    └────────────────────────────┘  │
│         │                     │                                             │
│         │            ┌────────┴────────┐                                    │
│         │            │  Agent tools    │                                    │
│         ▼            ▼                 ▼                                    │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────────┐ │
│  │ PySpark 3.5  │  │ Apache Iceberg — spark_catalog.airline_irop          │ │
│  │ + Iceberg    │  │ events · chat · uplift · inventory · audit           │ │
│  │ runtime jar  │  └──────────────────────────────────────────────────────┘ │
│  └──────────────┘                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │  MCP streamable-http (sql_exec_tool)
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Snowflake (external)                                                        │
│ CUSTOMER_DB.PROFILES.PASSENGER_PROFILES via CUSTOMER_MCP_SERVER             │
│ Profiles: CUST-101, CUST-202, CUST-303, CUST-404 — never copied to Iceberg  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Multi-agent workflow (sequential)

| Agent | Role | Data sources | Tools |
|-------|------|--------------|-------|
| **1 — Context & Signal** | Enrich profile + operational picture | Snowflake MCP profile (pre-fetched) + Iceberg | `fetch_operational_context` |
| **2 — Uplift & Strategy** | Archetype + action from gesture shelf | Iceberg uplift experiments | `query_uplift_and_actions` |
| **3 — Fulfillment & Guardrail** | Inventory check, execute, audit | Iceberg inventory + audit | `query_inventory`, `log_execution_result` |

### Passenger segments (demo seed data)

| Customer | Archetype | scenario-a behavior |
|----------|-----------|---------------------|
| CUST-101 | Sure Thing | Minimal / monitor — avoid wasted gestures |
| CUST-202 | Persuadable | Lounge + meal voucher |
| CUST-303 | Sleeping Dog | Proactive rebook — block voucher-only |
| CUST-404 | Choice Oriented | Hold alternates + push prompt → scenario-b chat |

### Data placement

| Data | Platform |
|------|----------|
| `PASSENGER_PROFILES` | Snowflake only (MCP) |
| `flight_operational_events`, `unstructured_chat_signals`, `action_gesture_shelf`, `historical_uplift_experiments`, `concierge_inventory_lookup`, `irop_execution_results` | Iceberg (`spark_catalog.airline_irop`) |

### Technical stack

| Component | Version / notes |
|-----------|-----------------|
| **Python** | 3.10+ (tested on **3.12**) |
| **Spark** | **3.5.4** via Cloudera AI Spark add-on (do not `pip install pyspark`) |
| **Iceberg** | Runtime jar under `/opt/spark/optional-lib/` |
| **CrewAI** | 1.15.x multi-agent orchestration |
| **Snowflake** | Hosted MCP server + Programmatic Access Token (PAT) |
| **OpenAI** | LLM for agent reasoning (`OPENAI_API_KEY`) |

---

## Snowflake passenger profiles (external)

Passenger golden records stay in Snowflake and are read at runtime via MCP. They are **not** seeded into Iceberg.

**Source of truth:** [`data/passenger_profiles_ddl.sql`](data/passenger_profiles_ddl.sql) defines the table. [`data/passenger_profiles.csv`](data/passenger_profiles.csv) uses the **same column names and order** as the DDL.

### Table columns

Matches live Snowflake `DESCRIBE TABLE` output (column order preserved):

| Column | Type | Description |
|--------|------|-------------|
| `CUSTOMER_ID` | `VARCHAR` | `CUST-101` … `CUST-404` |
| `FULL_NAME` | `VARCHAR` | Passenger display name |
| `LOYALTY_TIER` | `VARCHAR` | e.g. Platinum, Gold, Silver |
| `LIFETIME_SPEND_USD` | `FLOAT` | Lifetime spend in USD |
| `LIFETIME_FLIGHTS` | `NUMBER(38,0)` | Total flights on record |
| `PREFERRED_SEAT` | `VARCHAR` | Seat preference |
| `PREFERRED_LOUNGE` | `VARCHAR` | Preferred lounge |
| `PAST_DISRUPTIONS_COUNT` | `NUMBER(38,0)` | Historical disruption count |
| `LAST_DISRUPTION_OUTCOME` | `VARCHAR` | Last gesture outcome |
| `BASE_RETENTION_PROPENSITY` | `FLOAT` | 0.00–1.00 baseline retention score |

CSV headers use lowercase snake_case; Snowflake stores them as uppercase. The `COPY INTO` column list in the DDL maps CSV → table explicitly.

### Seed data (4 demo passengers)

Load [`data/passenger_profiles.csv`](data/passenger_profiles.csv) into Snowflake using the `COPY INTO` example in the DDL file. Archetype labels below come from Iceberg uplift seed data, not from this Snowflake table.

| customer_id | full_name | loyalty_tier | lifetime_spend_usd | Iceberg archetype |
|-------------|-----------|--------------|--------------------|-------------------|
| CUST-101 | Alexander Wright | Platinum | 145000 | Sure Thing |
| CUST-202 | Mei Lin Tan | Gold | 42000 | Persuadable |
| CUST-303 | James Okafor | Silver | 18500 | Sleeping Dog |
| CUST-404 | David Vance | Platinum | 420000 | Choice Oriented |

Expose the table through MCP server `CUSTOMER_DB.PROFILES.CUSTOMER_MCP_SERVER` with tool `sql_exec_tool`. The demo queries all ten DDL columns by name.

### MCP server requirements

| Item | Value |
|------|-------|
| Database / schema | `CUSTOMER_DB.PROFILES` |
| Table | `PASSENGER_PROFILES` |
| MCP server | `CUSTOMER_MCP_SERVER` |
| Tool | `sql_exec_tool` |
| PAT grants | `USAGE` on MCP server; `SELECT` on `PASSENGER_PROFILES` |

Endpoint pattern (set account in `.env`):

```
https://<your-account>.snowflakecomputing.com/api/v2/databases/CUSTOMER_DB/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER
```

---

## Prerequisites

1. **Cloudera AI workbench** with **Spark 3.5.4** add-on enabled.
2. **Iceberg** catalog access to `spark_catalog.airline_irop` with `ICEBERG_WAREHOUSE_URI` configured (see `.env.example`).
3. **Snowflake MCP server** deployed with the schema and seed data above.
4. **Snowflake PAT** with grants on the MCP server and profile table.
5. **OpenAI API key** for CrewAI agents.
6. Demo passengers **CUST-101, CUST-202, CUST-303, CUST-404** loaded in Snowflake.

---

## Setup (offline — workbench session)

Run these steps **once** in a Cloudera AI **workbench session** (not in the Application). Use a session with the **Spark 3.5.4** add-on enabled. Stop the session when setup completes — the dashboard runs separately as an Application.

### 1. Install Python dependencies

PySpark comes from the cluster Spark runtime — **do not** install it with pip.

```bash
pip install -r requirements.txt
```

### 2. Configure secrets (never commit `.env`)

```bash
cp .env.example .env
```

Edit `.env`:

```bash
OPENAI_API_KEY=sk-...
SNOWFLAKE_PAT=<your-programmatic-access-token>
SNOWFLAKE_ACCOUNT_URL=https://<your-account>.snowflakecomputing.com
ICEBERG_WAREHOUSE_URI=abfs://<container>@<account>.dfs.core.windows.net/<path>

# Optional — Iceberg jar (defaults to newest runtime jar on the cluster):
# ICEBERG_JAR=/opt/spark/optional-lib/iceberg-spark-runtime-3.5_2.12-*.jar
```

**PAT hygiene:** tokens expire. If you see `Failed to initialize MCP Adapter` or `Programmatic access token is expired`, rotate the PAT and restart the Application.

Verify MCP connectivity:

```bash
python3 -c "
from env_config import load_project_env
load_project_env()
from snowflake_mcp import verify_mcp_connection
print('MCP OK:', verify_mcp_connection())
"
```

### 3. Create and seed Iceberg tables

After a fresh session restart, smoke-test Iceberg writes first:

```bash
python3 run_demo.py test-insert
```

Then full setup (create tables + seed demo data; first object-store write may take 1–3 minutes):

```bash
python3 run_demo.py setup
```

### 4. (Optional) Run scenarios from the CLI

You can run agent workflows offline in the same workbench session before deploying the dashboard:

```bash
python3 run_demo.py scenario-a    # proactive NBA — all four passengers
python3 run_demo.py scenario-b    # concierge chat for CUST-404
```

---

## Run the dashboard (Cloudera AI Application)

Deploy the UI as a long-running **Application** — do not start the dashboard manually from a browser terminal for production demos.

### 1. Create the Application

In your Cloudera AI project:

1. Go to **Applications** → **New Application**
2. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `IROP NBA Demo` (or your choice) |
| **Command** | `python3 run_demo.py` (defaults to dashboard; `dashboard` is optional) |
| **Runtime** | Python 3.12 with **Spark 3.5.4** add-on |
| **Environment variables** | Same keys as `.env` (`OPENAI_API_KEY`, `SNOWFLAKE_PAT`, `SNOWFLAKE_ACCOUNT_URL`, `ICEBERG_WAREHOUSE_URI`, optional `ICEBERG_JAR`) |

3. **Start** the Application and wait until the status is **Running**

Cloudera AI sets `CDSW_APP_PORT` automatically and exposes the Flask app on `127.0.0.1` within the Application pod.

### 2. Open the dashboard

1. Click the Application name in the **Applications** list
2. Open the **Application URL** (or use the link icon) provided by Cloudera AI
3. You should see the Overview page; use the tabs for executive metrics, segments, `scenario-a`, and `scenario-b`

See [Cloudera AI Applications](https://docs.cloudera.com/machine-learning/cloud/projects/topics/ml-applications.html) and [embedded web applications](https://docs.cloudera.com/machine-learning/cloud/projects/topics/ml-embedded-web-apps.html).

### 3. Re-run setup after environment changes

If you recreate Iceberg tables, re-seed data, or rotate secrets, stop the Application, run `python3 run_demo.py setup` (or `seed`) in a workbench session, then restart the Application.

---

## Presenter talk track

A ~15-minute live narrative that works for mixed business and technical audiences.

| Minute | Tab / action | Talking points |
|--------|--------------|----------------|
| 0–2 | **Overview** | One disruption event, four passengers — why a rules engine fails (propensity ≠ uplift) |
| 2–4 | **Executive Dashboard** | Metrics come from Iceberg audit log — every agent decision is logged |
| 4–6 | **Missed Connection Segments** | Left: operational context (Iceberg). Right: golden profiles (Snowflake MCP) — split estate, unified decision |
| 6–12 | **scenario-a** | Run proactive NBA. Call out per-passenger outcome: monitor, gesture, rebook, hold-and-prompt |
| 12–15 | **scenario-b** | David (CUST-404) chats with constraints. Same agents, HILT execution, brain log explains *why* |
| 15+ | **Rules vs Agentic** | Close with contrast — rigid rules miss nuance; agentic respects constraints + inventory |

**Tip for executives:** lead with the *business outcome* (right passenger, right gesture, audit trail). **Tip for engineers:** pause on the brain log and mention the three agents, two data platforms, one workflow.

---

## How to run the demo

**Prerequisite:** complete [offline setup](#setup-offline--workbench-session) and deploy the [Cloudera AI Application](#run-the-dashboard-cloudera-ai-application) before presenting.

### Recommended presentation order

| Step | Action | What the audience sees |
|------|--------|------------------------|
| 1 | Open the **Application URL** | Overview — architecture and demo flow |
| 2 | **Executive Dashboard** tab | Historical metrics from Iceberg audit log |
| 3 | **Missed Connection Segments** tab | Disruption events + Snowflake profiles via MCP |
| 4 | **Run scenario-a** in the UI (or CLI) | Proactive NBA for all four passengers |
| 5 | **scenario-b — Concierge** tab | David (CUST-404) multi-turn chat + brain log |
| 6 | **Rules vs Agentic** tab | Contrast rigid rules vs agentic outcome |

### CLI reference (workbench session)

Use these in a workbench session for setup and optional offline runs. The dashboard itself is started by the Application (`python3 run_demo.py`).

```bash
python3 run_demo.py test-insert   # Iceberg INSERT smoke test (setup)
python3 run_demo.py setup         # create tables + seed data (setup — run offline first)
python3 run_demo.py seed          # re-seed only
python3 run_demo.py scenario-a    # Push / NBA (proactive)
python3 run_demo.py scenario-b    # Pull / Concierge (CUST-404, HILT)
python3 run_demo.py scenarios     # both scenario-a and scenario-b
python3 run_demo.py scenario-a -q # quieter CrewAI logs
```

> **Note:** `python3 run_demo.py` is the Application entrypoint (runs the dashboard by default) — configure it in **Applications → Command**, not in an interactive session terminal.

---

## Project layout

| Path | Purpose |
|------|---------|
| `run_demo.py` | CLI orchestrator |
| `crewai_agentic_workflow.py` | 3-agent CrewAI pipeline |
| `snowflake_mcp.py` | Snowflake MCP adapter (streamable-http) |
| `iceberg_tools.py` | PySpark/Iceberg tool implementations |
| `spark_session.py` | Spark + Iceberg session config |
| `scenarios.py` | scenario-a (push) and scenario-b (concierge) entry points |
| `data/` | Snowflake profile DDL + CSV seed data |
| `dashboard/` | Flask UI |
| `code_sample/` | Reference notebooks (Iceberg quickstart, MCP test) |
| `agent_studio_workflow/` | Optional Agent Studio port + Snowflake MCP runbooks |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `No module named 'pyspark'` | Spark add-on not enabled | Restart session with Spark **3.5.4** runtime |
| `ICEBERG_WAREHOUSE_URI is not set` | Missing lakehouse path | Set in `.env` (see `.env.example`) |
| MCP init timeout (20s) | Expired/invalid PAT or wrong account URL | Rotate PAT; check `SNOWFLAKE_ACCOUNT_URL` |
| `Programmatic access token is expired` | PAT TTL elapsed | Generate new PAT in Snowflake |
| Spend shows `$NaN` in UI | Comma-formatted spend from MCP | Hard refresh after `dashboard/static/js/app.js` fix |
| Empty segment panels | MCP or missing seed data | Run `setup`; verify MCP with snippet above |
| Iceberg jar not found | Wrong path on cluster | Set `ICEBERG_JAR` in `.env` |

---

## Security

- **Never commit** `.env`, PATs, API keys, or account-specific URLs.
- Use `.env.example` as a template with placeholders only.
- Passenger profiles are read from Snowflake at runtime; they are not stored in Iceberg or git.

---

## Reference

- [`data/passenger_profiles_ddl.sql`](data/passenger_profiles_ddl.sql) — Snowflake table DDL
- [`data/passenger_profiles.csv`](data/passenger_profiles.csv) — four demo passenger rows
- [`code_sample/Iceberg_PySpark_Quickstart_ADLS.ipynb`](code_sample/Iceberg_PySpark_Quickstart_ADLS.ipynb) — Spark/Iceberg session patterns
- [`code_sample/test_crewai_mcp.ipynb`](code_sample/test_crewai_mcp.ipynb) — Snowflake MCP adapter
