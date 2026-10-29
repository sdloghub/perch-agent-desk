"""Local append-only memory revisions and import provenance, separate from retrieval."""
import json,sqlite3,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def connection():
    path=Path(os.environ.get('DATA_DIR',ROOT/'data'))/'memory-journal.db';path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=30);c.execute('create table if not exists revision (seq integer primary key, owner text, action text, payload text, created real)');c.execute('create table if not exists imported (owner text, source text, digest text, ids text, primary key(owner,source))');path.chmod(0o600);return c
def record(owner,action,payload):
    with connection() as c:c.execute('insert into revision(owner,action,payload,created) values(?,?,?,?)',(owner,action,json.dumps(payload,ensure_ascii=False,default=str),time.time()))
def imported(owner,source):
    with connection() as c:
        r=c.execute('select digest,ids from imported where owner=? and source=?',(owner,source)).fetchone();return (r[0],json.loads(r[1])) if r else None
def mark_imported(owner,source,digest,ids):
    with connection() as c:c.execute('insert or replace into imported values(?,?,?,?)',(owner,source,digest,json.dumps(ids)))
