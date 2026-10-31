"""Exercise the actual vendor CLIs against loopback model fixtures, never real inference."""
import json
import sys
import types
import unittest
from unittest.mock import patch
from aiohttp import web
import agent_bridge as bridge

class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self,key,effort=None):
        requests=[];calls=[]
        async def serve(req):
            body=await req.json()
            if req.path.endswith('count_tokens'):return web.json_response({'input_tokens':100})
            requests.append(body)
            tools=body.get('tools',[])
            names=[t.get('function',t).get('name','') for t in tools]
            candidates=[n for n in names if 'probe_memory' in n]
            use_tool=len(requests)==1 and bool(candidates)
            if '/messages' in req.path:
                model=body['model'];stop='tool_use' if use_tool else 'end_turn'
                block={'type':'tool_use','id':'call_probe','name':candidates[0],'input':{}} if use_tool else {'type':'text','text':''}
                delta={'type':'input_json_delta','partial_json':'{"query":"native-probe"}'} if use_tool else {'type':'text_delta','text':'native-final-context-ok'}
                packets=[('message_start',{'type':'message_start','message':{'id':'msg_probe','type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'usage':{'input_tokens':20,'output_tokens':0}}}),
                    ('content_block_start',{'type':'content_block_start','index':0,'content_block':block}),
                    ('content_block_delta',{'type':'content_block_delta','index':0,'delta':delta}),
                    ('content_block_stop',{'type':'content_block_stop','index':0}),
                    ('message_delta',{'type':'message_delta','delta':{'stop_reason':stop,'stop_sequence':None},'usage':{'output_tokens':10}}),('message_stop',{'type':'message_stop'})]
                return web.Response(text=''.join('event: '+name+'\ndata: '+json.dumps(packet)+'\n\n' for name,packet in packets),content_type='text/event-stream')
            if use_tool:
                delta={'tool_calls':[{'index':0,'id':'call_probe','type':'function','function':{'name':candidates[0],'arguments':'{"query":"native-probe"}'}}]};stop='tool_calls'
            else:delta={'content':'native-final-context-ok'};stop='stop'
            packets=[{'id':'chatcmpl_probe','object':'chat.completion.chunk','created':1,'model':body['model'],'choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                {'id':'chatcmpl_probe','object':'chat.completion.chunk','created':1,'model':body['model'],'choices':[{'index':0,'delta':{},'finish_reason':stop}],'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}}]
            return web.Response(text=''.join('data: '+json.dumps(p)+'\n\n' for p in packets)+'data: [DONE]\n\n',content_type='text/event-stream')
        app=web.Application();app.router.add_post('/{tail:.*}',serve)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port=site._server.sockets[0].getsockname()[1]
        fake=types.ModuleType('open_webui.utils.middleware')
        async def execute(body,metadata,caller,call):
            calls.append(call);return {},'native-memory-result',None,None,False
        fake.execute_tool_call=execute
        old=sys.modules.get('open_webui.utils.middleware');sys.modules['open_webui.utils.middleware']=fake
        try:
            with patch.object(bridge,'gateway',return_value=(f'http://127.0.0.1:{port}/v1','offline-placeholder')):
                result=await bridge.run_agent({'model':'local_agents.'+key,**({'reasoning_effort':effort} if effort else {}),'messages':[{'role':'system','content':'native-system-marker'},
                    {'role':'user','content':'native-history-marker'},{'role':'user','content':'Invoke probe_memory then answer native-final-context-ok.'}]},
                    {'probe_memory':{'spec':{'name':'probe_memory','description':'Read-only test memory','parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}}},
                    {'chat_id':'native-offline-'+key},max_seconds=90)
            self.assertIn('native-final-context-ok',result)
            self.assertEqual(len(calls),1,'CLI must expose and execute the scoped WebUI MCP tool; exposed='+repr([t.get('function',t).get('name') for t in requests[0].get('tools',[])]))
            self.assertTrue(all(x['model']==bridge.AGENTS[key]['model'] for x in requests))
            if effort:
                expected={'claude-sonnet':('output_config',{'effort':effort}), 'step5':('reasoning_effort',effort), 'glm53':('thinking',{'type':'disabled' if effort=='off' else 'enabled'})}[key]
                self.assertEqual(requests[0].get(expected[0]),expected[1], 'reasoning must reach the actual model request')
            for marker in ('native-system-marker','native-history-marker'):self.assertIn(marker,json.dumps(requests[0]))
        finally:
            if old is None:sys.modules.pop('open_webui.utils.middleware',None)
            else:sys.modules['open_webui.utils.middleware']=old
            await runner.cleanup()
    async def test_step_official_cli(self):await self.exercise('step5')
    async def test_zcode_official_cli(self):await self.exercise('glm53')
    async def test_local_claude_cli(self):await self.exercise('claude-sonnet')
    async def test_step_reasoning_wire(self):await self.exercise('step5','high')
    async def test_claude_reasoning_wire(self):await self.exercise('claude-sonnet','high')
    async def test_glm_reasoning_enabled_wire(self):await self.exercise('glm53','high')
    async def test_glm_reasoning_disabled_wire(self):await self.exercise('glm53','off')

if __name__=='__main__':unittest.main(verbosity=2)
