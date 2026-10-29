"""Isolated real WebUI DB/API + real vendor CLIs against loopback model fixtures.
Never contacts real model providers; never changes production memory/selection.
"""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sandbox=tempfile.TemporaryDirectory(prefix='workspace-integration-',dir=ROOT)
TEST=Path(sandbox.name);data=TEST/'data';data.mkdir()
with sqlite3.connect(f'file:{ROOT}/data/webui.db?mode=ro',uri=True) as source:
    with sqlite3.connect(data/'webui.db') as dest:source.backup(dest)
os.environ.update({'DATA_DIR':str(data),'FROM_INIT_PY':'true','LOCAL_WORKSPACE_DB':str(data/'workspaces.db'),'WEBUI_AUTH':'False','WEBUI_SECRET_KEY':'isolated-local-test-only-secret-key-32-plus',
 'OFFLINE_MODE':'True','HF_HUB_OFFLINE':'1','RAG_EMBEDDING_MODEL':str(ROOT/'embedding-model'),'RAG_EMBEDDING_MODEL_AUTO_UPDATE':'False','WHISPER_MODEL_AUTO_UPDATE':'False',
 'ENABLE_OLLAMA_API':'False','ANONYMIZED_TELEMETRY':'False','ENABLE_MEMORY_BACKGROUND_REVIEW':'False','DO_NOT_TRACK':'True'})
from starlette.requests import Request
from fastapi.testclient import TestClient
from aiohttp import web
from local_server import app
from shared_memory import SharedMemory
import agent_bridge as bridge
import harness_bridge as dsh
from open_webui.models.users import Users

results=[]
def check(condition,label):
    if not condition:raise AssertionError(label)
    results.append(label);print('PASS',label,flush=True)

