"""Thin extension over the installed WebUI: authenticated local APIs and UI assets."""
from pathlib import Path
import json
import os
from urllib.parse import urlsplit

from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import FileResponse,HTMLResponse,RedirectResponse
from pydantic import BaseModel,Field
from fastapi import Query

from open_webui.main import app,SPAStaticFiles
from open_webui.env import FRONTEND_BUILD_DIR
from open_webui.utils.auth import get_verified_user
from open_webui.models.chats import Chats
from workspace_store import WorkspaceStore,WorkspaceError
from shared_memory import SharedMemory

ROOT=Path(__file__).resolve().parent
router=APIRouter(prefix='/api/local-workspaces',tags=['local-workspaces'])

def store():return WorkspaceStore()

async def guard(request:Request,user=Depends(get_verified_user)):
    # Browser requests remain same-origin and authenticated, even in single-user
    # mode. A random website must not be able to create local directories.
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
        raise HTTPException(403,'仅允许当前本机网页访问')
    if request.headers.get('sec-fetch-site')=='cross-site':raise HTTPException(403,'拒绝跨站请求')
    return user

async def own_chat(user,chat_id):
    if not chat_id or chat_id.startswith('local:'):return
    chat=await Chats.get_chat_by_id(chat_id)
    if not chat or chat.user_id!=user.id:raise HTTPException(404,'聊天不存在')

class Register(BaseModel):
    name:str=Field(default='',max_length=100)
    path:str=Field(min_length=1,max_length=4096)
    create_directory:bool=False
class Selection(BaseModel):
    workspace_id:str|None=None
    chat_id:str|None=None
    make_default:bool=False
class MemoryAdd(BaseModel):
    content:str=Field(min_length=1,max_length=20000)
    type:str='context'
    path:str|None=None
    scope:str='current'
    workspace_id:str|None=None
class MemoryOps(BaseModel):
    operations:list[dict]
    scope:str='current'
    workspace_id:str|None=None

@router.get('')
async def list_workspaces(request:Request,chat_id:str|None=None,user=Depends(guard)):
    await own_chat(user,chat_id)
    return {'workspaces':store().list(user.id),'selection':store().selection(user.id,chat_id),'home':str(Path.home())}

@router.post('')
async def register_workspace(form:Register,user=Depends(guard)):
    try:return store().register(user.id,form.name,form.path,form.create_directory)
    except (WorkspaceError,OSError) as e:raise HTTPException(400,str(e))

@router.put('/selection')
async def select_workspace(form:Selection,user=Depends(guard)):
    await own_chat(user,form.chat_id)
    try:return store().select(user.id,form.workspace_id,form.chat_id,form.make_default)
    except WorkspaceError as e:raise HTTPException(400,str(e))

@router.get('/browse')
async def browse_directories(path:str|None=None,user=Depends(guard)):
    try:return store().browse(path)
    except WorkspaceError as e:raise HTTPException(400,str(e))

@router.delete('/{id}')
async def remove_workspace(id:str,user=Depends(guard)):
    try:store().remove(user.id,id);return {'removed':True,'files_deleted':False}
    except WorkspaceError as e:raise HTTPException(409,str(e))

@router.get('/memories')
async def list_shared_memories(request:Request,workspace_id:str|None=None,scope:str='current',query:str='',user=Depends(guard)):
    try:
        entry=store().get(user.id,workspace_id) if workspace_id else None
        return await SharedMemory(request,user,entry).search(query=query,scope=scope,count=100)
    except ValueError as e:raise HTTPException(400,str(e))

@router.post('/memories')
async def add_shared_memory(request:Request,form:MemoryAdd,user=Depends(guard)):
    try:
        entry=store().get(user.id,form.workspace_id) if form.workspace_id else None
        return await SharedMemory(request,user,entry).add(form.content,form.type,form.path,form.scope)
    except ValueError as e:raise HTTPException(400,str(e))

@router.patch('/memories')
async def update_shared_memories(request:Request,form:MemoryOps,user=Depends(guard)):
    try:
        entry=store().get(user.id,form.workspace_id) if form.workspace_id else None
        return await SharedMemory(request,user,entry).update(form.operations,form.scope)
    except ValueError as e:raise HTTPException(400,str(e))

@router.get('/memory-revisions')
async def memory_revisions(memory_id:str,user=Depends(guard)):
    from memory_journal import connection
    import json
    results=[]
    with connection() as c:
        for seq,action,payload,created in c.execute('select seq,action,payload,created from revision where owner=? order by seq desc',(user.id,)):
            item=json.loads(payload)
            rows=item.get('rows',[]) if isinstance(item,dict) else []
            for row in rows:
                if row.get('id')==memory_id:results.append({'revision':seq,'created_at':created,'memory':row})
            if len(results)>=50:break
    return results

