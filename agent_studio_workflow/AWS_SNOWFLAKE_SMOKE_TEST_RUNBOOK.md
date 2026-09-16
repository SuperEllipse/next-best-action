# Snowflake MCP Smoke Test — Complete AWS Agent Studio Runbook

Use this on an **AWS-based** Cloudera AI Agent Studio workbench to validate Snowflake profile lookup before the full 3-agent IROP workflow.

Two approaches:
- **Plan A (preferred on AWS):** MCP via [mcp-remote](https://www.npmjs.com/package/mcp-remote) + `npx`
- **Plan B (fallback):** Custom tool `fetch_passenger_profile` — direct HTTP, no MCP subprocess

---

## Prerequisites

| Item | Value |
|------|-------|
| Snowflake account URL | `https://<your-account>.snowflakecomputing.com` |
| Snowflake MCP server | `CUSTOMER_DB.PROFILES.CUSTOMER_MCP_SERVER` |
| MCP tool name | `sql_exec_tool` |
| MCP tool argument | `{"sql": "SELECT ..."}` |
| Profile table | `CUSTOMER_DB.PROFILES.PASSENGER_PROFILES` |
| Test customer | `CUST-404` (David Vance, PLATINUM) |
| LLM | Your registered model in Agent Studio (e.g. `gpt-4o-mini`) |

**PAT grants:** role used by PAT needs `USAGE` on the MCP server and `SELECT` on `PASSENGER_PROFILES`.

**Project files:** Ensure `agent_studio_workflow/` is in your CML project (for Plan B custom tool upload).

---

## Part 1 — Register MCP (Plan A)

### 1.1 Open MCP registration

1. Cloudera AI → your **AWS workbench** → **AI Studios** → **Agent Studio**
2. **Tools Catalog** → **MCP Servers** tab → **Register**
3. Paste the JSON below

### 1.2 Registration JSON (dummy auth at registration)

Per [Cloudera MCP registration](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-register-mcp-server.html), use placeholder secrets at registration; real values go on the **workflow** MCP instance.

```json
{
  "mcpServers": {
    "Snowflake IROP Profiles MCP": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://<your-account>.snowflakecomputing.com/api/v2/databases/CUSTOMER_DB/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER",
        "--transport",
        "http-first",
        "--header",
        "Authorization:${SNOWFLAKE_AUTH}",
        "--header",
        "X-Snowflake-Authorization-Token-Type:PROGRAMMATIC_ACCESS_TOKEN",
        "--silent"
      ],
      "env": {
        "SNOWFLAKE_AUTH": "Bearer dummy",
        "NPM_CONFIG_CACHE": "/workspace/.npm-cache",
        "TMPDIR": "/workspace"
      }
    }
  }
}
```

**Notes:**
- `--transport http-first` — matches Snowflake streamable-http (same as CrewAI demo)
- `--silent` — keeps stdout clean for MCP stdio protocol
- Tool discovery warning at registration is **OK** if workflow run succeeds

### 1.3 Check registration logs (AWS)

After registering, check Agent Studio logs. **Success** looks like:
```
Created sandboxed MCP server command: npx (sandboxed, runtime: Node.js)
```
with **no** `bwrap: Failed to make / slave: Permission denied`.

If bwrap fails on AWS too, skip to **Part 4 — Plan B** (custom tool).

---

## Part 2 — Create workflow

| Setting | Value |
|---------|-------|
| **Workflow name** | `Snowflake MCP Smoke Test` |
| **Description** | Single-agent test of sql_exec_tool via mcp-remote → Snowflake hosted MCP |
| **Process** | Sequential |
| **Conversational** | No |
| **LLM** | Your registered model |

---

## Part 3 — Attach MCP to workflow (real credentials)

In the workflow editor, add MCP instance → **Snowflake IROP Profiles MCP** → assign to the agent below.

**Workflow MCP environment variables (real values):**

| Variable | Value |
|----------|-------|
| `SNOWFLAKE_AUTH` | `Bearer <your-real-PAT>` |
| `NPM_CONFIG_CACHE` | `/workspace/.npm-cache` |
| `TMPDIR` | `/workspace` |

Example: if PAT is `eyJraWQiOi...`, set  
`SNOWFLAKE_AUTH=Bearer eyJraWQiOi...`

Do **not** use `dummy` on the workflow instance.

---

## Part 4 — Agent (Plan A — MCP)

Create **one agent** with these fields:

| Field | Paste this |
|-------|------------|
| **Role** | `Snowflake Profile Test Agent` |
| **Goal** | Verify Snowflake MCP connectivity by retrieving one passenger profile row from CUSTOMER_DB.PROFILES.PASSENGER_PROFILES |
| **Backstory** | You are a Snowflake MCP integration tester for airline IROP demos. You must call the MCP tool sql_exec_tool only. Never invent passenger data — return only what the SQL query returns. If the tool fails, report the exact error. |
| **Custom tools** | None |
| **MCP** | Attach **Snowflake IROP Profiles MCP** to this agent. Enable **sql_exec_tool** if the UI lists it; if not, the task prompt names the tool explicitly. |

---

## Part 5 — Task (Plan A — MCP)

Create **one task**:

| Field | Value |
|-------|-------|
| **Assigned agent** | Snowflake Profile Test Agent |
| **Task name** | `Query passenger profile via MCP` |

**Task description** (paste exactly):

```
Smoke test for Snowflake MCP via mcp-remote (hosted CUSTOMER_MCP_SERVER).

Use the Snowflake MCP tool sql_exec_tool to run this SQL exactly:

SELECT * FROM CUSTOMER_DB.PROFILES.PASSENGER_PROFILES
WHERE customer_id = '{customer_id}';

Replace {customer_id} with the kickoff input value.
Return the full query result as JSON or text.
If the query fails, report the error message from the tool.
Do not use any other tools or invent profile fields.
```

**Expected output** (paste exactly):

```
The raw SQL result for the requested customer_id, or a clear error if MCP/Snowflake failed.
Must include at least: customer_id, loyalty tier, and baseline retention propensity if present in the row.
Do not hallucinate values not returned by sql_exec_tool.
```

---

## Part 6 — Kickoff input

| Parameter | Type | Example |
|-----------|------|---------|
| `customer_id` | string | `CUST-404` |

---

## Part 7 — Run test

1. Open workflow **Test** panel in Agent Studio (not Flask dashboard).
2. Paste kickoff JSON:

```json
{
  "customer_id": "CUST-404"
}
```

3. Run workflow.
4. Open execution trace / monitoring.

### Success criteria (Plan A)

| Check | Pass |
|-------|------|
| Workflow completes | Yes |
| Trace shows **`sql_exec_tool`** invocation | Yes |
| Output mentions **`CUST-404`** and profile attributes | Yes |
| No auth errors | Yes |

### Optional validation

Rerun with `"customer_id": "CUST-101"` — should return a different profile (proves live Snowflake, not hardcoded).

---

## Part 8 — Plan B: Custom tool (if MCP still fails)

Use this if MCP registration or execution fails (bwrap, npx, timeout, etc.). Same Snowflake endpoint as CrewAI — **no MCP registration required**.

### 8.1 Upload custom tool

1. **Tools Catalog** → **Custom Tools** → upload folder:  
   `agent_studio_workflow/tools/fetch_passenger_profile/`
2. Tool contains: `tool.py`, `requirements.txt`

### 8.2 Tool user parameters (on workflow)

| Parameter | Value |
|-----------|-------|
| `snowflake_pat` | Your real PAT |
| `snowflake_account_url` | `https://<your-account>.snowflakecomputing.com` |

### 8.3 Agent (Plan B)

| Field | Paste this |
|-------|------------|
| **Role** | `Snowflake Profile Test Agent` |
| **Goal** | Retrieve one passenger profile row from Snowflake for the given customer_id |
| **Backstory** | You fetch passenger profiles for IROP testing. Use the fetch_passenger_profile tool only. Never invent data. |
| **Custom tools** | **fetch_passenger_profile** |
| **MCP** | None |

### 8.4 Task (Plan B)

**Task description:**

```
Smoke test for Snowflake profile lookup (custom tool, no MCP).

Use the fetch_passenger_profile tool with customer_id from kickoff input '{customer_id}'.

Return the full tool output. If the tool fails, report the error.
Do not invent profile fields.
```

**Expected output:**

```
Raw profile JSON/text for the customer_id including loyalty tier and retention propensity if present,
or a clear error from the tool.
```

Same kickoff: `{"customer_id": "CUST-404"}`

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `bwrap: Failed to make / slave: Permission denied` | Platform sandbox issue. On Azure see `MCP_BWRAP_WORKAROUND.md`. On AWS, try Plan B or contact Cloudera admin. |
| MCP init timeout | Check logs for bwrap/npx errors first |
| 401 / 403 from Snowflake | Fix PAT grants; confirm `SNOWFLAKE_AUTH=Bearer <PAT>` on **workflow** MCP |
| Agent does not call MCP | Task must name `sql_exec_tool`; MCP attached to agent |
| Tool discovery warning only | Ignore if workflow run succeeds |
| `Workflow deployment ... not found` | Normal until you deploy; Test panel still works |

---

## After smoke test passes

Proceed to the full IROP Agent Studio workflow (3 agents, Iceberg custom tools + Snowflake on Agent 1). Use the same MCP registration (Plan A) or custom tool (Plan B) on the profile enrichment agent.

---

## Quick reference — Snowflake MCP endpoint

```
POST https://<your-account>.snowflakecomputing.com/api/v2/databases/CUSTOMER_DB/schemas/PROFILES/mcp-servers/CUSTOMER_MCP_SERVER

Headers:
  Authorization: Bearer <PAT>
  Content-Type: application/json
  X-Snowflake-Authorization-Token-Type: PROGRAMMATIC_ACCESS_TOKEN

tools/call body:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "sql_exec_tool",
    "arguments": {
      "sql": "SELECT * FROM CUSTOMER_DB.PROFILES.PASSENGER_PROFILES WHERE customer_id = 'CUST-404'"
    }
  }
}
```

This is the same call path used by CrewAI (`snowflake_mcp.py`), mcp-remote (Plan A), and `fetch_passenger_profile` (Plan B).
