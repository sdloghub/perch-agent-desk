#!/usr/bin/env python3
"""Start the isolated, loopback-only Open WebUI instance."""
import os
from pathlib import Path
import secrets
import tomllib

ROOT = Path(__file__).resolve().parent
os.umask(0o077)
os.chdir(ROOT)
secret = ROOT / '.session-secret'
if not secret.exists():
    secret.write_text(secrets.token_urlsafe(48))
from gateway_config import gateway
base, key = gateway()
os.environ.update({
    'DATA_DIR': str(ROOT / 'data'),
    'FROM_INIT_PY': 'true',
    'PYTHONPATH': str(ROOT),
    'WEBUI_SECRET_KEY': secret.read_text().strip(),
    'OPENAI_API_BASE_URL': base,
    'OPENAI_API_KEY': key,
    'ENABLE_OLLAMA_API': 'False',
    'ENABLE_SIGNUP': 'False',
    'WEBUI_AUTH': 'False',
    'ENABLE_MEMORIES': 'True',
    'ENABLE_MEMORY_SYSTEM_CONTEXT': 'True',
    'ENABLE_MEMORY_BACKGROUND_REVIEW': 'False',
    'MEMORIES_USER_CHAR_LIMIT': '3000',
    'MEMORIES_CONTEXT_CHAR_LIMIT': '5000',
    'ENABLE_TITLE_GENERATION': 'False',
    'ENABLE_TAGS_GENERATION': 'False',
    'ENABLE_FOLLOW_UP_GENERATION': 'False',
    'OFFLINE_MODE': 'True',
    'HF_HUB_OFFLINE': '1',
    'RAG_EMBEDDING_MODEL_AUTO_UPDATE': 'False',
    'RAG_EMBEDDING_MODEL': str(ROOT / 'embedding-model'),
    'WHISPER_MODEL_AUTO_UPDATE': 'False',
    'ANONYMIZED_TELEMETRY': 'False',
    'DO_NOT_TRACK': 'True',
    'SCARF_NO_ANALYTICS': 'True',
    'CORS_ALLOW_ORIGIN': 'http://127.0.0.1:8080;http://localhost:8080',
    'DEFAULT_MODELS': '',
})
os.execv(str(ROOT / '.venv/bin/python'), ['python', '-m', 'uvicorn', 'local_server:app', '--host', '127.0.0.1', '--port', '8080'])
