"""Local directory registry shared by every runtime; no project files live in this DB."""
import hashlib
import os
from pathlib import Path
import sqlite3
import time
import uuid

ROOT=Path(__file__).resolve().parent

class WorkspaceError(ValueError):pass

class WorkspaceStore:
    def __init__(self,path=None):
        self.path=Path(path or os.environ.get('LOCAL_WORKSPACE_DB') or ROOT/'data/workspaces.db')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS workspace(id TEXT PRIMARY KEY,owner TEXT NOT NULL,name TEXT NOT NULL,path TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(owner,path));
            CREATE TABLE IF NOT EXISTS preference(owner TEXT PRIMARY KEY,workspace_id TEXT);
            CREATE TABLE IF NOT EXISTS binding(owner TEXT NOT NULL,chat_id TEXT NOT NULL,workspace_id TEXT,PRIMARY KEY(owner,chat_id));
            ''')
        self.path.chmod(0o600)
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;return db
    def list(self,owner):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM workspace WHERE owner=? ORDER BY name COLLATE NOCASE,id',(owner,))]
    def get(self,owner,id):
        with self.connect() as db:r=db.execute('SELECT * FROM workspace WHERE id=? AND owner=?',(id,owner)).fetchone()
        if not r:raise WorkspaceError('工作区不存在或不属于当前用户')
        return dict(r)
    @staticmethod
    def directory(path,create=False):
        p=Path(path).expanduser()
        if not p.is_absolute():raise WorkspaceError('请输入本机绝对路径')
        if create:
            try:p.mkdir(parents=True,exist_ok=True)
            except OSError as e:raise WorkspaceError('无法创建目录，请检查本机权限') from e
        try:p=p.resolve(strict=True)
        except OSError as e:raise WorkspaceError('目录不存在') from e
        if not p.is_dir():raise WorkspaceError('请选择目录，而不是文件')
        if not os.access(p,os.R_OK|os.X_OK):raise WorkspaceError('当前服务无法读取此目录')
        return p
    def register(self,owner,name,path,create=False):
        p=self.directory(path,create);name=name.strip() or p.name or str(p)
        if len(name)>100:raise WorkspaceError('名称最多 100 个字符')
        with self.connect() as db:
            old=db.execute('SELECT id FROM workspace WHERE owner=? AND path=?',(owner,str(p))).fetchone()
            id=old['id'] if old else uuid.uuid4().hex
            db.execute('INSERT INTO workspace VALUES(?,?,?,?,?) ON CONFLICT(owner,path) DO UPDATE SET name=excluded.name',(id,owner,name,str(p),int(time.time())))
        return self.get(owner,id)
    def select(self,owner,id,chat_id=None,make_default=False):
        if id:self.get(owner,id)
        with self.connect() as db:
            if chat_id:db.execute('INSERT INTO binding VALUES(?,?,?) ON CONFLICT(owner,chat_id) DO UPDATE SET workspace_id=excluded.workspace_id',(owner,chat_id,id))
            if make_default or not chat_id:db.execute('INSERT INTO preference VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET workspace_id=excluded.workspace_id',(owner,id))
        return self.selection(owner,chat_id)
    def selection(self,owner,chat_id=None,bind=False):
        with self.connect() as db:
            row=db.execute('SELECT workspace_id FROM binding WHERE owner=? AND chat_id=?',(owner,chat_id)).fetchone() if chat_id else None
            source='chat' if row is not None else 'default'
            if row is None:row=db.execute('SELECT workspace_id FROM preference WHERE owner=?',(owner,)).fetchone()
            id=row['workspace_id'] if row else None
            if bind and chat_id:
                db.execute('INSERT OR IGNORE INTO binding VALUES(?,?,?)',(owner,chat_id,id))
        return {'workspace':self.get(owner,id) if id else None,'source':source,'chat_id':chat_id}
    def resolve(self,owner,chat_id,fallback):
        selection=self.selection(owner,chat_id,bind=True);workspace=selection['workspace']
        if workspace:
            path=self.directory(workspace['path'])
            if str(path)!=workspace['path']:raise WorkspaceError('工作区路径已改变，请在网页重新登记')
        else:
            path=Path(fallback);path.mkdir(parents=True,exist_ok=True,mode=0o700)
        return path,workspace
    def remove(self,owner,id):
        self.get(owner,id)
        with self.connect() as db:
            in_use=db.execute('SELECT 1 FROM binding WHERE owner=? AND workspace_id=? UNION SELECT 1 FROM preference WHERE owner=? AND workspace_id=?',(owner,id,owner,id)).fetchone()
            if in_use:raise WorkspaceError('工作区仍被聊天或默认设置使用；先解除绑定再移除')
            db.execute('DELETE FROM workspace WHERE owner=? AND id=?',(owner,id))
    def browse(self,path=None):
        p=self.directory(path or str(Path.home()));entries=[]
        try:
            for child in p.iterdir():
                if child.name.startswith('.'):continue
                try:
                    if child.is_dir():entries.append({'name':child.name,'path':str(child.resolve())})
                except OSError:continue
        except OSError as e:raise WorkspaceError('无法列出此目录') from e
        entries.sort(key=lambda x:x['name'].casefold())
        return {'path':str(p),'parent':str(p.parent),'directories':entries[:500],'truncated':len(entries)>500}

def common_workspace(metadata,fallback=None):
    chat=str(metadata.get('chat_id') or uuid.uuid4().hex)
    owner=metadata.get('user_id') or 'local-offline'
    key=hashlib.sha256((owner+':'+chat).encode()).hexdigest()[:24]
    fallback=Path(fallback) if fallback else ROOT/'workspaces/sessions'/key
    return WorkspaceStore().resolve(owner,chat,fallback)
