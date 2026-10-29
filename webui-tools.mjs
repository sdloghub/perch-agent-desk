import {readFileSync} from 'node:fs';
export const name = 'webui-tools';
export const inject = ['tools'];
export function apply(ctx) {
  const specs = JSON.parse(readFileSync(process.env.WEBUI_TOOL_SPECS, 'utf8'));
  for (const spec of specs) {
    ctx.tools.register({
      name: spec.name,
      description: spec.description || spec.name,
      parameters: spec.parameters || {type: 'object', properties: {}},
      output: {schema: {}, render: (_args, value) => [{type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value)}]},
      async execute(args, exec) {
        const response = await fetch(process.env.WEBUI_TOOL_URL, {
          method: 'POST', headers: {'Content-Type':'application/json',
            Authorization: `Bearer ${process.env.WEBUI_TOOL_TOKEN}`},
          body: JSON.stringify({name:spec.name, arguments:args}), signal:exec.signal,
        });
        if (!response.ok) throw new Error(`WebUI tool bridge HTTP ${response.status}`);
        return await response.json();
      },
    });
  }
}
