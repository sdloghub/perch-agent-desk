"""Expose reviewed local agent adapters without restoring unrelated gateway models."""
import json
from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8080'
token=None
def api(path,data=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
    with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
token=api('/api/v1/auths/signin',{'email':'','password':''})['token']
existing={x['id']:x for x in api('/api/v1/functions/')}
data={'id':'local_agents','name':'本机 Agent · 模型与来源选择','content':(ROOT/'agent_pipe.py').read_text(),
      'meta':{'description':'Step Code/Step 5、Antigravity/Gemini、Codex/ChatGPT、Claude Code/Modelflare、Z Code/Workbuddy GLM。WebUI 管理历史与记忆。'}}
entry=api('/api/v1/functions/id/local_agents/update' if 'local_agents' in existing else '/api/v1/functions/create',data)
if not entry['is_active']:api('/api/v1/functions/id/local_agents/toggle',{})
# Keep gateway's broad catalog disabled. Only explicit agent pipe entries appear.
config=api('/openai/config')
assert config['ENABLE_OPENAI_API'] is False
from agent_bridge import AGENTS
preferences=api('/api/v1/configs/models')
preferences['MODEL_ORDER_LIST']=['deepseek_harness.official','deepseek_harness.workbuddy']+['local_agents.'+key for key in AGENTS]
api('/api/v1/configs/models',preferences)
print([(x['id'],x.get('name')) for x in api('/api/models?refresh=true')['data']])
