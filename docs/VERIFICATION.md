# Verification boundaries

- 18 offline regressions passed on the development Mac.
- 77 isolated checks passed for workspace bindings, cross-project memory
  isolation, common memory tools, history injection, revision journaling and
  native Step Code / Z Code / Claude / dsh protocol roundtrips.
- Codex and Antigravity tool/event paths use fixture processes in the isolated
  integration test. This does not prove authenticated live model availability.
- Magpie's real gateway plus a loopback fake provider attributed five requests
  with different harness User-Agents to `perch`. No paid model inference was
  used for the Perch rename/UI/plugin acceptance.
- UI browser acceptance covers history continuation, memory browsing/search,
  draft protection, theme and narrow-screen navigation. Desktop and Lighthouse
  results are recorded in the design acceptance notes after the final audit.

External model catalogs, CLI flags, login state, account allowance and region
availability can change. A route being configured is not proof that a live
model will answer. No model provider is bundled or endorsed by this project.

## 2026-10-29 UI and reasoning acceptance

- Local Magpie calls completed for Gemini 3.8 primary design and Sonnet 5.5
  auxiliary review. Gemini reviewed the implementation twice. Local review
  outputs remain in `design-review/`, excluded from the public source tree.
- Corrected Request body consumption, IME/keyboard handling and SPA workspace
  refresh. Tested Request/default/explicit effort, headers, message context,
  new-chat preference and AbortController propagation with the actual controls
  script. Request reconstruction preserves the stop signal.
- 26 Python regressions passed. Real Step/Claude/Z Code/DeepSeek CLIs used local
  mock endpoints; captured outgoing payloads verified explicit effort values,
  GLM thinking enable/disable, tools and context. Codex/Antigravity argv checks
  verified effort forwarding. This does not claim fresh live inference at every
  provider or every possible effort level.
- Real browser checks verified provider -> model selection, returning to provider
  list, cross-provider search, arrow/Enter selection, direct search Enter,
  model-dependent effort options and saved effort after reload. 390px viewport
  had matching client/scroll widths. Memory dialog remained usable at 390px.
  History restored the stored Gemini model and Open workspace.
- macOS Perch opened the native directory chooser; selecting an existing folder
  preserved its custom workspace name. Cancel and successful selection were
  checked. Packaged main/preload match source; codesign verification passed.
- The service was restarted only after its task list was empty. Health and all
  three extension assets returned HTTP 200 after restart.
- 24 loose artifacts/notes were organized with a SHA-256 manifest. Three old
  experiment directories were archived under `~/.workbench/archive`; active
  runtime dependencies and data retain their paths. `~/.workbench/README.md`
  documents the layout. No user data was deleted.

Gemini's final review also proposed changes that were not adopted: direct Enter
already worked in the live upstream selector; reconstructed Request signals
passed an abort-propagation check; history links restored original chat state.
Replacing history links with bare pushState would not ask SvelteKit to render
another route. Observer callbacks settle through existing idempotent guards.
A workspace-success toast was added. Review findings were checked independently;
model review is not a guarantee that no bugs remain.
