# Local MCP server

The MCP ribbon keeps the active editor in place. Configure server controls port (1024–65535, default 8765), **Read only / Read and write**, optional automatic startup and token rotation. Save configuration before Start. Stop before changing configuration. Existing saved settings retain read-only access until the user changes it.

**Copy client configuration** copies an `mcpServers.gestimator` JSON entry containing the Streamable HTTP URL and Bearer header. Clients must support HTTP/custom authorization headers; adapt the entry to the client's config format. Show token reveals selectable configuration text if clipboard access is unavailable. The listener binds to `127.0.0.1`; all requests require its token and valid local Host/Origin headers. Port, access mode, token and startup choice are saved locally. A token grants the configured access, including file operations in write mode.

## Agent operations

The server exposes **110 typed application operations**, plus seven compatible read aliases. Read-only mode advertises 40 read tools. Read-and-write mode advertises all 117 tools. `tools/list` is the authoritative source for input schemas, required fields, bounds and annotations; the [operation registry](../../modern/backend/mcp_operations.py) defines the application adapters.

| Area | Operations |
|---|---|
| Project/files | `state`, `project.new/open/save/save_copy`, project settings, transaction undo/redo, recovery list/open/discard, full workbook export and mapped workbook preview/import. |
| Database reads | `program.libraries`, `library.list/attach`, `database.inspect` (all project metadata, categories and counts), `database.analysis/resource` (complete stored definitions). Attached sources remain isolated read-only snapshots. |
| Schedule/resources | Paged hierarchy/search/category filters, numbering defaults, add/duplicate/edit/batch edit, category creation/rename/move/delete, deletion previews/policies, source imports/Modify & Add, selected database-rate preview/apply, renumbering, colours, measurement quantities, dependent rates and usage. |
| Analysis | Load a schedule analysis; add calculation rows; add/duplicate resources; edit cells/remarks; copy/paste/duplicate/delete/reorder rows; draft undo/redo; batch preview/apply; insert templates; import/export workbooks; apply to the working project. |
| Measurements | Template discovery, item/heading creation and editing, caption, links, remarks, template properties, ordered item/record operations, record batches and worksheet imports, full totals and schedule quantity updates. |
| Portable transfer | `clipboard.export/paste` exchange bounded JSON and dependencies without requiring OS clipboard access. Prefer this over a shared session copy buffer when multiple clients are connected. |
| Import options | Read shipped program defaults and validate supplied Modify & Add settings. Application UI preferences remain in the UI; supply explicit settings/rows for agent imports/templates. |

Native application tools return `{data, revision, change_seq, analysis_dirty, project_dirty, warning}` and structured content. All writes require the current integer `revision`, including file/context operations. Use the revision from the preceding response. Stale writes and invalid fields fail before mutation; existing backend transactions roll back invalid batches. Numeric values are strings containing decimals or bounded arithmetic, not JSON floats or Python code. Measurement input fields `cN`, editable flags, links and property slots come from template metadata; calculated fields and Breakup remain read-only.

The original aliases remain available: `get_project`, `list_schedule`, `list_resources`, `get_analysis`, `list_measurements`, `get_measurement`, `list_databases`. They retain their original flat results. `get_analysis` includes the active unsaved draft. `database.analysis` inspects another stored analysis without replacing that draft.

## Preparing an estimate

1. Read `state` for the revision and current dirty flags. Use `project.new` for a fresh estimate, or `project.open` for an isolated existing copy. Unsaved work requires explicit `discard: true`; it is never discarded automatically.
2. Discover/attach a database, inspect its metadata/definitions and use its paged schedule/resource states to find source IDs. Import with `add_from_library`, or create project resources/schedule items directly. New IDs and revisions are returned.
3. `analysis.load` the target schedule code, then edit/add rows and resource quantities. Preview batches before applying. `analysis.apply` updates the working estimate and dependent rates; it does not save the source file.
4. Discover measurement templates, create an item, add records, batch-edit raw inputs and link schedule codes. Blank NLBH factors remain optional. Update quantities with an explicit original rounding label.
5. Export a workbook and save explicitly. Save Copy requires a new path and refuses overwriting files; Save uses the existing project path, source-conflict checks and numbered backups. Re-read state after a transport timeout before retrying a write.

Project undo covers whole data transactions; analysis undo covers the active draft. A dirty active analysis blocks incompatible project edits until it is applied or explicitly discarded. A recovery-checkpoint failure returns a committed result with `warning`, so a client must not repeat the edit as though it failed.

## Desktop synchronization and lifecycle

Every HTTP tool uses the same serialized service/SQLite owner thread as desktop requests. The original ORM, decimal/currency routines, measurement callbacks and workbook exporters remain authoritative. The bounded queue rejects excess work. Reads wait at most 30 seconds and writes 110 seconds; a timed-out request may already be executing, so read state before retrying.

Successful writes advance a change sequence. The desktop polls lightweight status while the server runs, refreshes changed content and resets project context after agent open/new operations. It defers refresh while a cell/dialog is being edited. If an agent changes the revision during a human edit, the human's stale submission is rejected and reopened with its typed value for correction/retry. Status polling omits the full tool schemas; configuration/tool inspection loads them separately.

Closing configuration leaves the server running. Stop releases its listener; application/backend shutdown also stops it. Listener generations are checked when a tool executes, so queued or incomplete requests from a stopped listener cannot edit the project after a restart. An already executing transaction finishes before Stop runs on the owner thread. Occupied ports and invalid stored settings remain visible and recoverable in the app. Automatic startup restores the exact saved endpoint/token/access mode. Request count and the last method/tool are shown in settings; headers, token and project content are not logged. MCP tools cannot change their own listener/access configuration or execute shell commands.

The transport supports [MCP 2025-11-25 Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) and [tool discovery/calls](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), with JSON responses and negotiation for 2025-11-25/2025-06-18/2025-03-26. POST individual JSON-RPC messages to `/mcp` with `Accept: application/json, text/event-stream` and `Content-Type: application/json`; subsequent requests may include the negotiated `MCP-Protocol-Version`. Notifications return 202; GET returns 405. No session IDs, unsolicited SSE, OAuth discovery, remote binding or standalone stdio hosting are provided. Third-party client and native-platform validation remain separate gates.
