# Magpie Agent: Perch

Adds `Perch · 栖` as a connect-only Agent in Magpie. Models remain selected in Perch.

```sh
magpie plugin add ./magpie-plugin
magpie perch provider magpie
magpie perch provider
```

The root install script also adds a `perch` launcher so Magpie can detect it.
Magpie writes `~/.config/perch/gateway.json` with its loopback URL and **Perch's
own Agent Key**. `gateway_config.py` uses that configuration for Step Code,
Claude Code, Z Code and dsh. Do not commit this JSON file. Restart Perch's
Python service after connecting or disconnecting, because dsh receives the
credential in its startup environment.

This uses the [official Agent plugin API](https://usemagpie.ai/docs/plugins).
Dedicated Agent Key attribution takes precedence over a harness's User-Agent.
The `ua` hint is a fallback, not the attribution mechanism. Built-in agents'
settings and identities remain unchanged. Direct local ChatGPT/Gemini login
calls do not use this gateway.

`magpie perch default` restores the keys Magpie replaced. The legacy migration
fallback in `gateway_config.py` can read an existing local Codex Magpie provider
only when the Perch JSON does not exist. For a fresh installation, connect this
plugin before starting Perch.

Test: `node scripts/test-magpie-plugin.mjs` runs an isolated Magpie gateway and
five loopback mock requests with different client UAs; every usage row must be
`perch`. It neither uses nor changes the live provider accounts.
