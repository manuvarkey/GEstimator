# Local MCP server

The MCP ribbon leaves the active Schedule, Analysis, Resources or Measurements editor in place. Start/Stop controls the listener; Configure server opens its settings dialog. The server starts stopped unless automatic startup was explicitly saved.

## Connect a client

1. Open **MCP → Configure server**, choose a port (1024–65535; default 8765), and save settings. Automatic startup is optional. Stop the server before changing settings or rotating its token.
2. Start the server from the dialog or ribbon. Open a project in GEstimator to make its schedule, resources and measurements available.
3. Use **Copy client configuration** to copy a JSON `mcpServers.gestimator` entry with the endpoint URL and `Authorization: Bearer …` header. The client must support Streamable HTTP and custom authorization headers. Adapt the JSON to its configuration format if needed. **Show token** also reveals selectable configuration text when clipboard access is unavailable.

The listener binds only to `127.0.0.1`, at `http://127.0.0.1:<port>/mcp`. A generated connection token is required for all requests; valid local Host/Origin headers are enforced. Rotating the token invalidates old client configuration. The port, token and automatic-start preference are saved in this installation's local application preferences. The token grants read access to the currently open project, so keep copied client configuration private.

## Tools and data

| Tool | Result |
|---|---|
| `get_project` | Current project name, revision and unsaved-state flags; works without a project. |
| `list_schedule` | Searchable schedule hierarchy with stored rates and quantities; `query` and `offset`, 100 items per page. |
| `list_resources` | Searchable resource hierarchy with base rates, VAT and discounts; `query` and `offset`, 100 items per page. |
| `get_analysis` | Active analysis and draft, including Python-calculated amounts; preserves the selected analysis. |
| `list_measurements` | Measurement descriptions and totals; `offset`, 100 items per page. |
| `get_measurement` | One item's template, links, raw expressions, original rendered values/Breakup and totals; required `id`, optional `record_offset`, 100 records per page. |
| `list_databases` | Attached read-only database snapshots. |

Only these read tools are exposed. MCP cannot open arbitrary files, run application commands, mutate estimates, save projects or stop/configure its own listener. Switching/opening projects in the application changes the data clients see on their next request. Active draft data is explicitly included in `get_analysis`.

The HTTP handlers queue tools onto the same owner thread as desktop requests, including all SQLite/ORM access. They reuse the existing Python service, template callbacks and calculation engine. There is no second database or calculation implementation. The bounded request queue rejects excess work; pending read requests time out. Existing measurement loading still parses the legacy measurement JSON before paging the returned records/items.

## Lifecycle and protocol

Closing the settings dialog keeps the server running. Stop releases its port; Start can reuse it. An occupied port produces a visible error and leaves the server stopped. The app owns the listener, so application/backend shutdown releases it. Automatic startup restores the saved port/token and reports conflicts rather than choosing another port. Request count and last method/tool appear in settings; headers, token and project data are not logged.

The implementation supports the [MCP 2025-11-25 Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) and [tool discovery/calls](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), with JSON responses. It negotiates 2025-11-25, 2025-06-18 or 2025-03-26 on `initialize`. Clients POST individual JSON-RPC messages to `/mcp`, with `Accept: application/json, text/event-stream` and `Content-Type: application/json`. Subsequent requests may specify the negotiated `MCP-Protocol-Version`. Notifications receive HTTP 202. The server is stateless and does not allocate session IDs or provide an unsolicited SSE stream (GET returns 405). It does not implement the newer protocol revision, OAuth discovery, remote access or standalone stdio hosting.

Transport tests exercise initialization, discovery, calls, notifications, invalid requests, authentication, Host/Origin restrictions, parallel desktop/HTTP reads, live project and measurement results, rejected write attempts, configuration validation, port conflicts, stop/restart, token rotation and shutdown. Browser coverage uses the real Python process and HTTP listener, including saved automatic startup and preserved editor/draft state. Target-platform WebView behavior and third-party client setup remain integration checks.
