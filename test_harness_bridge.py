import asyncio
import json
import sys
import types
import unittest
from aiohttp import web
from harness_bridge import run_harness, make_input
from deepseek_route import resolve_deepseek

class RoutingTests(unittest.TestCase):
    def test_resolution(self):
        self.assertEqual(resolve_deepseek('group/deepseek',{}),'group/deepseek')
        self.assertEqual(resolve_deepseek('deepseek-v4.1-flash',{}),'deepseek-v4.1-flash')
        self.assertIsNone(resolve_deepseek('workbuddy/step-5-preview',{}))
        self.assertIsNone(resolve_deepseek('notdeepseek',{}))
        self.assertEqual(resolve_deepseek('my-memory',{'my-memory':{'info':{'base_model_id':'group/deepseek'}}}),'group/deepseek')
        self.assertIsNone(resolve_deepseek('a',{'a':{'info':{'base_model_id':'a'}}}))

    def test_context(self):
        system,blocks=make_input([{'role':'system','content':'memory-marker'},
            {'role':'user','content':'old-turn'}, {'role':'assistant','content':'old-reply'},
            {'role':'user','content':'continue'}])
        self.assertIn('memory-marker',system)
        for value in ('old-turn','old-reply','continue'):self.assertIn(value,blocks[0]['text'])

class PassthroughTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_deepseek_unchanged(self):
        from deepseek_filter import Filter
        body={'model':'workbuddy/step-5-preview','messages':[{'role':'user','content':'hello'}]}
        before=json.dumps(body)
        request=types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace(MODELS={})))
        self.assertIs(await Filter().inlet(body,request),body)
        self.assertEqual(json.dumps(body),before)

class SourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_sources(self):
        from unittest.mock import AsyncMock, patch
        from deepseek_pipe import Pipe
        pipe=Pipe()
        self.assertEqual(len(pipe.pipes()),2)
        for source,target in [('official','deepseek/deepseek-flash'),('workbuddy','workbuddy/deepseek-v4.1-flash')]:
            with patch('harness_bridge.run_harness',new_callable=AsyncMock,return_value='ok') as run:
                self.assertEqual(await pipe.pipe({'model':'deepseek_harness.'+source}),'ok')
                self.assertEqual(run.call_args.args[0]['_harness_model'],target)
        with self.assertRaises(ValueError):
            await pipe.pipe({'model':'deepseek_harness'})

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self,effort=None):
        requests=[];callbacks=[]
        async def mock(req):
            body=await req.json();requests.append(body)
            if len(requests)==1:
                delta={'tool_calls':[{'index':0,'id':'call-webui','type':'function',
                    'function':{'name':'webui_probe_memory','arguments':'{"query":"context-marker"}'}}]}
                finish='tool_calls'
            else:
                self.assertIn('callback-ok',json.dumps(body))
                delta={'content':'verified-final-context-marker'};finish='stop'
            packets=[{'id':'mock','object':'chat.completion.chunk','created':1,'model':body['model'],
                'choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                {'id':'mock','object':'chat.completion.chunk','created':1,'model':body['model'],
                'choices':[{'index':0,'delta':{},'finish_reason':finish}],
                'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}}]
            return web.Response(text=''.join('data: '+json.dumps(p)+'\n\n' for p in packets)+'data: [DONE]\n\n',content_type='text/event-stream')
        app=web.Application();app.router.add_post('/v1/chat/completions',mock)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port=site._server.sockets[0].getsockname()[1]
        fake=types.ModuleType('open_webui.utils.middleware')
        async def execute(body,metadata,caller,tool_call):
            callbacks.append(tool_call)
            return {},{'result':'callback-ok'},None,None,False
        fake.execute_tool_call=execute
        old=sys.modules.get('open_webui.utils.middleware');sys.modules['open_webui.utils.middleware']=fake
        try:
            result=await run_harness({'_harness_model':'group/deepseek','model':'deepseek_harness.official',**({'reasoning_effort':effort} if effort else {}),'messages':[
                {'role':'system','content':'system-marker'}, {'role':'user','content':'old-context-marker'},
                {'role':'assistant','content':'old-assistant-marker'}, {'role':'user','content':'current-marker'}]},
                {'probe_memory':{'spec':{'name':'probe_memory','description':'Read probe memory',
                    'parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}}},
                {'chat_id':'offline-verification'},base_url=f'http://127.0.0.1:{port}/v1',api_key='test-not-secret',max_seconds=120)
            self.assertIn('verified-final-context-marker',result)
            self.assertNotIn('webui_probe_memory',result)
            self.assertEqual(len(callbacks),1)
            self.assertEqual(callbacks[0]['function']['name'],'probe_memory')
            payload=json.dumps(requests[0])
            for marker in ('system-marker','old-context-marker','old-assistant-marker','current-marker'):self.assertIn(marker,payload)
            self.assertEqual(requests[0]['model'],'group/deepseek')
            if effort:self.assertEqual(requests[0].get('reasoning_effort'),effort)
        finally:
            if old is None:sys.modules.pop('open_webui.utils.middleware',None)
            else:sys.modules['open_webui.utils.middleware']=old
            await runner.cleanup()

    async def test_real_harness_tools_and_context(self):await self.exercise()
    async def test_high_reasoning_wire(self):await self.exercise('high')
    async def test_max_reasoning_wire(self):await self.exercise('max')

if __name__=='__main__':unittest.main(verbosity=2)
