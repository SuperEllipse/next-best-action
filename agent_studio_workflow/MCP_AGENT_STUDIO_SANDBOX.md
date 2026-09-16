# Agent Studio Sandbox vs MCP — Why Workbench CLI Works But UI Hangs

## The sandbox (custom tools)

Per [Cloudera Tool Execution](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-tool-execution.html), custom tools run in a **sandbox** with:

| Path | Role |
|------|------|
| `/workspace` | Writable artifact directory (CWD); `SESSION_DIRECTORY` |
| `/workflow_data` | **Read-only** mount of your CML project files; `WORKFLOW_DATA_DIRECTORY` |

Tools cannot read arbitrary host paths like `/home/cdsw/...` unless those files are part of the project and exposed under `/workflow_data`.

## MCP execution (different, but related)

Per [Cloudera MCP integration guide](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-mcp-integration-guide.html):

- MCP servers run as **local stdio processes** spawned via **`uvx`** (Python) or **`npx`** (Node.js).
- Agent Studio uses these runtimes to **download and isolate** MCP packages — it does **not** rely on your workbench shell installs.
- Only **stdio** transport is supported in Agent Studio (not direct HTTP registration).

So MCP is **not** identical to custom-tool sandboxing, but the same principle applies: **paths and binaries you use in the workbench terminal are not automatically available when Agent Studio spawns MCP.**

## Why our uvx bridge worked in CLI but hung in Agent Studio

| Config element | Workbench `verify_bridge.sh` | Likely Agent Studio runtime |
|----------------|------------------------------|----------------------------|
| Bridge path | `/home/cdsw/agent_studio_workflow/mcp_bridge` | **Not visible** unless under `/workflow_data/...` |
| `uvx` | `/home/cdsw/.local/bin/uvx` on PATH | May be missing or cold-downloading in isolated env |
| Package source | `--from` local path | uvx expects PyPI packages (see DuckDuckGo example in [register MCP docs](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-register-mcp-server.html)) |

Workbench verification passes because it runs in **your session** with full filesystem and PATH. Agent Studio MCP init times out when the subprocess cannot resolve the local `--from` path or start `uvx` quickly enough.

---

## Recommended options (in order)

### Option A — `mcp-remote` via `npx` (best for hosted Snowflake MCP)

Uses [mcp-remote](https://www.npmjs.com/package/mcp-remote) to proxy stdio ↔ Snowflake **streamable-http** with PAT headers. No local bridge files required.

**Registration JSON:** `mcp_snowflake_agent_studio_mcp_remote.json`

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
        "SNOWFLAKE_AUTH": "Bearer dummy"
      }
    }
  }
}
```

**At workflow attach:** set `SNOWFLAKE_AUTH` to `Bearer <your-real-PAT>` (include the `Bearer ` prefix).

Notes:
- `--transport http-first` matches Snowflake streamable-http (same as CrewAI `snowflake_mcp.py`).
- No OAuth flow — PAT is passed via custom headers (supported by mcp-remote).
- Tool name remains **`sql_exec_tool`** with argument `{"sql": "..."}`.

### Option B — uvx bridge via `/workflow_data` (pre-built wheel)

`/workflow_data` is **read-only** at runtime. `uvx --from` a source directory **fails** there because setuptools tries to write `*.egg-info` into the source tree.

**Workaround:** ship a pre-built wheel (read-only is fine) and point `--from` at the `.whl` file. uv installs deps into its cache under `/workspace`.

**Registration JSON:** `mcp_snowflake_agent_studio_workflow_data.json`

```json
{
  "mcpServers": {
    "Snowflake IROP Profiles MCP": {
      "command": "uvx",
      "args": [
        "--from",
        "/workflow_data/agent_studio_workflow/mcp_bridge/dist/irop_snowflake_mcp_bridge-0.3.0-py3-none-any.whl",
        "irop-snowflake-mcp-bridge"
      ],
      "env": {
        "UV_CACHE_DIR": "/workspace/.uv-cache",
        "TMPDIR": "/workspace",
        "UV_LINK_MODE": "copy",
        "UV_NO_PROGRESS": "1",
        "SNOWFLAKE_PAT": "dummy",
        "SNOWFLAKE_ACCOUNT_URL": "https://<your-account>.snowflakecomputing.com"
      }
    }
  }
}
```

Rebuild wheel after bridge changes:
```bash
cd /home/cdsw/agent_studio_workflow/mcp_bridge && uv build -o dist
```

Requires `agent_studio_workflow/mcp_bridge/dist/*.whl` in your CML project (included in `/workflow_data`).

### Option C — Custom tool (no MCP registration)

Use `tools/fetch_passenger_profile/` — direct HTTP to Snowflake MCP endpoint. Same data as CrewAI demo, no uvx/npx dependency. Best fallback if MCP registration keeps failing.

---

## What to try next

1. **Delete** existing MCP registration in Agent Studio.
2. Register with **`mcp_snowflake_agent_studio_mcp_remote.json`** (Option A).
3. Attach to workflow with real `SNOWFLAKE_AUTH=Bearer <PAT>`.
4. Run smoke test; confirm `sql_exec_tool` in trace.

If Option A fails (e.g. npx unavailable in your Agent Studio image), try Option B, then Option C.

## Workbench-only verification (does not prove Agent Studio)

```bash
bash /home/cdsw/agent_studio_workflow/mcp_bridge/verify_bridge.sh
```

This validates Snowflake + bridge logic in your shell — **not** the Agent Studio MCP spawn environment.
