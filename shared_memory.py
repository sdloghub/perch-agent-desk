"""One memory contract for all models: Open WebUI rows, with global/project scope."""
import json
from pathlib import PurePosixPath

MEMORY_NAMES={'search_memories','add_memory','update_memory','replace_memory_content','delete_memory','list_memory_paths','read_memory_path'}

class SharedMemory:
    def __init__(self,request,user,workspace=None):
        self.request=request;self.user=user;self.workspace=workspace
        self.prefix='workspaces/'+workspace['id'] if workspace else None
    def allowed(self,memory,scope='current'):
        path=memory.path or ''
        if scope=='all':return True
        project=path.startswith('workspaces/')
        if scope=='global':return not project
        return not project or bool(self.prefix and (path==self.prefix or path.startswith(self.prefix+'/')))
    async def rows(self,scope='current'):
        from open_webui.models.memories import Memories
        if scope not in ('current','global','all'):raise ValueError('scope 必须为 current/global/all')
        return [m for m in await Memories.get_memories_by_user_id(self.user.id) if self.allowed(m,scope)]
    @staticmethod
    def public(m):
        return {'id':m.id,'type':m.type,'path':m.path,'content':m.content,'created_at':m.created_at,'updated_at':m.updated_at}
    def address(self,path,type,scope):
        if scope not in ('current','global'):raise ValueError('写入 scope 必须为 current/global')
        path=(path or ('profile/preferences' if type=='user' else 'notes')).strip('/')
        if '..' in PurePosixPath(path).parts:raise ValueError('记忆路径不能包含 ..')
        if type=='user' and path.startswith('workspaces/'):
            raise ValueError('用户偏好应保存在全局分类，不使用工作区路径')
        if path.startswith('workspaces/'):
            if not self.prefix or not (path==self.prefix or path.startswith(self.prefix+'/')):raise ValueError('不能写入其他工作区的记忆路径')
            return path
        if type=='context' and scope=='current' and self.prefix:return self.prefix+'/'+path
        return path
    async def search(self,query='',count=20,type='all',path=None,memory_id=None,scope='current'):
        from open_webui.utils.memory import search_memory_rows
        rows=await self.rows(scope)
        # Relative project paths are resolved just like writes.
        if path and self.prefix and scope=='current' and not path.startswith('workspaces/'):
            path=self.prefix+'/'+path.strip('/')
        candidates=search_memory_rows(rows,query=query or None,memory_type=type,path=path,memory_id=memory_id,limit=100)
        # Fuse lexical and semantic ranks, then enforce the same scope again.
        if query and not memory_id:
            from open_webui.routers.memories import query_memory,QueryMemoryForm
            allowed={m.id:m for m in rows if type=='all' or m.type==type}
            if path:
                allowed={m.id:m for m in search_memory_rows(list(allowed.values()),path=path,limit=100)}
            try:
                result=await query_memory(self.request,QueryMemoryForm(content=query,k=100),self.user)
                ids=(result.ids or [[]])[0]
                similarities=(result.distances or [[]])[0]
                threshold=max(0.70,(max(similarities) if similarities else 1)-0.04)
                scores={m.id:1/(30+i) for i,m in enumerate(candidates)}
                for i,id in enumerate(ids):
                    if i<12 and i<len(similarities) and similarities[i]>=threshold and id in allowed:scores[id]=scores.get(id,0)+1/(30+i)
                known={**allowed,**{m.id:m for m in candidates}}
                candidates=[known[id] for id in sorted(scores,key=lambda id:(-scores[id],id))]
            except Exception:
                # Offline index unavailable: lexical recall still works.
                pass
        return [self.public(m) for m in candidates[:max(1,min(count,100))]]

    async def add(self,content,type='context',path=None,scope='current'):
        from open_webui.routers.memories import add_memory,AddMemoryForm
        if type not in ('user','context'):raise ValueError('type 必须为 user/context')
        if not content.strip():raise ValueError('记忆内容不能为空')
        resolved=self.address(path,type,scope)
        for existing in await self.rows(scope):
            if existing.type==type and existing.path==resolved and ' '.join(existing.content.split())==' '.join(content.split()):return self.public(existing)
        m=await add_memory(self.request,AddMemoryForm(content=content,type=type,path=self.address(path,type,scope)),self.user)
        from memory_journal import record
        record(self.user.id,'add',self.public(m))
        return self.public(m)
    async def update(self,operations,scope='current'):
        if scope not in ('current','global'):raise ValueError('写入 scope 必须为 current/global')
        from open_webui.routers.memories import update_memories,UpdateMemoriesForm
        rows={m.id:m for m in await self.rows(scope)};normalized=[]
        for op in operations:
            op=dict(op);action=op.get('action')
            if action!='add' and op.get('id') not in rows:raise ValueError('记忆不属于当前可见范围')
            if action=='add':op['path']=self.address(op.get('path'),op.get('type','context'),scope)
            elif 'path' in op:op['path']=self.address(op['path'],op.get('type') or rows[op['id']].type,scope)
            if action in ('replace','move'):
                # WebUI's validated operation includes null defaults. Preserve
                # scope/type explicitly when only the content was edited.
                op.setdefault('path',rows[op['id']].path)
                op.setdefault('type',rows[op['id']].type)
            normalized.append(op)
        from memory_journal import record
        record(self.user.id,'before_update',{'operations':normalized,'rows':[self.public(rows[o['id']]) for o in normalized if o.get('id') in rows]})
        result=await update_memories(self.request,UpdateMemoriesForm(operations=normalized,source='tool'),self.user)
        record(self.user.id,'after_update',result)
        return result
    async def context(self,query=""):
        rows=await self.rows();rows.sort(key=lambda m:(m.updated_at or 0),reverse=True)
        if query:
            relevant=await self.search(query=query,count=30)
            rank={m['id']:i for i,m in enumerate(relevant)}
            rows.sort(key=lambda m:(rank.get(m.id,1000),-(m.updated_at or 0)))
        users=[self.public(m) for m in rows if m.type=='user'];projects=[self.public(m) for m in rows if self.prefix and (m.path or '').startswith(self.prefix+'/')];others=[self.public(m) for m in rows if m.type!='user' and not (self.prefix and (m.path or '').startswith(self.prefix+'/'))]
        parts=[]
        # Favor current project records; user preferences are shared across projects.
        for label,items,budget in [('全局用户记忆',users,3000),('当前工作区记忆',projects,4000),('通用上下文记忆',others,1000)]:
            texts=[];used=0
            for item in items:
                line=json.dumps(item,ensure_ascii=False)
                if used+len(line)>budget:continue
                texts.append(line);used+=len(line)
            if texts:parts.append(label+'\n'+'\n'.join(texts))
        return '\n\n'.join(parts)
    def tools(self):
        def spec(name,description,properties,required=()):
            return {'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required)}}
        string=lambda desc:{'type':'string','description':desc}
        scope={'type':'string','enum':['current','global','all'],'description':'current：全局和当前工作区；global：仅全局；all：显式检索全部工作区'}
        async def search_memories(**args):return json.dumps(await self.search(**args),ensure_ascii=False)
        async def add_memory(**args):return json.dumps(await self.add(**args),ensure_ascii=False)
        async def update_memory(**args):return json.dumps(await self.update(**args),ensure_ascii=False)
        async def replace_memory_content(memory_id,content,type=None,path=None,scope='current'):
            op={'action':'replace','id':memory_id,'content':content}
            if type:op['type']=type
            if path is not None:op['path']=path
            return json.dumps(await self.update([op],scope),ensure_ascii=False)
        async def delete_memory(memory_id,scope='current'):return json.dumps(await self.update([{'action':'remove','id':memory_id}],scope),ensure_ascii=False)
        async def list_memory_paths(query='',type='all',count=100,scope='current'):
            rows=await self.search(query,count,type,scope=scope);return json.dumps(sorted(set(m['path'] or '' for m in rows)),ensure_ascii=False)
        async def read_memory_path(path,type='all',include_children=True,count=50,scope='current'):
            rows=await self.search(count=count,type=type,path=path,scope=scope)
            if not include_children:rows=[m for m in rows if m['path']==path or (self.prefix and m['path']==self.prefix+'/'+path.strip('/'))]
            return json.dumps(rows,ensure_ascii=False)
        funcs={f.__name__:f for f in [search_memories,add_memory,update_memory,replace_memory_content,delete_memory,list_memory_paths,read_memory_path]}
        search_props={'query':string('内容关键词；留空可浏览'),'count':{'type':'integer'},'type':{'type':'string','enum':['user','context','all']},'path':string('可选记忆路径'),'memory_id':string('可选精确记忆 ID'),'scope':scope}
        write_scope={**scope,'enum':['current','global']}
        definitions=[spec('search_memories','跨模型共用的 WebUI 记忆检索。默认只搜索全局及当前工作区。',search_props),spec('add_memory','保存到共用 WebUI 记忆。用户偏好全局保存，context 默认写入当前工作区。',{'content':string('内容，注明日期和来源'),'type':{'type':'string','enum':['user','context']},'path':string('相对分类路径，如 decisions'),'scope':write_scope},['content']),spec('update_memory','批量增改删除共用 WebUI 记忆；修改前先检索 ID。',{'operations':{'type':'array','items':{'type':'object','properties':{'action':{'type':'string','enum':['add','replace','remove','move']},'id':string('已有记忆 ID'),'content':string('内容'),'type':{'type':'string','enum':['user','context']},'path':string('相对路径')},'required':['action']}},'scope':write_scope},['operations']),spec('replace_memory_content','更正已有记忆内容，其他 harness 下次立即可读。',{'memory_id':string('记忆 ID'),'content':string('新内容'),'type':{'type':'string','enum':['user','context']},'path':string('分类路径'),'scope':write_scope},['memory_id','content']),spec('delete_memory','删除指定记忆，不删除原聊天。',{'memory_id':string('记忆 ID'),'scope':write_scope},['memory_id']),spec('list_memory_paths','浏览当前可见记忆分类。',{k:v for k,v in search_props.items() if k in ('query','type','count','scope')}),spec('read_memory_path','读取共用记忆分类。',{'path':string('分类路径'),'type':{'type':'string','enum':['user','context','all']},'include_children':{'type':'boolean'},'count':{'type':'integer'},'scope':scope},['path'])]
        return {d['name']:{'tool_id':'shared-memory:'+d['name'],'type':'builtin','spec':d,'callable':funcs[d['name']]} for d in definitions}
