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
