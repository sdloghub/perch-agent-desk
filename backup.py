"""Consistent SQLite backup plus human-readable current-memory export."""
import datetime
import json
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent
os.umask(0o077)
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
dest = ROOT / 'backups' / stamp
dest.mkdir(parents=True)
with sqlite3.connect(f'file:{ROOT / "data/webui.db"}?mode=ro', uri=True) as src:
    with sqlite3.connect(dest / 'webui.db') as out:
        src.backup(out)
    src.row_factory = sqlite3.Row
    rows = [dict(r) for r in src.execute('SELECT id,user_id,type,path,content,meta,created_at,updated_at FROM memory ORDER BY path,created_at')]
(dest / 'memories.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
lines = ['# 记忆快照', '', '这是只读备份；修改请使用网页记忆管理。删除现有记忆不会删除历史备份。', '']
for row in rows:
    lines += [f'## {row["path"] or "未分类"} · {row["id"]}', '', f'类型：{row["type"]}；更新时间：{row["updated_at"]}', '', row['content'], '', f'来源元数据：{row["meta"]}', '']
(dest / 'memory-summary.md').write_text('\n'.join(lines))
workspace_db=ROOT/'data/workspaces.db'
if workspace_db.exists():
    with sqlite3.connect(f'file:{workspace_db}?mode=ro',uri=True) as src:
        with sqlite3.connect(dest/'workspaces.db') as out:src.backup(out)
print(f'Backup ready: {dest}')

journal_db=ROOT/'data/memory-journal.db'
if journal_db.exists():
    with sqlite3.connect(f'file:{journal_db}?mode=ro',uri=True) as src:
        with sqlite3.connect(dest/'memory-journal.db') as out:src.backup(out)
