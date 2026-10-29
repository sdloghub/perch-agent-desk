import asyncio
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import agent_bridge as bridge

class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_mcp_and_each_agent_event_protocol(self):
        calls=[]
        fake=types.ModuleType('open_webui.utils.middleware')
        async def execute(body,metadata,caller,call):
            calls.append((metadata['chat_id'],call))
            return {},{'value':'memory-roundtrip'},None,None,False
        fake.execute_tool_call=execute
        old=sys.modules.get('open_webui.utils.middleware');sys.modules['open_webui.utils.middleware']=fake
        try:
            for agent_key in ('step5','gemini','codex','claude-sonnet','glm53'):
                kind=bridge.AGENTS[agent_key]['kind']
                envelopes={
                    'step':[{'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'verified-final'}],'stopReason':'stop'}},{'type':'agent_end'}],
                    'agy':[{'event':'result','result':{'status':'SUCCESS','response':'verified-final'}}],
                    'codex':[{'type':'item.completed','item':{'type':'agent_message','text':'verified-final'}},{'type':'turn.completed'}],
                    'claude':[{'type':'result','subtype':'success','is_error':False,'result':'verified-final'}],
                    'zcode':[{'type':'result','response':'verified-final','projection':{'status':'idle'}}]}
                def launch(agent,run,workspace,env,system):
                    self.assertIn('system-marker',system)
                    source="""import json,os,subprocess,sys
prompt=sys.stdin.read() if len(sys.argv)==1 else sys.argv[-1]
assert 'old-turn-marker' in prompt and 'new-turn-marker' in prompt
frames=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},{'jsonrpc':'2.0','id':2,'method':'tools/list'},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'probe_memory','arguments':{'query':'test'}}}]
r=subprocess.run([sys.executable,HELPER],input=''.join(json.dumps(x)+'\\n' for x in frames),text=True,capture_output=True,check=True)
replies=[json.loads(x) for x in r.stdout.splitlines()]
assert replies[0]['result']['serverInfo']['name']=='webui-context'
assert replies[1]['result']['tools'][0]['name']=='probe_memory'
assert 'memory-roundtrip' in str(replies[2]['result'])
for packet in ENVELOPES: print(json.dumps(packet),flush=True)
""".replace('HELPER',repr(str(bridge.ROOT/'webui_mcp.py'))).replace('ENVELOPES',repr(envelopes[kind]))
                    return [bridge.PYTHON,'-c',source],''
                with patch.object(bridge,'launch',launch):
                    output=await bridge.run_agent({'model':'local_agents.'+agent_key,'messages':[{'role':'system','content':'system-marker'},{'role':'user','content':'old-turn-marker'},{'role':'user','content':'new-turn-marker'}]},
                        {'probe_memory':{'spec':{'name':'probe_memory','description':'probe','parameters':{'type':'object','properties':{'query':{'type':'string'}}}}}},
                        {'chat_id':'offline-'+kind},max_seconds=20)
                    self.assertIn('verified-final',output);self.assertNotIn('memory-roundtrip',output)
            self.assertEqual(len(calls),5)
            self.assertEqual(len({chat for chat,_ in calls}),5)
        finally:
            if old is None:sys.modules.pop('open_webui.utils.middleware',None)
            else:sys.modules['open_webui.utils.middleware']=old

    async def test_timeout_kills_agent_and_records_failure(self):
        with patch.object(bridge,'launch',lambda *args:([bridge.PYTHON,'-c','import time;time.sleep(30)'],'')):
            with self.assertRaises(TimeoutError):
                await bridge.run_agent({'model':'local_agents.step5','messages':[]},{},{'chat_id':'offline-timeout'},max_seconds=.2)
        folder=bridge.ROOT/'agent-runs'/bridge.hashlib.sha256(b'offline-timeout').hexdigest()[:24]
        result=json.loads(max(folder.glob('*/result.json'),key=lambda p:p.stat().st_mtime).read_text())
        self.assertFalse(result['completed'])

    async def test_wrong_source_is_rejected(self):
        with self.assertRaises(ValueError):await bridge.run_agent({'model':'local_agents.unknown'},{},{})

    async def test_launch_uses_fixed_sources_and_no_global_config_write(self):
        with tempfile.TemporaryDirectory(dir=bridge.ROOT) as d:
            root=Path(d)
            for key,agent in bridge.AGENTS.items():
                run=root/key;run.mkdir();workspace=run/'workspace';workspace.mkdir()
                env=bridge.clean_env();env.update(WEBUI_TOOL_URL='http://127.0.0.1:1/tool',WEBUI_TOOL_TOKEN='test-only',WEBUI_TOOL_SPECS=str(run/'tools.json'))
                (run/'tools.json').write_text('[]')
                with patch.object(bridge,'gateway',return_value=('http://127.0.0.1:1/v1','fake-key')):
                    args,prefix=bridge.launch(agent,run,workspace,env,'system-marker')
                self.assertTrue(Path(args[0]).exists())
                if agent['kind']=='zcode':
                    data=json.loads((run/'provider.secret.json').read_text());self.assertEqual(data['config']['defaultModelSelection']['modelId'],agent['model'])
                elif agent['kind']!='step':self.assertIn(agent['model'],args)
                if agent['kind']=='codex':
                    self.assertIn('mcp_servers.webui.default_tools_approval_mode="approve"',args)
                    self.assertIn('approval_policy="never"',args)
                    self.assertIn('--sandbox',args)
                self.assertNotIn('fake-key',' '.join(args))

if __name__=='__main__':unittest.main(verbosity=2)
