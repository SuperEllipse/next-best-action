# MCP Failure: bwrap Permission Denied (Azure Workbench)

## Symptom (from Agent Studio logs)

```
Using Bubblewrap sandbox (LGPL 2.0+) for secure MCP server execution
Created sandboxed MCP server command: npx (sandboxed, runtime: Node.js)
bwrap: Failed to make / slave: Permission denied
ERROR - Error updating MCP tools for MCP ...: unhandled errors in a TaskGroup
```

MCP never starts — **not** a Snowflake, mcp-remote, or JSON config issue.

## Root cause

Agent Studio wraps **all MCP servers** (both `npx` and `uvx`) in **Bubblewrap** for isolation. On **Azure CML workbenches**, Linux mount namespaces are restricted, so bwrap fails before `npx` or `uvx` runs.

This is a documented Cloudera known issue: **DSE-50025** — [AI Studios Known Issues](https://docs.cloudera.com/machine-learning/cloud/ai-studios-release-notes/topics/ml-ai-studios-known-issues.html).

## Fix 1 — Enable insecure tool execution (Cloudera workaround)

Allows MCP and tools to run **without** bwrap sandbox.

1. Open your project in Cloudera AI Workbench.
2. **Project Settings → Advanced → Environment Variables**
3. Add:
   - **Name:** `ALLOW_AGENT_STUDIO_INSECURE_TOOL_EXECUTION`
   - **Value:** `true`
4. **Submit** and **restart the Agent Studio application**.

Then re-register MCP (Option A JSON) and retry the smoke test.

**Warning:** Tools and MCP run in the app runtime without sandbox isolation. Use only in trusted dev/demo environments.

To disable later: set to `false` and restart Agent Studio.

## Fix 2 — Custom tool (no MCP at all)

If you cannot enable insecure mode, use **`tools/fetch_passenger_profile/`** on Agent 1:

- Direct HTTP to Snowflake hosted MCP endpoint (same as CrewAI demo)
- No bwrap MCP subprocess
- Upload tool in Tools Catalog; pass `SNOWFLAKE_PAT` in tool User Parameters

## After Fix 1 succeeds

Re-use Option A registration: `mcp_snowflake_agent_studio_mcp_remote.json`

Workflow MCP env: `SNOWFLAKE_AUTH=Bearer <real-PAT>`
