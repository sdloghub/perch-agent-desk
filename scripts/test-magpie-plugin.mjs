// Isolated real Magpie + mock upstream. No provider accounts or paid calls.
import { execFileSync, spawn } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  copyFileSync,
  chmodSync,
} from "node:fs";
import { join, dirname, resolve } from "node:path";
import { tmpdir, homedir } from "node:os";
import { createServer } from "node:http";
import { once } from "node:events";
import assert from "node:assert/strict";
const root = resolve(import.meta.dirname, ".."),
  scratch = mkdtempSync(join(tmpdir(), "perch-magpie-")),
  config = join(scratch, "config");
mkdirSync(join(scratch, "bin"), { recursive: true });
writeFileSync(join(scratch, "bin/perch"), "#!/bin/sh\nexit 0\n", {
  mode: 0o755,
});
const env = {
  ...process.env,
  XDG_CONFIG_HOME: config,
  XDG_CACHE_HOME: join(scratch, "cache"),
  HOME: scratch,
  PATH: join(scratch, "bin") + ":" + process.env.PATH,
  MAGPIE_NO_ACCOUNTS: "1",
  MAGPIE_PLUGIN_MARKET: "off",
};
const bun =
  process.env.MAGPIE_TEST_BUN ||
  join(homedir(), ".cache/magpie/bun/1.4.4/magpie-bun");
for (const v of ["1.4.4", "1.4.2"]) {
  const dest = join(env.XDG_CACHE_HOME, "magpie/bun", v, "magpie-bun");
  mkdirSync(dirname(dest), { recursive: true });
  copyFileSync(bun, dest);
  chmodSync(dest, 0o755);
}
const cli = (...args) =>
  execFileSync(
    process.env.MAGPIE_TEST_BINARY || join(homedir(), ".local/bin/magpie"),
    args,
    {
      env,
      encoding: "utf8",
      timeout: 30000,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
async function listen(s) {
  s.listen(0, "127.0.0.1");
  await once(s, "listening");
  return s.address().port;
}
const mock = createServer(async (req, res) => {
  for await (const _ of req) {
  }
  res.setHeader("Content-Type", "application/json");
  res.end(
    JSON.stringify(
      req.method === "GET"
        ? { data: [{ id: "test-model", object: "model" }] }
        : {
            id: "mock",
            object: "chat.completion",
            model: "test-model",
            choices: [
              {
                index: 0,
                message: { role: "assistant", content: "perch-fixture-ok" },
                finish_reason: "stop",
              },
            ],
            usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
          },
    ),
  );
});
let server;
try {
  const port = await listen(mock),
    reserve = createServer(),
    gatewayPort = await listen(reserve);
  await new Promise((r) => reserve.close(r));
  env.MAGPIE_ADDR = `127.0.0.1:${gatewayPort}`;
  cli("plugin", "add", join(root, "magpie-plugin"));
  cli(
    "provider",
    "add",
    "Fixture",
    "id=fixture",
    `url=http://127.0.0.1:${port}/v1`,
    "key=mock-local-only",
    "models=test-model",
  );
  writeFileSync(join(scratch, "agents.txt"), cli("agents"));
  cli("perch", "provider", "magpie");
  const gateway = JSON.parse(
    readFileSync(join(scratch, ".config/perch/gateway.json"), "utf8"),
  );
  assert.ok(gateway.api_key);
  assert.equal(gateway.enabled, true);
  let logs = "";
  server = spawn(
    process.env.MAGPIE_TEST_BINARY || join(homedir(), ".local/bin/magpie"),
    ["serve"],
    { env, stdio: ["ignore", "pipe", "pipe"] },
  );
  server.stderr.on("data", (x) => (logs += x));
  server.stdout.on("data", (x) => (logs += x));
  const base = `http://127.0.0.1:${gatewayPort}`;
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try {
      await fetch(base + "/v1/models", {
        headers: { Authorization: "Bearer " + gateway.api_key },
      });
      ready = true;
      break;
    } catch {
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  assert.ok(ready, "gateway starts");
  for (const ua of [
    "claude-cli/2",
    "pi-ai/1",
    "step-code/1",
    "zcode/1",
    "perch-agent-desk",
  ]) {
    const r = await fetch(base + "/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + gateway.api_key,
        "Content-Type": "application/json",
        "User-Agent": ua,
      },
      body: JSON.stringify({
        model: "fixture/test-model",
        messages: [{ role: "user", content: "fixture" }],
        stream: false,
      }),
    });
    assert.equal(r.status, 200, await r.text());
  }
  const csv = cli("usage", "--csv", "all");
  writeFileSync(join(scratch, "usage.csv"), csv);
  const rows = csv.trim().split("\n");
  assert.equal(rows.length, 6);
  for (const row of rows.slice(1)) assert.ok(row.includes("perch"), row);
  assert.equal(
    rows.filter(
      (x) =>
        x.includes("claude") || x.includes("step-code") || x.includes("zcode"),
    ).length,
    0,
  );
  console.log(
    JSON.stringify(
      {
        passed: true,
        requests: 5,
        attributedTo: "perch",
        paidCalls: 0,
        scratch,
      },
      null,
      2,
    ),
  );
} catch (e) {
  console.error(e.message);
  process.exitCode = 1;
} finally {
  server?.kill("SIGTERM");
  await new Promise((r) => mock.close(r));
}
