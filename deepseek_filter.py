"""
title: DeepSeek 自动 Harness 路由
version: 1.0.0
"""
from deepseek_route import resolve_deepseek, PIPE_ID

class Filter:
    async def inlet(self, body: dict, __request__=None, __user__=None) -> dict:
        original = body.get('model', '')
        if original == PIPE_ID or original.startswith(PIPE_ID + '.'):
            return body
        target = resolve_deepseek(original, __request__.app.state.MODELS)
        if target:
            # Apply the original workspace model's system/params before switching
            # providers. WebUI continues to own memory injection and tool binding.
            from open_webui.models.models import Models
            from open_webui.models.users import UserModel
            from open_webui.utils.payload import apply_system_prompt_to_body, apply_model_params_to_body_openai
            info = await Models.get_model_by_id(original)
            if info:
                params = info.params.model_dump(exclude_none=True)
                system = params.pop('system', None)
                body = apply_model_params_to_body_openai(params, body)
                if system:
                    body = await apply_system_prompt_to_body(system, body, body.get('metadata', {}), UserModel(**__user__))
            body['_harness_model'] = target
            body['_harness_original_model'] = original
            body['model'] = PIPE_ID
        return body
