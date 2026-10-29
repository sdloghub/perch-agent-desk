"""Minimal scoped stdio MCP transport for WebUI's bound tools; no credentials on stdout."""
import json
import os
from pathlib import Path
import sys
import urllib.request


def invoke(name, arguments):
    request = urllib.request.Request(os.environ['WEBUI_TOOL_URL'],
        data=json.dumps({'name':name,'arguments':arguments}).encode(),
        headers={'Content-Type':'application/json',
                 'Authorization':'Bearer '+os.environ['WEBUI_TOOL_TOKEN']})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main():
    specs = json.loads(Path(os.environ['WEBUI_TOOL_SPECS']).read_text())
    for line in sys.stdin:
        packet = json.loads(line)
        if 'id' not in packet:
            continue
        method = packet.get('method')
        try:
            if method == 'initialize':
                result = {'protocolVersion':packet.get('params',{}).get('protocolVersion','2024-11-05'),
                          'capabilities':{'tools':{}},'serverInfo':{'name':'webui-context','version':'1.0.0'}}
            elif method == 'tools/list':
                result = {'tools':[{'name':s['name'],'description':s.get('description',''),
                                   'inputSchema':s.get('parameters',{'type':'object','properties':{}})} for s in specs]}
            elif method == 'tools/call':
                params = packet['params']
                value = invoke(params['name'],params.get('arguments',{}))
                result = {'content':[{'type':'text','text':value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)}]}
            elif method == 'ping':
                result = {}
            else:
                raise ValueError('Unsupported MCP method')
            reply = {'jsonrpc':'2.0','id':packet['id'],'result':result}
        except Exception:
            reply = {'jsonrpc':'2.0','id':packet['id'],'error':{'code':-32603,'message':'WebUI tool failed; check local run diagnostics'}}
        print(json.dumps(reply,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    if len(sys.argv)>1:
        value=invoke(sys.argv[1],json.loads(sys.argv[2]) if len(sys.argv)>2 else {})
        print(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False))
    else:
        main()
