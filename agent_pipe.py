"""
title: 本机 Agent · 模型与来源选择
version: 1.0.0
"""
class Pipe:
    def pipes(self):
        from agent_bridge import AGENTS
        return [{'id':key,'name':value['name']} for key,value in AGENTS.items()]

    async def pipe(self,body:dict,__tools__:dict=None,__metadata__:dict=None,
                   __event_emitter__=None,__event_call__=None,__request__=None):
        from agent_bridge import run_agent
        return await run_agent(body,__tools__ or {},__metadata__ or {},
                               __event_emitter__,__event_call__,__request__)
