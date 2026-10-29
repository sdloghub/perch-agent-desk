// Magpie owns the per-agent key. No filesystem/network code runs in this hook.
export const agent = {
  id: "perch",
  name: "Perch · 栖",
  bin: "perch",
  config: "~/.config/perch/gateway.json",
  format: "json",
  ua: ["perch-agent-desk"],
  notice:
    "模型在 Perch 中选择。重新启动 Perch 后，内部 harness 的 Magpie 请求统一计入 Perch。",
};
export function connect({ gateway }) {
  return { base_url: gateway.v1, api_key: gateway.key, enabled: true };
}