@router.get('/memory-catalog')
async def memory_catalog(request:Request,workspace_id:str|None=None,scope:str='current',query:str='',offset:int=Query(0,ge=0),limit:int=Query(40,ge=1,le=100),user=Depends(guard)):
    try:
        entry=store().get(user.id,workspace_id) if workspace_id else None
        memory=SharedMemory(request,user,entry)
        if query:
            rows=await memory.search(query=query,scope=scope,count=100)
        else:
            rows=[memory.public(m) for m in await memory.rows(scope)]
            rows.sort(key=lambda m:m['updated_at'] or 0,reverse=True)
        return {'items':rows[offset:offset+limit],'total':len(rows),'has_more':offset+limit<len(rows)}
    except ValueError as e:raise HTTPException(400,str(e))

@router.get('/overview')
async def desk_overview(request:Request,user=Depends(guard)):
    from collections import Counter
    rows=await SharedMemory(request,user).rows('all')
    groups=Counter('codex' if (m.path or '').startswith('imports/codex/') else 'workspace' if (m.path or '').startswith('workspaces/') else 'global' for m in rows)
    return {'total':len(rows),'types':dict(Counter(m.type for m in rows)),'groups':dict(groups),'workspaces':len(store().list(user.id))}

@router.get('/runtime-models')
async def runtime_models(user=Depends(guard)):
    from reasoning_config import CAPABILITIES
    return {key:{'provider':v[0],'levels':v[1]} for key,v in CAPABILITIES.items()}

@router.get('/controls.js')
async def controls_script():return FileResponse(ROOT/'perch_controls.js',media_type='application/javascript',headers={'Cache-Control':'no-cache'})

@router.get('/ui.js')
async def workspace_script():return FileResponse(ROOT/'local_workspace_ui.js',media_type='application/javascript',headers={'Cache-Control':'no-cache'})
@router.get('/ui.css')
async def workspace_style():return FileResponse(ROOT/'local_workspace_ui.css',media_type='text/css',headers={'Cache-Control':'no-cache'})

# Extend the existing SPA static handler, including direct /auth, /notes and
# /workspace entries. Assets retain the vendor handler and normal middleware.
class WorkspaceSPA(SPAStaticFiles):
    def file_response(self,full_path,stat_result,scope,status_code=200):
        if str(full_path).endswith('.html'):
            text=Path(full_path).read_text().replace('maximum-scale=1, ', '', 1)
            # Choose the requested dark theme before upstream's own theme bootstrap.
            text=text.replace('<head>', '<head><script>try{localStorage.theme="dark"}catch(e){}document.documentElement.classList.add("dark");document.documentElement.style.colorScheme="dark";</script>', 1)
            text=text.replace('</head>','<link rel="stylesheet" href="/api/local-workspaces/ui.css">\n<script defer src="/api/local-workspaces/ui.js"></script>\n<script defer src="/api/local-workspaces/controls.js"></script>\n</head>')
            return HTMLResponse(text,status_code=status_code,headers={'Cache-Control':'no-cache'})
        return super().file_response(full_path,stat_result,scope,status_code)
original=list(app.router.routes)
app.include_router(router)
desk_router=APIRouter()
@desk_router.get('/desk')
@desk_router.get('/desk/')
async def desk_index(request:Request):
    # Old desktop/bookmark links continue directly in the upstream SPA.
    chat=request.query_params.get('chat', '')
    from uuid import UUID
    try:target='/c/'+str(UUID(chat))
    except ValueError:target='/'
    return RedirectResponse(target,status_code=307)
@desk_router.get('/desk/bridge.js')
async def desk_bridge():return FileResponse(ROOT/'ui/bridge.js',media_type='application/javascript',headers={'Cache-Control':'no-cache'})
@desk_router.get('/desk/embed.css')
async def desk_embed_style():return FileResponse(ROOT/'ui/embed.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
@desk_router.get('/desk/assets/{name}')
async def desk_asset(name:str):
    path=(ROOT/'ui/dist/assets'/name).resolve()
    if path.parent!=(ROOT/'ui/dist/assets').resolve() or not path.is_file():raise HTTPException(404)
    return FileResponse(path)
app.include_router(desk_router)
new=app.router.routes[len(original):]
app.router.routes[:]=new+original
for route in original:
    if getattr(route,'name',None)=='spa-static-files':
        route.app=WorkspaceSPA(directory=FRONTEND_BUILD_DIR,html=True)