async def verify_runtimes(owner,workspace,other,chat):
    user=await Users.get_user_by_id(owner)
    metadata={'user_id':owner,'chat_id':chat,'params':{'tool_approval_mode':'full'}}
    request=Request({'type':'http','app':app,'state':{'metadata':metadata},'headers':[]})
    memory=SharedMemory(request,user,workspace)
    saved=await memory.add('通用记忆初始值：青铜桥','context','verification')
    foreign=SharedMemory(request,user,other)
    await foreign.add('另一个项目的隔离记录：白桦塔','context','verification')
    await memory.add('通用用户偏好：简体中文','user','profile/verification')
    rows=await memory.search();check(any(m['id']==saved['id'] for m in rows),'canonical WebUI project memory saved')
    check(not any('白桦塔' in m['content'] for m in rows),'other workspace excluded from default memory search')
    check(any('白桦塔' in m['content'] for m in await memory.search(scope='all')),'explicit all-workspace memory search')
    try:await foreign.update([{'action':'replace','id':saved['id'],'content':'wrong project'}])
    except ValueError:pass
    else:raise AssertionError('cross-workspace write should reject')
    check((await memory.search(memory_id=saved['id']))[0]['content'].endswith('青铜桥'),'foreign workspace cannot modify current project memory')
    mode={'calls':[],'target':'search_memories','args':{'memory_id':saved['id']}}
    async def model(req):
        body=await req.json()
        if req.path.endswith('count_tokens'):return web.json_response({'input_tokens':100})
        mode['calls'].append(body)
        names=[t.get('function',t).get('name','') for t in body.get('tools',[])]
        target=next((n for n in names if n.endswith(mode['target'])),None)
        use=len(mode['calls'])==1
        if use and not target:raise AssertionError('shared memory tool absent from native model tools')
        args=json.dumps(mode['args'],ensure_ascii=False)
        if req.path.endswith('/messages'):
            block={'type':'tool_use','id':'call_probe','name':target,'input':{}} if use else {'type':'text','text':''}
            delta={'type':'input_json_delta','partial_json':args} if use else {'type':'text_delta','text':'shared-workspace-memory-ok'}
            packets=[('message_start',{'type':'message_start','message':{'id':'msg_probe','type':'message','role':'assistant','model':body['model'],'content':[],'stop_reason':None,'usage':{'input_tokens':10,'output_tokens':0}}}),('content_block_start',{'type':'content_block_start','index':0,'content_block':block}),('content_block_delta',{'type':'content_block_delta','index':0,'delta':delta}),('content_block_stop',{'type':'content_block_stop','index':0}),('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use' if use else 'end_turn','stop_sequence':None},'usage':{'output_tokens':10}}),('message_stop',{'type':'message_stop'})]
            return web.Response(text=''.join('event: '+n+'\ndata: '+json.dumps(v)+'\n\n' for n,v in packets),content_type='text/event-stream')
        delta={'tool_calls':[{'index':0,'id':'call_probe','type':'function','function':{'name':target,'arguments':args}}]} if use else {'content':'shared-workspace-memory-ok'}
        packets=[{'id':'probe','object':'chat.completion.chunk','created':1,'model':body['model'],'choices':[{'index':0,'delta':delta,'finish_reason':None}]},{'id':'probe','object':'chat.completion.chunk','created':1,'model':body['model'],'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls' if use else 'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}}]
        return web.Response(text=''.join('data: '+json.dumps(p)+'\n\n' for p in packets)+'data: [DONE]\n\n',content_type='text/event-stream')
    server=web.Application();server.router.add_post('/{tail:.*}',model)
    runner=web.AppRunner(server);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();port=site._server.sockets[0].getsockname()[1]
    oldlaunch=bridge.launch
    async def subprocess_guard(*args,**kwargs):
        check(Path(kwargs['cwd'])==Path(workspace['path']),'process cwd = selected workspace: '+Path(str(args[0])).name)
        return await original_subprocess(*args,**kwargs)
    original_subprocess=asyncio.create_subprocess_exec
    def launch(agent,run,work,env,system):
        args,prefix=oldlaunch(agent,run,work,env,system)
        if agent['kind'] not in ('agy','codex'):return args,prefix
        # These authenticated clients cannot use the loopback chat-completions
        # fixture. Exercise their exact MCP/terminal adapters and event paths.
        if agent['kind']=='agy':
            helper=work/('.webui-tools-'+run.name+'.py')
            probe="import json,subprocess,sys;sys.stdin.read();r=subprocess.run([sys.executable,HELPER,'search_memories',ARGS],capture_output=True,text=True,check=True);assert '青铜桥' in r.stdout;print(json.dumps({'event':'result','result':{'status':'SUCCESS','response':'shared-workspace-memory-ok'}}))".replace('HELPER',repr(str(helper))).replace('ARGS',repr(json.dumps({'memory_id':saved['id']})))
        else:
            probe="""import json,subprocess,sys
sys.stdin.read()
frames=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'search_memories','arguments':ARGS}}]
r=subprocess.run([sys.executable,HELPER],input=''.join(json.dumps(x)+'\\n' for x in frames),capture_output=True,text=True,check=True)
assert '青铜桥' in r.stdout
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'shared-workspace-memory-ok'}}))
print(json.dumps({'type':'turn.completed'}))
""".replace('HELPER',repr(str(ROOT/'webui_mcp.py'))).replace('ARGS',repr({'memory_id':saved['id']}))
        return [bridge.PYTHON,'-c',probe],prefix
    body={'messages':[{'role':'system','content':'<memory_context>stale-foreign-memory</memory_context> preserve-system-rule'},{'role':'user','content':'prior-context'},{'role':'assistant','content':'previous-answer'},{'role':'user','content':'read the shared memory'}]}
    try:
        with patch.object(bridge,'gateway',return_value=(f'http://127.0.0.1:{port}/v1','offline-only')),patch.object(bridge,'launch',launch),patch('asyncio.create_subprocess_exec',subprocess_guard):
            for key in bridge.AGENTS:
                mode['calls']=[]
                mode['target']='add_memory' if key=='step5' else 'search_memories'
                mode['args']={'content':'Step Code 写入，所有 harness 共用：青铜桥','type':'context','path':'cross-harness'} if key=='step5' else {'memory_id':saved['id']}
                live=[]
                async def emit(event):live.append(event)
                output=await bridge.run_agent({**body,'model':'local_agents.'+key},{},dict(metadata),emitter=emit,request=request,max_seconds=90)
                check('shared-workspace-memory-ok' in output,'runtime and canonical memory roundtrip: '+key)
                check(any(e['type']=='status' and '工具' in e['data']['description'] for e in live),'live tool event before return: '+key)
                if mode['calls']:
                    payload=json.dumps(mode['calls'][0],ensure_ascii=False)
                    check('preserve-system-rule' in payload and 'prior-context' in payload and 'previous-answer' in payload,'role history preserved: '+key)
                    check('stale-foreign-memory' not in payload and '白桦塔' not in payload,'unscoped memory replaced: '+key)
                    check(workspace['path'] in payload,'workspace identity in native prompt: '+key)
                if key=='step5':
                    rows=await memory.search(query='青铜桥');saved=next(m for m in rows if 'Step Code 写入' in m['content'])
            for source in ('deepseek/deepseek-flash','workbuddy/deepseek-v4.1-flash'):
                mode['calls']=[];mode['target']='search_memories';mode['args']={'memory_id':saved['id']}
                live=[]
                async def emit(event):live.append(event)
                output=await dsh.run_harness({**body,'_harness_model':source},{},dict(metadata),request=request,emitter=emit,base_url=f'http://127.0.0.1:{port}/v1',api_key='offline-only',max_seconds=90)
                check('shared-workspace-memory-ok' in output,'DeepSeek source shares workspace and Step memory: '+source)
                check(any(e['type']=='status' and '工具' in e['data']['description'] for e in live),'DeepSeek live tool event: '+source)
                check('Step Code 写入' in json.dumps(mode['calls'][-1],ensure_ascii=False),'DeepSeek reads memory actually written by Step Code: '+source)
        checkpoints=await memory.search(path='sessions',count=100)
        check(any('会话交接快照' in m['content'] for m in checkpoints),'successful runtime automatically persists a sourced checkpoint')
        semantic=await memory.search(query='跨代理共享的青铜桥',count=10)
        check(any(m['id']==saved['id'] for m in semantic),'paraphrased semantic retrieval finds shared memory')
        duplicate=await memory.add(saved['content'],path='cross-harness')
        check(duplicate['id']==saved['id'],'duplicate writes return existing memory id')
        changed=await memory.update([{'action':'replace','id':saved['id'],'content':'跨 harness 更新：已验证'}]);check(bool(changed),'canonical memory update')
        updated=(await memory.search(memory_id=saved['id']))[0]
        check(updated['content']=='跨 harness 更新：已验证','canonical update is immediately visible')
        check(updated['path']==saved['path'] and updated['type']==saved['type'],'content replacement preserves project path and type')
        check(not await foreign.search(memory_id=saved['id']),'replaced memory remains hidden from other projects')
        await memory.update([{'action':'remove','id':saved['id']}]);check(not await memory.search(memory_id=saved['id']),'canonical deletion is immediately visible')
    finally:await runner.cleanup()

try:
    with TestClient(app) as client:
        auth=client.post('/api/v1/auths/signin',json={'email':'','password':''}).json();headers={'Authorization':'Bearer '+auth['token']};owner=auth['id']
        def api(path='',method='get',**kwargs):
            response=getattr(client,method)('/api/local-workspaces'+path,headers=headers,**kwargs)
            if response.status_code>=400:raise RuntimeError((response.status_code,response.text))
            return response.json()
        client.cookies.clear()
        check(client.get('/api/local-workspaces').status_code==401,'API requires existing WebUI authentication')
        check(client.post('/api/local-workspaces',headers={**headers,'Origin':'https://untrusted.invalid'},json={'path':str(TEST/'bad'),'create_directory':True}).status_code==403,'cross-origin directory creation rejected')
        a=api(method='post',json={'name':'离线验收项目','path':str(TEST/'project with spaces'),'create_directory':True})
        b=api(method='post',json={'name':'隔离项目','path':str(TEST/'other'),'create_directory':True})
        check(Path(a['path']).is_dir(),'web API creates selected directory')
        check(api(method='post',json={'name':'同一路径','path':a['path']})['id']==a['id'],'directory registration is canonical/idempotent')
        chat=client.post('/api/v1/chats/new',headers=headers,json={'chat':{'title':'isolated workspace verification','models':['local_agents.step5'],'messages':[],'history':{'messages':{},'currentId':None}}}).json()['id']
        api('/selection','put',json={'workspace_id':a['id'],'chat_id':chat,'make_default':True})
        check(api('?chat_id='+chat)['selection']['workspace']['id']==a['id'],'chat selection persisted through web API')
        asyncio.run(verify_runtimes(owner,a,b,chat))
        page=client.get('/');check('/api/local-workspaces/ui.js' in page.text,'chat HTML includes workspace UI')
        check('/api/local-workspaces/ui.js' in client.get('/notes').text,'workspace extension survives direct entry at another SPA page')
        check(client.get('/api/local-workspaces/ui.js').status_code==200,'workspace frontend asset served')
        check(api('/browse?path='+str(TEST))['directories'],'web directory browser works')
    (ROOT/'workspace-integration-report.json').write_text(json.dumps({'checks':results,'passed':len(results),'real_model_calls':0,'scope':'isolated real WebUI API/DB, real Step/Claude/ZCode/DeepSeek CLIs, Codex/Antigravity scoped tool adapter fixtures'},ensure_ascii=False,indent=2))
    print('ALL PASSED',len(results),flush=True)
finally:sandbox.cleanup()
