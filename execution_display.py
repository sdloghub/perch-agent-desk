"""Public execution progress; never turn private reasoning blocks into UI text."""
import json
import re

_SECRET = re.compile(r'(api[_-]?key|authorization|bearer|password|secret|cookie|token|credential)',re.I)
def redact(value):
    if isinstance(value,dict):return {k:('[已隐藏]' if _SECRET.search(str(k)) else redact(v)) for k,v in value.items() if str(k) not in ('thinking','reasoning','reasoning_content','signature')}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str):
        value=re.sub(r'(?i)(Bearer\s+)[\w.\-]+',r'\1[已隐藏]',value)
        value=re.sub(r'(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+',r'\1[已隐藏]',value)
        return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}\b','[已隐藏]',value)
    return value

def public_text(value,limit=6000):
    if isinstance(value,str):
        try:value=json.loads(value)
        except (ValueError,TypeError):pass
    value=redact(value)
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,default=str,indent=2)
    return text[:limit]+ ('\n[显示已截断]' if len(text)>limit else '')

class ExecutionDisplay:
    """Coarse status only: no arguments, results or model prose in chat."""
    def __init__(self,emitter,name):self.emitter=emitter;self.name=name;self.last=None
    async def show(self,label,value):
        if not self.emitter:return
        text='正在思考…'
        if '工具' in label:text='正在使用工具…' if '结果' not in label else '正在整理结果…'
        if text==self.last:return
        self.last=text
        await self.emitter({'type':'status','data':{'description':text,'done':False}})
