"""Perch has its own Magpie identity; never prints gateway credentials."""
import json,os,tomllib
from pathlib import Path
from urllib.parse import urlsplit

def gateway():
    config=Path(os.environ.get('PERCH_GATEWAY_CONFIG',Path.home()/'.config/perch/gateway.json'))
    if config.exists():
        data=json.loads(config.read_text())
        if not data.get('enabled') or not data.get('api_key'):
            raise ValueError('请先在 Magpie 中启用 Perch Agent 插件连接')
        base,key=data['base_url'].rstrip('/'),data['api_key']
    else:
        # Migration path for the existing installation before plugin activation.
        data=tomllib.loads((Path.home()/'.codex/config.toml').read_text())['model_providers']['magpie']
        base,key=data['base_url'].rstrip('/'),data['experimental_bearer_token']
    url=urlsplit(base)
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.username or url.password:
        raise ValueError('Magpie gateway must stay on loopback')
    return base,key
