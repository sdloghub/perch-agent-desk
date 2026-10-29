"""Restrict this WebUI to two explicit Flash sources; never runs inference."""
import json
from pathlib import Path
import urllib.request
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8080'
token=None
def api(path,data=None):
    h={'Content-Type':'application/json'}
    if token:h['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
token=api('/api/v1/auths/signin',{'email':'','password':''})['token']
for id,file,name in [('deepseek_harness','deepseek_pipe.py','DeepSeek V4.1 Flash · 来源选择'),('deepseek_auto_route','deepseek_filter.py','DeepSeek 自动 Harness 路由')]:
    api('/api/v1/functions/id/'+id+'/update',{'id':id,'name':name,'content':(ROOT/file).read_text(),'meta':{'description':'仅 DeepSeek V4.1 Flash，明确选择官方 API 或 Workbuddy 来源。'}})
# Preserve previous model definitions and history, but remove them from selection.
models=api('/api/v1/models/list')['items']
for m in models:
    m['is_active']=False
    api('/api/v1/models/model/update?id='+quote(m['id'],safe=''),m)
config=api('/openai/config')
config['ENABLE_OPENAI_API']=False
api('/openai/config/update',config)
api('/api/v1/configs/models',{'DEFAULT_MODELS':'','DEFAULT_PINNED_MODELS':'','MODEL_ORDER_LIST':['deepseek_harness.official','deepseek_harness.workbuddy'],
    'DEFAULT_MODEL_PARAMS':{'function_calling':'native'},'DEFAULT_MODEL_METADATA':{'capabilities':{'builtin_tools':True,'memory':True,'vision':False},'builtinTools':{'memory':True,'chats':True,'notes':True,'knowledge':True,'subagents':False}}})
print('Sources:',[(m['id'],m.get('name')) for m in api('/api/models?refresh=true')['data']])
