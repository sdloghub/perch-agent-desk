"""Shared model classification: aliases resolve to the actual provider model."""
import re

PIPE_ID = 'deepseek_harness'

def resolve_deepseek(model_id, models):
    seen = set()
    current = model_id
    while current and current not in seen:
        seen.add(current)
        model = models.get(current) or {}
        base = (model.get('info') or {}).get('base_model_id')
        if not base:
            break
        current = base
    if current == PIPE_ID:
        return None
    return current if re.search(r'(^|[/_.\-])deepseek([/_.\-]|$)', current or '', re.I) else None
