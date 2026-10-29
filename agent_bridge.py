"""Real agent subprocesses, explicit providers, WebUI-owned history and scoped tools."""
import shutil
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import tomllib
import uuid

from aiohttp import web
from harness_bridge import make_input, render_execution

ROOT=Path(__file__).resolve().parent
SOURCES=Path(os.environ.get('PERCH_AGENT_SOURCES',ROOT.parent/'agent-sources'))
NODE=os.environ.get('PERCH_NODE') or shutil.which('node') or str(next(iter((Path.home()/'.nvm/versions/node').glob('*/bin/node')),Path('/usr/local/bin/node')))
PYTHON=str(ROOT/'.venv/bin/python')
CLAUDE=Path.home()/'Library/Application Support/Claude/claude-code'
AGENTS={
    'step5':{'name':'Step Code · Step 5 · Workbuddy','kind':'step','model':'workbuddy/step-5-preview'},
    'gemini':{'name':'Antigravity · Gemini 3.8 Flash · 本机','kind':'agy','model':'gemini-3.8-flash-high'},
    'codex':{'name':'Codex · ChatGPT · 本机','kind':'codex','model':'gpt-6.1-terra'},
    'claude-sonnet':{'name':'Claude Code · Sonnet 5.5 · Modelflare','kind':'claude','model':'modelflare/claude-sonnet-5-5'},
    'claude-opus':{'name':'Claude Code · Opus 5.5 · Modelflare','kind':'claude','model':'modelflare/claude-opus-5-5'},
    'claude-haiku':{'name':'Claude Code · Haiku 5.5 · Modelflare','kind':'claude','model':'modelflare/claude-haiku-5-5'},
    'claude-fable':{'name':'Claude Code · Fable 5.1 · Modelflare','kind':'claude','model':'modelflare/claude-fable-5-1'},
    'glm53':{'name':'Z Code · GLM 5.3 · Workbuddy','kind':'zcode','model':'workbuddy/glm-5.3'},
    'glm53flash':{'name':'Z Code · GLM 5.3 Flash · Workbuddy','kind':'zcode','model':'workbuddy/glm-5.3-flash'},
}


from gateway_config import gateway


def clean_env():
    allowed={'HOME','USER','LOGNAME','TMPDIR','LANG','LC_ALL','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY',
             'http_proxy','https_proxy','all_proxy','no_proxy','SSL_CERT_FILE','SSL_CERT_DIR','SSH_AUTH_SOCK'}
    env={k:v for k,v in os.environ.items() if k in allowed}
    env['PATH']=str(Path(NODE).parent)+':'+str(Path.home()/'.local/bin')+':/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    env.update({'NO_COLOR':'1','DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1'})
    return env


@asynccontextmanager
async def tool_bridge(body,tools,metadata,caller,run_dir,display=None):
    token=secrets.token_urlsafe(32)
    specs=[];mapped={};calls=[]
    for name,tool in tools.items():
        alias=name if len(name)<=64 else name[:47]+'_'+hashlib.sha256(name.encode()).hexdigest()[:16]
        spec={**tool.get('spec',{}),'name':alias}
        specs.append(spec);mapped[alias]=name
    spec_path=run_dir/'tools.json'
    spec_path.write_text(json.dumps(specs,ensure_ascii=False))
    async def execute(req):
        if req.headers.get('Authorization')!='Bearer '+token:
            raise web.HTTPForbidden()
        call=await req.json();alias=call.get('name');args=call.get('arguments',{})
        if alias not in mapped or not isinstance(args,dict):
            raise web.HTTPBadRequest()
        name=mapped[alias]
        if metadata.get('params',{}).get('tool_approval_mode')=='ask':
            if not caller or await caller({'type':'confirmation','data':{'tool_call':{'id':uuid.uuid4().hex,'name':name,'arguments':args}}}) is not True:
                return web.json_response({'error':'Tool call not approved'})
        if display:await display.show('调用工具 · '+name,args)
        from open_webui.utils.middleware import execute_tool_call
        _,result,_,_,_=await execute_tool_call(body,{**metadata,'tools':tools},caller,
            {'id':uuid.uuid4().hex,'type':'function','function':{'name':name,'arguments':json.dumps(args)}})
        if display:await display.show('工具结果 · '+name,result)
        calls.append({'name':name,'arguments':args,'result':result})
        return web.json_response(result,dumps=lambda value:json.dumps(value,ensure_ascii=False,default=str))
    app=web.Application(client_max_size=4*1024*1024);app.router.add_post('/tool',execute)
    runner=web.AppRunner(app,access_log=None);await runner.setup()
    try:
        site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port=site._server.sockets[0].getsockname()[1]
        yield {'WEBUI_TOOL_URL':f'http://127.0.0.1:{port}/tool','WEBUI_TOOL_TOKEN':token,'WEBUI_TOOL_SPECS':str(spec_path)},calls
    finally:
        await runner.cleanup()


