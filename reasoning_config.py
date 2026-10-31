"""Per-request reasoning capabilities and validation shared by UI and runtimes."""
CAPABILITIES = {
 'official': ('DeepSeek', ['low','high','max']),
 'workbuddy': ('DeepSeek', ['low','high','max']),
 'step5': ('StepFun', ['low','medium','high']),
 'gemini': ('Google', ['low','medium','high']),
 'codex': ('OpenAI', ['low','medium','high','xhigh']),
 'claude-sonnet': ('Anthropic', ['low','medium','high','xhigh','max']),
 'claude-opus': ('Anthropic', ['low','medium','high','xhigh','max']),
 'claude-haiku': ('Anthropic', ['low','medium','high','xhigh','max']),
 'claude-fable': ('Anthropic', ['low','medium','high','xhigh','max']),
 'glm53': ('智谱', ['off','high']),
 'glm53flash': ('智谱', ['off','high']),
}
def effort_for(body):
 value=body.get('reasoning_effort', (body.get('params') or {}).get('reasoning_effort'))
 if value in (None,'','default'):return None
 key=body.get('model','').rsplit('.',1)[-1]
 if key not in CAPABILITIES or value not in CAPABILITIES[key][1]:
  raise ValueError('当前模型不支持此思考等级')
 return value
