"""
title: DeepSeek V4.1 Flash · 来源选择
version: 1.1.0
"""
SOURCES = {
    'official': ('DeepSeek V4.1 Flash · 官方 API', 'deepseek/deepseek-flash'),
    'workbuddy': ('DeepSeek V4.1 Flash · Workbuddy', 'workbuddy/deepseek-v4.1-flash'),
}

class Pipe:
    def pipes(self):
        return [{'id': key, 'name': value[0]} for key, value in SOURCES.items()]

    async def pipe(self, body: dict, __tools__: dict = None, __metadata__: dict = None,
                   __event_emitter__=None, __event_call__=None, __request__=None):
        from harness_bridge import run_harness
        source = body.get('model', '').rsplit('.', 1)[-1]
        if source not in SOURCES:
            raise ValueError('请先选择 DeepSeek V4.1 Flash 的来源：官方 API 或 Workbuddy')
        body = {**body, '_harness_model': SOURCES[source][1]}
        return await run_harness(body, __tools__ or {}, __metadata__ or {},
                                 __event_emitter__, __event_call__, __request__)
