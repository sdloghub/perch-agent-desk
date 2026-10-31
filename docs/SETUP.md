# Setup and architecture

## Installation scope

This source snapshot targets macOS, Python 3.12, Node.js 24, Open WebUI 0.12.4,
Electron 45.1.0 and a Magpie release supporting custom Agent plugins (tested
with 0.1.1809). Install Magpie from its official distribution. The repository
contains no model weights, provider accounts or vendor CLI binaries.

Install the Python and desktop dependencies with the commands in README.
Before starting `start.py`, download a compatible local embedding model:

```sh
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-small-zh-v1.5', local_dir='embedding-model')"
```

The startup is offline after that download. The embedding weights must exist
locally; they are not part of Git. `start.py` creates its own session secret,
uses `data/`, disables remote catalog passthrough and binds `127.0.0.1:8080`.
On first run the single-user WebUI account is created by its built-in sign-in
endpoint. No external login is required. Keep this configuration local.

## Agent dependencies

The adapters currently expect these separate installations:

- `harness-runtime/node_modules/@deepseek-ai/dsh/lib/bin.js`: `npm ci --prefix harness-runtime`.
- Step Code built at `../agent-sources/Step-Code/apps/cli/dist/main.js`.
  Source: https://github.com/stepfun-ai/Step-Code ; local tested revision
  `81e79bc4b699148d6823fedde9b5e70d9a80255f`. Follow upstream's pnpm build.
- Z Code built at `../agent-sources/ZCode/apps/zcode-cli/packages/cli/dist/zcode.cjs`.
  Source: https://github.com/zai-org/ZCode ; tested revision
  `3c5b227649371507ddc4eb46ac5133afe6db1cab`. Follow upstream's CLI build.
- `codex` and `agy` on PATH, authenticated with your own local account.
- Claude Code installed by the Claude desktop app under
  `~/Library/Application Support/Claude/claude-code/*/**/Contents/MacOS/claude`.

Set `PERCH_AGENT_SOURCES` for a different Step-Code/ZCode parent directory;
`PERCH_NODE`, `PERCH_CODEX` and `PERCH_AGY` override executable discovery.
A missing runtime fails explicitly when selected. CLI options and provider
model IDs are version-sensitive: inspect `agent_bridge.py` and `deepseek_route.py`
against your actual upstream installation.

## Models and first-time WebUI configuration

Configure your own DeepSeek/Workbuddy/Modelflare providers in Magpie; the IDs in
`AGENTS` must match your catalog. Connect the Perch plugin before service startup:

```sh
.venv/bin/python scripts/install_magpie_plugin.py
.venv/bin/python start.py
```

In a second terminal, install the reviewed WebUI functions and limit the catalog:

```sh
.venv/bin/python install_harness.py
.venv/bin/python configure_sources.py
.venv/bin/python install_agents.py
```

These configure local WebUI functions; they do not call a model. `configure_sources.py`
disables previously configured native model presets, without deleting chat history.
Run it once on a fresh dedicated instance, not as an automatic upgrade command.
Use the existing WebUI model selector for the explicit source/runtime aliases.
There is no account onboarding wizard in this early source release.

## Application and UI

`desktop/build_app.py` copies the pinned Electron distribution, sets Perch's
name/bundle ID, generates the Perch P icon with transparent outer padding,
copies the sandboxed desktop shell and signs it locally. Icon generation uses
`desktop/build_icon.swift`, macOS `iconutil`, and Xcode Command Line Tools. It
refuses to overwrite an existing bundle. Open `desktop/Perch.app` after starting
the service. The desktop shell opens `/`, preserves the previous local
WebUI browser profile on upgrades, and has no Node integration in web pages.
It does not start the Python service automatically. A user-managed LaunchAgent
may run `start.py` with the repository's Python executable and working directory.

The main interface is the original Open WebUI SPA at `/`, with the upstream
sidebar, chat, model selector, attachments and streaming controls intact.
`local_workspace_ui.js` and `.css` add compact workspace/history/memory controls
and a neutral black treatment. The theme initializes to dark before upstream
hydration. Memory records are paginated and expandable. No iframe or second
frontend framework is loaded by the native entry point.

Old `/desk` bookmarks redirect to `/`; a valid `?chat=<UUID>` continues at
`/c/<UUID>`. The earlier React prototype and bridge assets remain in `ui/` for
reference but are no longer the application entry point or build dependency.

## Memory and projects

WebUI's memory rows are authoritative. `shared_memory.py` provides the same
memory tools to every runtime and filters by owner/global/project scope.
`workspace_store.py` stores directory registrations and chat bindings separately.
`runtime_context.py` injects a bounded retrieved memory context and saves sourced
per-chat handoff checkpoints. Imported memory is evidence, not instructions.

`memory_journal.py` records revisions locally; `backup.py` uses SQLite's backup
API. Deleting a memory does not purge backups or the revision journal. To back
up, run `.venv/bin/python backup.py`; restore requires a stopped service and a
consistent matching set of databases. Do not publish these files.

The service can execute real terminal/file tools in the selected directory.
This is a local, trusted-user integration, not a multi-tenant sandbox. Avoid
untrusted project contents and review each runtime's permission options.


## Desktop controls

`desktop/preload.cjs` must ship next to `main.cjs`; `build_app.py` includes it.
Clicking the workspace button in Perch opens the native macOS directory picker.
Browser users can use the directory manager instead. Provider groups and model
reasoning controls are served by `perch_controls.js`; capability metadata comes
from the authenticated `/api/local-workspaces/runtime-models` endpoint.
`reasoning_config.py` validates per-model effort levels before invoking runtimes.
Automatic leaves the runtime default intact. Explicit settings affect subsequent
requests and persist locally per chat/model, with a model preference for new chats.

Run `node scripts/test-controls.cjs` for fetch/body/header preservation checks and
`.venv/bin/python -m unittest discover -p 'test_*.py' -v` for runtime regressions.
The native CLI tests use loopback mock endpoints and do not consume provider credit.

Local screenshots and acceptance reports live under `artifacts/`; local progress
notes live in `docs/local/`. The workbench root README lists active directories
and archived experiments. Do not move runtime dependencies, credentials or data
without checking their live references.
