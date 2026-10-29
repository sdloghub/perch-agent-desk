"""Install reviewed local functions through the authenticated WebUI API."""
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8080'
token=None
def api(path,data=None,method=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)

token=api('/api/v1/auths/signin',{'email':'','password':''})['token']
existing={f['id']:f for f in api('/api/v1/functions/')}
for id,name,file in [('deepseek_harness','DeepSeek Harness','deepseek_pipe.py'),
                     ('deepseek_auto_route','DeepSeek 自动 Harness 路由','deepseek_filter.py')]:
    data={'id':id,'name':name,'content':(ROOT/file).read_text(),'meta':{'description':'本机 DeepSeek Harness 集成；WebUI 管理上下文与记忆。'}}
    entry=api(f'/api/v1/functions/id/{id}/update' if id in existing else '/api/v1/functions/create',data)
    if not entry['is_active']:entry=api(f'/api/v1/functions/id/{id}/toggle',{})
    if id=='deepseek_auto_route' and not entry['is_global']:api(f'/api/v1/functions/id/{id}/toggle/global',{})

model={'id':'deepseek-memory','base_model_id':'group/deepseek','name':'DeepSeek · Harness 记忆助手',
    'meta':{'description':'DeepSeek 自动通过官方 Harness 执行，使用 WebUI 对话与长期记忆。',
        'capabilities':{'builtin_tools':True,'file_upload':True,'file_context':False,'memory':True,'vision':False},
        'builtinTools':{'memory':True,'chats':True,'notes':True,'knowledge':True,'web_search':False,
            'image_generation':False,'code_interpreter':False,'subagents':False,'automations':False}},
    'params':{'system':(ROOT/'memory-policy.md').read_text(),'function_calling':'native'},
    'access_grants':[],'is_active':True}
models=api('/api/v1/models/list')['items']
api('/api/v1/models/model/update' if any(m['id']==model['id'] for m in models) else '/api/v1/models/create',model)
print('Installed active DeepSeek Harness pipe, global automatic router and memory model preset.')
