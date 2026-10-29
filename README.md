# Perch · 栖

A local agent desk with shared memory, project workspaces and a standalone Chromium app.

[简体中文](README.zh-CN.md) · [Architecture & setup](docs/SETUP.md) · [Magpie agent plugin](magpie-plugin/README.md)

Perch brings the conversation history, working directory and memory of several agent runtimes into one macOS window. It is built **on Open WebUI and Magpie**: Open WebUI owns conversations and the memory database; Magpie routes supported model requests. Perch adds the workspace shell, runtime adapters, scoped memory tools and a dedicated Magpie agent identity. This is an independent integration, not an official product of either upstream project.

- Persistent history sidebar with title/content search, continuation and unsent-draft protection.
- Per-chat working directories shared across the embedded runtimes.
- Searchable, paginated memory library with provenance, editing, deletion and a local revision journal.
- Local lexical/embedding retrieval, global user preferences and project-scoped context.
- React + Radix Themes interface, Phosphor icons, light/dark themes and narrow-screen navigation.
- Electron client using Chromium, independent of an external browser.
- Magpie Agent plugin: internal harness requests use Perch's dedicated Agent Key, so usage belongs to `perch` even when the client's User-Agent names another harness.

## Runtime routes

| Runtime | Configured source |
| --- | --- |
| DeepSeek Harness (dsh) | DeepSeek V4.1 Flash, official API or Workbuddy via Magpie |
| Step Code | Step 5 via Workbuddy / Magpie |
| Claude Code | Claude via Modelflare / Magpie |
| Z Code | GLM 5.3 / GLM 5.3 Flash via Workbuddy / Magpie |
| Codex | Local ChatGPT login |
| Antigravity | Local Gemini login |

Model availability depends on your own providers and local installations. Local ChatGPT/Gemini calls do not pass through Magpie and are not counted as Perch gateway usage. No credentials, account sessions, model binaries or user data are distributed here. The adapters are an early macOS integration with external CLI dependencies, not a universal installer.

## Start

Requires macOS, Python 3.12, Node.js 24, Magpie with Agent plugin support, and the desired agent runtimes. Read [setup](docs/SETUP.md) for dependencies, model configuration and the one-time local model installation.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --prefix ui
npm run build --prefix ui
npm ci --prefix desktop
.venv/bin/python desktop/build_app.py
.venv/bin/python scripts/install_magpie_plugin.py
.venv/bin/python start.py
```

Open `http://127.0.0.1:8080/desk` or `desktop/Perch.app`. The service uses Open WebUI's single-user mode with no login form and binds to loopback only. Do not expose this configuration to a network.

## Verification

```sh
.venv/bin/python -m unittest discover -p 'test_*.py' -v
.venv/bin/python verify_workspace_integration.py
node scripts/test-magpie-plugin.mjs
```

The runtime tests require installed CLI dependencies. They use loopback model fixtures, not paid inference. The integration test copies an existing local WebUI database into an isolated temporary database; it does not change live conversations. Local verification: 18 regression tests and 77 integration checks. Codex and Antigravity protocol checks use fixtures, not live model acceptance; Gemini may be unavailable in some regions. See [verification boundaries](docs/VERIFICATION.md).

## Upstream credit

- [Open WebUI](https://github.com/open-webui/open-webui): conversation engine, UI, memory APIs and local embeddings. Its license and branding terms remain applicable; [license copy](third_party/Open-WebUI-LICENSE).
- [Magpie](https://github.com/yetone/magpie): model gateway, provider routing and the Agent plugin mechanism. MIT licensed.
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness), [Step Code](https://github.com/stepfun-ai/Step-Code), [Z Code](https://github.com/zai-org/ZCode): separately installed runtimes. Codex, Claude Code and Antigravity are installed/authenticated separately.
- React, Radix Themes, Phosphor Icons and Electron supply the app interface and desktop shell.

Original Perch integration code is MIT licensed. Upstream software retains its own licenses; it is not relicensed by this repository. The UI retains visible Open WebUI and Magpie attribution. See [NOTICE](NOTICE).