def launch(agent,run_dir,workspace,env,system):
    """Build fixed executable/argv; user prompt is stdin, never shell interpolation."""
    kind=agent['kind'];model=agent['model']
    callback_env={k:env[k] for k in ('WEBUI_TOOL_URL','WEBUI_TOOL_TOKEN','WEBUI_TOOL_SPECS')}
    mcp={'command':PYTHON,'args':[str(ROOT/'webui_mcp.py')],'env':callback_env}
    if kind=='codex':
        args=[os.environ.get('PERCH_CODEX') or shutil.which('codex') or str(Path.home()/'.local/bin/codex'),'exec','--ignore-user-config','--ignore-rules',
              '--skip-git-repo-check','--ephemeral','--json','--sandbox','workspace-write',
              '-m',model,'-c','approval_policy="never"',
              '-c','mcp_servers.webui.default_tools_approval_mode="approve"',
              '-c','mcp_servers.webui.command='+json.dumps(PYTHON),
              '-c','mcp_servers.webui.args='+json.dumps(mcp['args']),
              '-c','mcp_servers.webui.env_vars='+json.dumps(['WEBUI_TOOL_URL','WEBUI_TOOL_TOKEN','WEBUI_TOOL_SPECS']),'-']
        return args,system+'\n\n'
    if kind=='agy':
        # agy has no per-invocation MCP option. Use its native terminal with a
        # scoped tool helper; never edit the user's global agy MCP registry.
        helper=workspace/('.webui-tools-'+run_dir.name+'.py')
        script=(ROOT/'webui_mcp.py').read_text()
        script=script.replace("if __name__ == '__main__':",'os.environ.update('+repr(callback_env)+")\n\nif __name__ == '__main__':")
        helper.write_text(script);helper.chmod(0o600)
        specs=Path(env['WEBUI_TOOL_SPECS']).read_text()
        prefix=system+'\n\nWebUI 工具可通过终端调用：'+PYTHON+' '+helper.name+' 工具名 \'JSON参数\'。仅在需要时调用，参数是 JSON 对象。工具定义：'+specs+'\n\n'
        return [os.environ.get('PERCH_AGY') or shutil.which('agy') or str(Path.home()/'.local/bin/agy'),'--input-format','stream-json','--output-format','stream-json',
                '--mode','auto','--sandbox','--disable-slash-commands','--model',model,'--print-timeout','580s'],prefix
    base,key=gateway()
    if kind=='claude':
        binaries=sorted(CLAUDE.glob('*/**/Contents/MacOS/claude'),key=lambda p:p.stat().st_mtime,reverse=True)
        if not binaries:raise RuntimeError('本机 Claude Code 不存在')
        env.update({'ANTHROPIC_BASE_URL':base.removesuffix('/v1'), 'ANTHROPIC_API_KEY':key,
                    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1','CLAUDE_CODE_DISABLE_AUTO_MEMORY':'1'})
        config=run_dir/'mcp.json';config.write_text(json.dumps({'mcpServers':{'webui':mcp}}))
        return [str(binaries[0]),'--bare','--print','--verbose','--output-format','stream-json',
                '--no-session-persistence','--strict-mcp-config','--mcp-config',str(config),
                '--permission-mode','acceptEdits','--allowedTools','Read,Edit,Write,Glob,Grep,Bash,mcp__webui__*',
                '--model',model,'--append-system-prompt',system],''
    if kind=='step':
        config_root=run_dir/'step';config_root.mkdir()
        agent_dir=config_root/'agent';agent_dir.mkdir()
        env.update({'STEP_CODING_AGENT_DIR':str(agent_dir),'OPENAI_API_KEY':key,'STEP_PERMISSION_PRESET':'approve-for-me'})
        # Models and MCP belong to the injected Step config root, not ~/.stepcode.
        (config_root/'models.json').write_text(json.dumps({'providers':{'magpie':{'baseUrl':base,
            'api':'openai-completions','apiKey':'$OPENAI_API_KEY',
            'models':[{'id':model,'name':'Step 5 / Workbuddy','contextWindow':262144,'maxTokens':8192}]}}}))
        (config_root/'config.toml').write_text('defaultProjectTrust = "never"\n[mcp_servers.webui]\ncommand = '+json.dumps(PYTHON)+'\nargs = '+json.dumps(mcp['args'])+'\nenabled = true\n[mcp_servers.webui.env]\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in callback_env.items()))
        return [NODE,str(SOURCES/'Step-Code/apps/cli/dist/main.js'),'--provider','magpie','--model',model,
                '--mode','json','--print','--no-session','--no-extensions','--no-skills','--no-prompt-templates',
                '--no-context-files','--append-system-prompt',system],''
    if kind=='zcode':
        home=run_dir/'zcode-home';(home/'.zcode/cli').mkdir(parents=True)
        env.update({'HOME':str(home),'ZCODE_DATA_BASE_DIR':str(home),
                    'ZCODE_BUILTIN_PROVIDER_CONFIG_FILE':str(SOURCES/'ZCode/config/provider/zcode-builtin.json')})
        config=run_dir/'provider.secret.json'
        config.write_text(json.dumps({'schemaVersion':1,'config':{
            'providerConfigRules':{'providerRules':[{'providerId':'magpie','providerName':'Workbuddy / Magpie','config':{
                'group':'standard-personal','access':{'type':'api-key','apiKey':key},
                'api':{'type':'openai-chat-completions','baseUrl':base},'personalModelIds':[model]}}]},
            'modelConfigRules':{'providerModelRules':[],'manualProviderModelRules':[]},
            'defaultModelSelection':{'providerId':'magpie','modelId':model}}}))
        config.chmod(0o600);env['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE']=str(config)
        (home/'.zcode/cli/config.json').write_text(json.dumps({
            'features':{'mcp':True,'subagent':False,'memory':False},'memory':{'use':False},
            'plugins':{'enabled':False},'skills':{'enabled':False},'hooks':{'enabled':False},
            'mcp':{'servers':{'webui':{**mcp,'type':'stdio','enabled':True,'alwaysLoad':True}}}}))
        # The official CLI selects the provider through its config, not --model.
        return [NODE,str(SOURCES/'ZCode/apps/zcode-cli/packages/cli/dist/zcode.cjs'),
                '--mode','guarded','--output-format','stream-json','--cwd',str(workspace),'--prompt'],system+'\n\n'
    raise ValueError('Unknown agent')


class Events:
    def __init__(self,kind):
        self.kind=kind;self.final='';self.completed=False;self.failure=None;self.trace=[]

    def add(self,event):
        kind=event.get('type');item=event.get('item',{})
        if self.kind=='codex':
            if kind=='item.completed' and item.get('type')=='agent_message':self.final=item.get('text','')
            if kind in ('turn.completed','thread.completed'):self.completed=True
            if kind in ('turn.failed','thread.failed','error'):self.failure=event.get('error') or event.get('message') or 'Codex failed'
            if kind in ('item.started','item.completed') and item.get('type') in ('command_execution','mcp_tool_call','file_change','web_search'):
                self.trace.append(json.dumps(item,ensure_ascii=False))
        elif self.kind=='step':
            if kind=='message_end' and event.get('message',{}).get('role')=='assistant':
                message=event['message']
                text=''.join(b.get('text','') for b in message.get('content',[]) if b.get('type')=='text')
                if text:self.final=text
                if message.get('stopReason') in ('error','aborted'):self.failure=message.get('errorMessage','Step Code failed')
            if kind=='agent_end':self.completed=True
            if kind in ('tool_execution_start','tool_execution_end'):self.trace.append(json.dumps(event,ensure_ascii=False))
        elif self.kind=='agy':
            if event.get('event')=='result':
                result=event.get('result',{});self.final=result.get('response','')
                self.completed=result.get('status')=='SUCCESS'
                if not self.completed:self.failure='Antigravity 未成功完成（检查本机登录或配额）'
            elif 'tool' in event.get('event','').lower():
                self.trace.append(json.dumps(event,ensure_ascii=False))
        elif self.kind=='claude':
            if kind=='result':
                self.final=event.get('result','');self.completed=not event.get('is_error',False) and event.get('subtype')=='success'
                if not self.completed:self.failure='Claude Code 未成功完成'
            if kind in ('assistant','user'):
                for block in event.get('message',{}).get('content',[]):
                    if block.get('type') in ('tool_use','tool_result'):self.trace.append(json.dumps(block,ensure_ascii=False))
        elif self.kind=='zcode':
            if kind=='result':
                self.final=event.get('response','');self.completed=event.get('projection',{}).get('status')=='idle'
                if not self.completed:self.failure='Z Code 未成功完成'
            elif kind in ('turn.failed','session.error'):
                self.failure='Z Code runtime error'
            elif event.get('payload',{}).get('toolName') and kind!='model.streaming':
                self.trace.append(json.dumps({'type':kind,'data':event['payload']},ensure_ascii=False))


async def run_agent(body,tools,metadata,emitter=None,caller=None,request=None,*,max_seconds=600):
    key=body.get('model','').rsplit('.',1)[-1]
    if key not in AGENTS:raise ValueError('请选择有效的 Agent 与模型来源')
    agent=AGENTS[key]
    chat=str(metadata.get('chat_id') or uuid.uuid4().hex)
    chat_hash=hashlib.sha256(chat.encode()).hexdigest()[:24]
    run_dir=ROOT/'agent-runs'/chat_hash/uuid.uuid4().hex;run_dir.mkdir(parents=True,mode=0o700)
    from runtime_context import prepare_runtime
    workspace,body,tools,shared_instructions=await prepare_runtime(body,tools,metadata,request)
    system,blocks=make_input(body.get('messages',[]))
    system=shared_instructions+'\n\n'+system
    from execution_display import ExecutionDisplay
    display=ExecutionDisplay(emitter,agent['name'])
    proc=None;events=Events(agent['kind']);completed=False;packets=[]
    async def status(text,done=False):
        if emitter:await emitter({'type':'status','data':{'description':text,'done':done}})
    try:
        async with tool_bridge(body,tools,metadata,caller,run_dir,display) as (tool_env,calls):
            env={**clean_env(),**tool_env}
            args,prefix=launch(agent,run_dir,workspace,env,system)
            prompt=prefix+blocks[0]['text']
            if agent['kind']=='zcode':
                # CLI only accepts --prompt text; store the argv in memory only.
                args.append(prompt);input_data=b''
            elif agent['kind']=='agy':
                input_data=(json.dumps({'event':'user','message':{'content':prompt}},ensure_ascii=False)+'\n').encode()
            else:input_data=prompt.encode()
            await status('正在思考…')
            with (run_dir/'stderr.log').open('wb') as err:
                proc=await asyncio.create_subprocess_exec(*args,cwd=workspace,env=env,
                    stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=err,
                    start_new_session=True,limit=16*1024*1024)
                async with asyncio.timeout(max_seconds):
                    proc.stdin.write(input_data);await proc.stdin.drain();proc.stdin.close()
                    total=0
                    while raw:=await proc.stdout.readline():
                        total+=len(raw)
                        if total>32*1024*1024:raise RuntimeError('Agent 输出超过本机保留上限')
                        try:event=json.loads(raw)
                        except json.JSONDecodeError:continue
                        if not isinstance(event,dict):continue
                        packets.append(event);old=len(events.trace);events.add(event)
                        for trace in events.trace[old:]:await display.show('原生工具执行',trace)
                        # Only public assistant prose, never thinking/reasoning blocks.
                        if agent['kind'] in ('step','claude') and event.get('type') in ('message_end','assistant'):
                            message=event.get('message',{})
                            if message.get('role','assistant')=='assistant':
                                text=''.join(b.get('text','') for b in message.get('content',[]) if b.get('type')=='text')
                                if text:
                                    await display.show('模型进度说明',text)
                                    events.trace.append('模型进度说明：'+text)
                        elif agent['kind']=='codex' and event.get('type')=='item.completed' and event.get('item',{}).get('type')=='agent_message':
                            await display.show('模型进度说明',event['item'].get('text',''))
                    code=await proc.wait()
            if code or events.failure or not events.completed or not events.final.strip():
                raise RuntimeError(f'{agent["name"]} 执行失败或未完整结束（退出码 {code}）。请查看本机 agent-runs 的 stderr.log。')
            for call in calls:events.trace.append('WebUI 工具：'+json.dumps(call,ensure_ascii=False,default=str))
            result=render_execution(events.trace,events.final).replace('DeepSeek Harness 执行记录',agent['name']+' 执行记录',1)
            completed=True
            await status(agent['name']+' 执行完成',True)
            try:
                from runtime_context import checkpoint
                await checkpoint(body,metadata,request,result)
            except Exception as error:
                from memory_journal import record
                record(metadata.get('user_id','unknown'),'checkpoint_failed',{'chat_id':metadata.get('chat_id'),'error_type':type(error).__name__})
            return result
    finally:
        if proc and proc.returncode is None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:await asyncio.wait_for(proc.wait(),5)
            except asyncio.TimeoutError:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await proc.wait()
        # Temporary Z Code provider files necessarily contain a plaintext key.
        # Remove them on success, failure and cancellation; never archive them.
        shutil.rmtree(run_dir/'zcode-home',ignore_errors=True)
        (run_dir/'step/models.json').unlink(missing_ok=True)
        (run_dir/'provider.secret.json').unlink(missing_ok=True)
        (run_dir/'mcp.json').unlink(missing_ok=True)
        (run_dir/'step/config.toml').unlink(missing_ok=True)
        (run_dir/'zcode-home/.zcode/cli/config.json').unlink(missing_ok=True)
        (workspace/('.webui-tools-'+run_dir.name+'.py')).unlink(missing_ok=True)
        (run_dir/'result.json').write_text(json.dumps({'agent':key,'model':agent['model'],'completed':completed,
            'chat_id':chat,'workspace':metadata.get('local_workspace'),'events':packets,'response':events.final},ensure_ascii=False,indent=2))
