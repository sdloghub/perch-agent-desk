/* Enhance the original WebUI selector; selection still belongs to upstream. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let capabilities = {}, loading = false, group = null, currentList = null, scheduled = false;
  const labels = {default:'自动',off:'关闭',low:'低',medium:'中',high:'高',xhigh:'很高',max:'最高'};
  const key = id => (id || '').split('.').pop();
  const provider = id => capabilities[key(id)]?.provider || '其他';
  const make = (tag,text,cls) => { const el=document.createElement(tag); if(text)el.textContent=text;if(cls)el.className=cls;return el; };
  const selected = () => {
    const label=$('model-selector-model-button')?.getAttribute('aria-label') || '';
    return Object.keys(capabilities).find(id => {
      const names={official:'官方 API',workbuddy:'DeepSeek V4.1 Flash · Workbuddy',step5:'Step Code',gemini:'Antigravity',codex:'Codex',glm53:'GLM 5.3 ·',glm53flash:'GLM 5.3 Flash', 'claude-sonnet':'Sonnet','claude-opus':'Opus','claude-haiku':'Haiku','claude-fable':'Fable'};
      return names[id] && label.includes(names[id]);
    });
  };
  const storageKey = model => 'perch:effort:' + (location.pathname.startsWith('/c/') ? location.pathname : 'new') + ':' + model;
  function choice(model) { try { return localStorage.getItem(storageKey(model)) || localStorage.getItem('perch:effort:default:'+model) || 'default'; } catch { return 'default'; } }
  function decorateMenu() {
    const list=$('model-selector-list'); if(!list)return;
    if(list!==currentList){currentList=list;group=null;}
    let panel=$('perch-provider-panel');
    if(!panel || panel.nextElementSibling!==list){panel?.remove();panel=make('div',null,'perch-provider-panel');panel.id='perch-provider-panel';list.before(panel);}
    const options=[...list.querySelectorAll('[role="option"][data-value]')];
    const query=$('model-search-input')?.value.trim();
    const signature=JSON.stringify([group,query,options.map(o=>o.dataset.value)]);
    if(panel.dataset.signature===signature)return;
    panel.dataset.signature=signature;panel.replaceChildren();
    const searching=!!query;
    list.classList.toggle('perch-provider-stage',!group&&!searching);
    options.forEach(o=>o.classList.toggle('perch-model-hidden',!searching&&(!group||provider(o.dataset.value)!==group)));
    if(searching){panel.append(make('p','所有供应商的搜索结果','perch-menu-caption'));return;}
    if(group){
      const back=make('button','‹ 供应商','perch-provider-back');back.type='button';
      back.onclick=()=>{group=null;panel.dataset.signature='';decorateMenu();panel.querySelector('button')?.focus();};
      panel.append(back,make('strong',group,'perch-menu-title'));return;
    }
    panel.append(make('p','选择供应商','perch-menu-caption'));
    const providers=[...new Set(options.map(o=>provider(o.dataset.value)))];
    for(const name of providers){
      const b=make('button',null,'perch-provider-row');b.type='button';
      b.append(make('span',name),make('small',options.filter(o=>provider(o.dataset.value)===name).length+' 个模型 / 来源  ›'));
      b.onclick=()=>{group=name;panel.dataset.signature='';decorateMenu();options.find(o=>provider(o.dataset.value)===name)?.focus();};panel.append(b);
    }
  }
  function mount() {
    if(!Object.keys(capabilities).length){
      if(loading||!localStorage.getItem('token'))return;loading=true;
      fetch('/api/local-workspaces/runtime-models',{headers:{Authorization:'Bearer '+localStorage.getItem('token')}})
        .then(r=>{if(!r.ok)throw Error(r.status);return r.json();}).then(data=>{capabilities=data;mount();}).catch(()=>{}).finally(()=>{loading=false;});return;
    }
    decorateMenu();
    const welcome = location.pathname === '/' && [...document.querySelectorAll('h2')].find(e=>!e.closest('#sidebar') && e.textContent.includes(' · '));
    if (welcome && !$('perch-welcome')) {
      const original = welcome.parentElement;
      original.classList.add('perch-upstream-welcome');
      const intro=make('header',null,'perch-welcome');intro.id='perch-welcome';
      const wordmark=make('div',null,'perch-wordmark');
      const mark=make('span',null,'perch-mark');mark.ariaHidden='true';
      mark.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M12 21v-6m0-2v-5"/><path d="M12 13 8 9m4 4 4-4"/><path d="M8 9 5.5 6.5M16 9l2.5-2.5"/><circle cx="12" cy="4.8" r="1.3" fill="currentColor" stroke="none"/><circle cx="5.5" cy="6.5" r=".8" fill="currentColor" stroke="none"/><circle cx="18.5" cy="6.5" r=".8" fill="currentColor" stroke="none"/></svg>';
      wordmark.append(mark,make('span','Perch · 栖'));
      intro.append(wordmark,make('h1','从这里，继续。'),make('p','一个工作空间，连接你的模型与记忆。'));
      original.before(intro);
    }
    if(location.pathname!=='/'){ $('perch-welcome')?.remove(); }
    const suggestions=$('suggestions-heading');
    if (suggestions) suggestions.parentElement.classList.add('perch-upstream-suggestions');
    const list=document.querySelector('[aria-labelledby="suggestions-heading"]');
    if(list && !$('perch-shortcuts')) {
      const links=make('div',null,'perch-shortcuts');links.id='perch-shortcuts';
      for(const [title,description,target] of [['选择工作空间','从本机项目开始','.lw-current'],['继续对话','回到上次的进度','#lw-history-open'],['查看记忆','管理共用的上下文','.lw-memory-button:not(#lw-history-open)']]){
        const b=make('button');b.type='button';b.append(make('strong',title),make('span',description));b.onclick=()=>document.querySelector(target)?.click();links.append(b);
      }
      list.before(links);
    }
    const toolbar=$('local-workspace-toolbar'); if(!toolbar)return;
    let control=$('perch-effort');
    if(!control){
      const label=make('label',null,'perch-effort');label.append(make('span','思考'));
      control=make('select');control.id='perch-effort';control.setAttribute('aria-label','思考等级');label.append(control);
      toolbar.querySelector('.lw-toolbar-actions').prepend(label);
      control.onchange=()=>{try{localStorage.setItem(storageKey(control.dataset.model),control.value);localStorage.setItem('perch:effort:default:'+control.dataset.model,control.value);}catch{} };
    }
    const model=selected(),levels=capabilities[model]?.levels||[];
    const stamp=(model||'')+':'+location.pathname;
    if(control.dataset.stamp!==stamp){
      control.replaceChildren();for(const value of ['default',...levels]){const o=make('option',labels[value]);o.value=value;control.append(o);}
      control.dataset.model=model||'';control.dataset.stamp=stamp;
      const saved=choice(model);control.value=['default',...levels].includes(saved)?saved:'default';control.disabled=!model;
      control.title='仅控制后续请求的推理强度；自动使用模型默认值';
    }
  }
  // Add the explicit per-chat/per-model setting only to a chat inference request.
  const originalFetch=window.fetch.bind(window);
  window.fetch=async function(input,init){
    const url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
    if(url.origin===location.origin && /\/api\/(?:v1\/)?chat\/completions$/.test(url.pathname)){
      const request=new Request(input instanceof Request ? input.clone() : input,init);
      if(request.method==='POST'){
        let body;
        try { body=await request.clone().json(); } catch { return originalFetch(request); }
        const model=key(body.model);const effort=choice(model);
        if(effort!=='default'&&capabilities[model]?.levels.includes(effort)){
          body.params={...(body.params||{}),reasoning_effort:effort};
          body.reasoning_effort=effort;
          return originalFetch(new Request(request,{body:JSON.stringify(body)}));
        }
      }
      return originalFetch(request);
    }
    return originalFetch(input,init);
  };
  document.addEventListener('input',e=>{if(e.target.id==='model-search-input')requestAnimationFrame(decorateMenu);});
  document.addEventListener('keydown',e=>{
    if(e.isComposing || e.keyCode===229)return;
    const list=$('model-selector-list'), panel=$('perch-provider-panel');
    if(!list||!panel||!['ArrowDown','ArrowUp','Home','End','Enter'].includes(e.key))return;
    const searching=!!$('model-search-input')?.value.trim();
    const back=panel.querySelector('.perch-provider-back');
    const candidates=group||searching?[...(back&&!searching?[back]:[]),...list.querySelectorAll('[role="option"]:not(.perch-model-hidden)')]:[...panel.querySelectorAll('.perch-provider-row')];
    if(!candidates.length)return;
    let index=candidates.indexOf(document.activeElement);
    if(index<0 && (document.activeElement?.id!=='model-search-input'||!['ArrowDown','ArrowUp'].includes(e.key)))return;
    e.preventDefault();e.stopImmediatePropagation();
    if(e.key==='Enter'){candidates[index].click();return;}
    index=e.key==='Home'?0:e.key==='End'?candidates.length-1:index<0?(e.key==='ArrowUp'?candidates.length-1:0):(index+(e.key==='ArrowUp'?-1:1)+candidates.length)%candidates.length;
    candidates[index].focus();
  },true);
  new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;mount();});}}).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['aria-label']});
  window.addEventListener('perch:navigate',mount);
  mount();
})();
