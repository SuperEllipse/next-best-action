# Option A — Snowflake MCP via mcp-remote (npx)

Use this configuration in Agent Studio. It connects stdio MCP to Snowflake's **hosted** MCP server over streamable-http with a PAT — same endpoint as the working CrewAI demo (`snowflake_mcp.py`), no local uvx bridge or project files required.

References:
- [mcp-remote on npm](https://www.npmjs.com/package/mcp-remote)
- [Cloudera MCP registration](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-register-mcp-server.html)
- [Agent Studio sandbox](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-tool-execution.html) — npm cache uses writable `/workspace`

---

## Step 1 — Delete old MCP registration

Remove any previous **Snowflake IROP Profiles MCP** registration (uvx bridge variants).

---

## Step 2 — Register MCP (paste JSON)

File: `mcp_snowflake_agent_studio_mcp_remote.json`

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

| Field | Registration value |
|-------|-------------------|
| `SNOWFLAKE_AUTH` | `Bearer dummy` (placeholder only) |
| `NPM_CONFIG_CACHE` | Writable cache in sandbox |
| `--silent` | Keeps stdout clean for MCP stdio protocol |

Tool discovery warning in Agent Studio is OK if the workflow run succeeds.

---

## Step 3 — Attach MCP to workflow

When adding the MCP instance to your workflow, set:

| Variable | Value |
|----------|-------|
| `SNOWFLAKE_AUTH` | `Bearer <your-real-PAT>` |
| `NPM_CONFIG_CACHE` | `/workspace/.npm-cache` (same as registration) |
| `TMPDIR` | `/workspace` |

Copy the PAT from project `.env` (`SNOWFLAKE_PAT`) but prefix with `Bearer ` in `SNOWFLAKE_AUTH`.

Example: if PAT is `eyJ...`, then  
`SNOWFLAKE_AUTH=Bearer eyJ...`

---

## Step 4 — Smoke test

Kickoff JSON:

```json
{
  "customer_id": "CUST-404"
}
```

Task prompt must call **`sql_exec_tool`** with:

```json
{"sql": "SELECT * FROM CUSTOMER_DB.PROFILES.PASSENGER_PROFILES WHERE customer_id = 'CUST-404'"}
```

Success: trace shows `sql_exec_tool` and profile fields for CUST-404.

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| **`bwrap: Failed to make / slave: Permission denied`** in Agent Studio logs | **Platform issue (Azure).** Not your MCP JSON. Set project env `ALLOW_AGENT_STUDIO_INSECURE_TOOL_EXECUTION=true` and restart Agent Studio. See `MCP_BWRAP_WORKAROUND.md` and [Cloudera DSE-50025](https://docs.cloudera.com/machine-learning/cloud/ai-studios-release-notes/topics/ml-ai-studios-known-issues.html). |
| MCP init timeout | Often the same bwrap failure; check logs for `bwrap` before changing JSON |
| 401 / auth error | Re-enter `SNOWFLAKE_AUTH` on **workflow** MCP config with `Bearer ` prefix |
| Agent skips MCP | Task must name `sql_exec_tool` explicitly |
| Still failing after bwrap fix | Use custom tool `tools/fetch_passenger_profile/` (direct HTTP, no MCP) |

---

## Why Option A vs uvx bridge

| | uvx bridge (Option B) | mcp-remote (Option A) |
|--|----------------------|------------------------|
| Project files | Wheel in `/workflow_data` | None |
| Runtime | `uvx` + local package | `npx` + npm download |
| Snowflake connection | Bridge forwards HTTP | Direct to hosted MCP URL |
| Matches CrewAI | Yes (same tool/endpoint) | Yes |
