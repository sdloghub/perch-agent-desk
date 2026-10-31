/* Local workspace UI, independent of the selected model and WebUI SPA releases. */
(() => {
  'use strict';
  const base = '/api/local-workspaces';
  let state = null, activeChat = undefined, dialog, toolbar, memoryScope = 'current', browsing = '';
  let memoryOffset = 0, memoryRequest = 0;
  let historyPage = 1, historyRequest = 0, historyRows = [], historyQuery = '', historyTimer;
  const $ = (id) => document.getElementById(id);
  const chatId = () => location.pathname.startsWith('/c/') ? decodeURIComponent(location.pathname.slice(3)) : null;
  const element = (tag, text, cls) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  };
  async function api(path = '', method = 'GET', data, prefix = base) {
    const token = localStorage.getItem('token');
    if (!token) throw new Error('正在连接本机用户，请稍后再试');
    const response = await fetch(prefix + path, {method, headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); } catch { throw new Error('本机服务响应异常（HTTP ' + response.status + '）'); }
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '操作失败，请检查输入');
    return result;
  }
  function notice(message, error = false) {
    let node = $('lw-notice');
    if (!dialog?.open) {
      node = $('perch-toast');
      if (!node) { node = element('div', undefined, 'perch-toast'); node.id = 'perch-toast'; node.setAttribute('role','status'); document.body.append(node); }
      clearTimeout(node.hideTimer); node.hideTimer=setTimeout(()=>node.remove(),6000);
    }
    if (node) { node.textContent = message; node.classList.toggle('lw-error', error); }
  }
  function workspace() { return state?.selection?.workspace; }
  async function refresh() {
    const requestedChat = chatId();
    const data = await api(requestedChat ? '?chat_id=' + encodeURIComponent(requestedChat) : '');
    if (requestedChat !== chatId()) return;
    state = data; activeChat = requestedChat;
    renderToolbar();
    if (dialog?.open) renderSelection();
  }
  function renderToolbar() {
    if (!toolbar) return;
    const w = workspace();
    toolbar.querySelector('.lw-workspace-name').textContent = w ? w.name : '当前聊天临时目录';
    toolbar.querySelector('.lw-workspace-path').textContent = w ? w.path : '选择本机目录 · 所有 Agent 共用';
    toolbar.querySelector('button').title = w ? w.path : '建立本机工作区';
    toolbar.querySelector('button').setAttribute('aria-label', '本机工作区 ' + (w ? w.name : '当前聊天临时目录'));
  }
  async function safe(action) {
    try { await action(); } catch (e) { notice(e.message, true); }
  }
  function mount() {
    if (!['/','/c/'].some(p => p === '/' ? location.pathname === '/' : location.pathname.startsWith(p))) { toolbar?.remove(); return; }
    const input = $('chat-input');
    if (!input) return;
    if (!toolbar) {
      toolbar = element('div', undefined, 'lw-toolbar'); toolbar.id = 'local-workspace-toolbar';
      const choose = element('button', undefined, 'lw-current'); choose.type = 'button'; choose.setAttribute('aria-label', '本机工作区');
      const contextLabel = element('span', '工作区', 'lw-context-label');
      choose.append(contextLabel);
      const label = element('span', undefined, 'lw-current-label');
      label.append(element('strong', '本机工作区 · ', 'lw-workspace-name'), element('small', '', 'lw-workspace-path'));
      choose.append(label); choose.addEventListener('click', () => safe(chooseWorkspace));
      const memory = element('button', '记忆', 'lw-memory-button'); memory.type = 'button'; memory.addEventListener('click', () => safe(() => openManager('memory')));
      const history = element('button', '继续对话', 'lw-memory-button'); history.type = 'button'; history.id = 'lw-history-open'; history.setAttribute('aria-label', '继续对话'); history.addEventListener('click', () => safe(() => openManager('history')));
      const actions = element('div', undefined, 'lw-toolbar-actions'); actions.append(history, memory);
      toolbar.append(choose, actions);
    }
    // Keep the extension above the composer, outside Svelte's editable subtree.
    const host = input.closest('#message-input-container') || input.closest('form') || input.parentElement?.parentElement;
    if (host && toolbar.parentElement !== host.parentElement) host.parentElement.insertBefore(toolbar, host);
    if (activeChat !== chatId()) { activeChat = chatId(); refresh().catch(() => { activeChat = undefined; }); }
  }
  function createDialog() {
    dialog = element('dialog', undefined, 'lw-dialog'); dialog.id = 'local-workspace-dialog'; dialog.setAttribute('aria-labelledby', 'lw-heading');
    // Static markup only. All paths, names, memory content and errors use textContent.
    dialog.innerHTML = `
      <header class="lw-header"><div><h2 id="lw-heading">本机工作区</h2><p id="lw-description">同一个目录，同一份记忆，切换 Agent 继续工作。</p></div><button type="button" id="lw-close" aria-label="关闭窗口">×</button></header>
      <nav class="lw-tabs" aria-label="工作区设置"><button type="button" id="lw-history-tab">继续对话</button><button type="button" id="lw-workspace-tab">本机目录</button><button type="button" id="lw-memory-tab">共用记忆</button></nav>
      <div id="lw-notice" role="status" aria-live="polite"></div>
      <section id="lw-history-section" hidden>
        <form id="lw-history-search" class="lw-line"><input type="search" id="lw-history-query" placeholder="搜索聊天标题或内容" aria-label="搜索历史对话"><button type="submit">搜索</button></form>
        <p class="lw-hint">按最近更新排序；直接回到原对话，保留上下文、模型和工作区。</p>
        <div id="lw-history-draft" class="lw-history-draft" hidden><p>输入框有未发送的内容，仍要切换对话吗？</p><div class="lw-line"><button type="button" id="lw-history-cancel">留在当前对话</button><a id="lw-history-confirm">仍然切换</a></div></div>
        <div id="lw-history-list" aria-live="polite"></div>
        <button type="button" id="lw-history-more" hidden>加载更多</button>
      </section>
      <section id="lw-workspace-section">
        <label for="lw-select">当前聊天的工作区</label><div class="lw-line"><select id="lw-select" aria-label="当前聊天的工作区"></select><button type="button" id="lw-use">使用此工作区</button></div>
        <p id="lw-selected-path" class="lw-path"></p><label class="lw-check"><input type="checkbox" id="lw-default">新聊天也默认使用此工作区</label>
        <div class="lw-rule"></div><h3>添加本机目录</h3>
        <form id="lw-add-form"><label for="lw-path">本机绝对路径</label><div class="lw-line"><input id="lw-path" required placeholder="/Users/你的用户名/Projects/项目"><button type="button" id="lw-browse">浏览目录</button></div>
        <label for="lw-name">工作区名称</label><input id="lw-name" placeholder="留空使用目录名称" maxlength="100">
        <label class="lw-check"><input type="checkbox" id="lw-create">目录不存在时创建</label><button type="submit" class="lw-primary">添加并使用</button></form>
        <div id="lw-browser" hidden><div class="lw-line"><strong>本机目录</strong><button type="button" id="lw-up">上一级</button><button type="button" id="lw-pick">选择当前目录</button></div><p id="lw-browse-path" class="lw-path"></p><div id="lw-directories"></div></div>
        <details class="lw-manage"><summary>管理已登记的工作区</summary><div id="lw-workspace-list"></div></details>
        <p class="lw-hint">目录位于运行 WebUI 的这台 Mac。Agent 从所选目录开始执行；更换工作区在下一轮生效。</p>
      </section>
      <section id="lw-memory-section" hidden>
        <div class="lw-memory-heading"><div><h3>所有模型共用的记忆</h3><p id="lw-memory-for" class="lw-path"></p></div><select id="lw-memory-scope" aria-label="记忆范围"><option value="current">全局 + 当前工作区</option><option value="global">仅全局</option><option value="all">全部工作区</option></select></div>
        <form id="lw-memory-search" class="lw-line"><input id="lw-query" placeholder="搜索记忆" aria-label="搜索记忆"><button type="submit">搜索</button></form>
        <p id="lw-memory-count" class="lw-path" role="status"></p><div id="lw-memory-list" aria-live="polite"></div><button type="button" id="lw-memory-more" hidden>加载更多记忆</button>
        <details id="lw-new-memory"><summary>添加共用记忆</summary><form id="lw-memory-form"><label for="lw-content">记忆内容</label><textarea id="lw-content" required rows="3" placeholder="项目决定、进度或长期偏好"></textarea><div class="lw-line"><select id="lw-memory-type" aria-label="保存范围"><option value="context">当前工作区的项目记忆</option><option value="user">全局用户偏好</option></select><input id="lw-memory-path" placeholder="分类，如 decisions" aria-label="记忆分类"><button type="submit" class="lw-primary">保存记忆</button></div></form></details>
        <p class="lw-hint">记忆保存在 WebUI，供 DeepSeek、Step Code、Antigravity、Codex、Claude Code 和 Z Code 使用。全局偏好跨项目共享，项目记忆跟随工作区。</p>
      </section>`;
    const body = element('div', undefined, 'lw-dialog-body');
    for (const child of [...dialog.children].slice(2)) body.append(child);
    dialog.append(body);
    document.body.append(dialog);
    $('lw-close').onclick = () => dialog.close();
    $('lw-workspace-tab').onclick = () => switchTab('workspace');
    $('lw-memory-tab').onclick = () => safe(() => switchTab('memory'));
    $('lw-history-tab').onclick = () => safe(() => switchTab('history'));
    $('lw-history-search').onsubmit = e => { e.preventDefault(); clearTimeout(historyTimer); safe(() => loadHistory()); };
    $('lw-history-query').oninput = () => { clearTimeout(historyTimer); historyTimer = setTimeout(() => safe(() => loadHistory()), 250); };
    $('lw-history-more').onclick = () => safe(() => loadHistory(true));
    $('lw-history-cancel').onclick = () => { $('lw-history-draft').hidden = true; };
    $('lw-history-confirm').onclick = () => dialog.close();
    dialog.addEventListener('close', () => { clearTimeout(historyTimer); historyRequest++; });
    $('lw-select').onchange = () => {
      const w = (state?.workspaces || []).find(w => w.id === $('lw-select').value); $('lw-selected-path').textContent = w?.path || '使用当前聊天的独立临时目录；切换 Agent 时目录不变。';
    };
    $('lw-use').onclick = () => safe(async () => {
      await api('/selection', 'PUT', {workspace_id: $('lw-select').value || null, chat_id: chatId(), make_default: $('lw-default').checked});
      await refresh(); notice('工作区已绑定，下一条消息生效。');
    });
    $('lw-add-form').onsubmit = e => { e.preventDefault(); safe(async () => {
      const w = await api('', 'POST', {name: $('lw-name').value, path: $('lw-path').value.trim(), create_directory: $('lw-create').checked});
      await api('/selection', 'PUT', {workspace_id: w.id, chat_id: chatId(), make_default: $('lw-default').checked});
      await refresh(); $('lw-browser').hidden = true; notice('已使用工作区「' + w.name + '」。');
    }); };
    $('lw-browse').onclick = () => safe(async () => {
      if (window.perchDesktop?.chooseWorkspace) {
        const path = await window.perchDesktop.chooseWorkspace();
        if (path) $('lw-path').value = path;
      } else await browse($('lw-path').value || state.home);
    });
    $('lw-up').onclick = () => safe(() => browse($('lw-up').dataset.path));
    $('lw-pick').onclick = () => { $('lw-path').value = browsing; $('lw-browser').hidden = true; };
    $('lw-memory-more').onclick = () => safe(() => loadMemories(true));
    $('lw-memory-scope').onchange = () => { memoryScope = $('lw-memory-scope').value; safe(loadMemories); };
    $('lw-memory-search').onsubmit = e => { e.preventDefault(); safe(loadMemories); };
    $('lw-memory-form').onsubmit = e => { e.preventDefault(); safe(async () => {
      await api('/memories', 'POST', {workspace_id: workspace()?.id || null, content: $('lw-content').value, type: $('lw-memory-type').value, path: $('lw-memory-path').value || null});
      $('lw-content').value = ''; await loadMemories(); notice('已保存；切换模型后也可检索。');
    }); };
  }
  async function chooseWorkspace() {
    if (!window.perchDesktop?.chooseWorkspace) return openManager('workspace');
    const path = await window.perchDesktop.chooseWorkspace();
    if (!path) return;
    await refresh();
    const w = (state?.workspaces || []).find(w=>w.path===path) || await api('', 'POST', {path});
    await api('/selection', 'PUT', {workspace_id: w.id, chat_id: chatId(), make_default: false});
    await refresh();
    notice('已切换到工作区「' + w.name + '」。');
  }
  async function openManager(section) {
    if (!dialog) createDialog();
    await refresh(); notice(''); renderSelection();
    if (!dialog.open) dialog.showModal();
    await switchTab(section);
    if (section === 'history') $('lw-history-query').focus();
  }
  async function switchTab(section) {
    $('lw-workspace-section').hidden = section !== 'workspace'; $('lw-memory-section').hidden = section !== 'memory';
    $('lw-history-section').hidden = section !== 'history';
    $('lw-history-tab').classList.toggle('lw-active', section === 'history');
    for (const tab of ['history', 'workspace', 'memory']) $('lw-' + tab + '-tab').setAttribute('aria-pressed', String(tab === section));
    $('lw-heading').textContent = section === 'history' ? '继续历史对话' : section === 'memory' ? '共用记忆' : '本机工作区';
    $('lw-history-draft').hidden = true;
    $('lw-description').textContent = section === 'history' ? '找到上次的话题，接着聊。' : section === 'memory' ? '管理长期偏好与项目进度，供所有 Agent 共用。' : '为当前对话选择本机目录，切换 Agent 后继续使用。';
    $('lw-workspace-tab').classList.toggle('lw-active', section === 'workspace'); $('lw-memory-tab').classList.toggle('lw-active', section === 'memory');
    if (section === 'memory') await loadMemories();
    if (section === 'history') await loadHistory();
  }
  async function loadHistory(more = false) {
    const query = $('lw-history-query').value.trim(), request = ++historyRequest;
    more = more && query === historyQuery;
    const page = more ? historyPage + 1 : 1;
    const list = $('lw-history-list'), button = $('lw-history-more');
    button.disabled = true; notice('正在读取历史对话…');
    try {
      const params = new URLSearchParams({page: String(page)});
      if (query) params.set('text', query);
      else { params.set('include_pinned', 'true'); params.set('include_folders', 'true'); }
      const rows = await api('/' + (query ? 'search' : 'list') + '?' + params, 'GET', undefined, '/api/v1/chats');
      if (request !== historyRequest || query !== $('lw-history-query').value.trim()) return;
      historyRows = more ? [...new Map([...historyRows, ...rows].map(row => [row.id, row])).values()] : rows;
      historyPage = page; historyQuery = query; list.replaceChildren(); notice('');
      if (!historyRows.length) list.append(element('p', query ? '没有找到相关对话，试试其他关键词。' : '还没有历史对话。发送消息后会保存在这里。', 'lw-empty'));
      for (const row of historyRows) {
        const link = element('a', undefined, 'lw-history-row'); link.href = '/c/' + encodeURIComponent(row.id);
        const label = element('div', undefined, 'lw-history-label');
        label.append(element('strong', row.title || '未命名对话'));
        const date = new Date(row.updated_at * 1000);
        label.append(element('small', (row.id === chatId() ? '当前对话 · ' : '') + (row.archived ? '已归档 · ' : '') + (Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}))));
        if (row.snippet) label.append(element('p', row.snippet, 'lw-history-snippet'));
        link.append(label, element('span', row.id === chatId() ? '返回' : '继续 →', 'lw-history-go'));
        link.addEventListener('click', e => {
          if (row.id === chatId()) { e.preventDefault(); dialog.close(); $('chat-input')?.focus(); return; }
          const input = $('chat-input');
          if ((input?.innerText || input?.value || '').trim()) {
            e.preventDefault(); $('lw-history-confirm').href = link.href;
            $('lw-history-draft').hidden = false; $('lw-history-cancel').focus(); return;
          }
          dialog.close();
        });
        list.append(link);
      }
      button.hidden = rows.length < 60;
    } catch (e) {
      if (request !== historyRequest) return;
      if (!more) { historyRows = []; list.replaceChildren(element('p', '读取失败，请重新搜索或稍后再试。', 'lw-empty')); button.hidden = true; }
      throw e;
    } finally { if (request === historyRequest) button.disabled = false; }
  }
  function renderSelection() {
    const select = $('lw-select'); if (!select) return;
    select.replaceChildren(new Option('当前聊天临时目录（所有 Agent 共用）', ''));
    for (const w of state.workspaces) select.add(new Option(w.name, w.id));
    select.value = workspace()?.id || ''; select.dispatchEvent(new Event('change'));
    const list = $('lw-workspace-list'); list.replaceChildren();
    if (!state.workspaces.length) list.append(element('p', '尚未登记本机目录。', 'lw-hint'));
    for (const w of state.workspaces) {
      const row = element('div', undefined, 'lw-registry-row'); const label = element('div'); label.append(element('strong', w.name), element('small', w.path, 'lw-path'));
      const remove = element('button', '移除登记'); remove.type = 'button'; remove.onclick = () => safe(async () => { await api('/' + w.id, 'DELETE'); await refresh(); notice('已移除登记，本机文件未删除。'); });
      row.append(label, remove); list.append(row);
    }
  }
  async function browse(path) {
    const data = await api('/browse?path=' + encodeURIComponent(path)); browsing = data.path;
    $('lw-browser').hidden = false; $('lw-browse-path').textContent = data.path; $('lw-up').dataset.path = data.parent;
    const list = $('lw-directories'); list.replaceChildren();
    if (!data.directories.length) list.append(element('p', '此目录没有可见的子目录。', 'lw-hint'));
    for (const folder of data.directories) { const button = element('button', '▱  ' + folder.name); button.type = 'button'; button.onclick = () => safe(() => browse(folder.path)); list.append(button); }
    if (data.truncated) list.append(element('p', '仅显示前 500 个目录，可直接输入路径。', 'lw-hint'));
  }
  async function loadMemories(more = false) {
    more = more === true;
    const request = ++memoryRequest;
    const offset = more ? memoryOffset : 0;
    const moreButton = $('lw-memory-more'); moreButton.disabled = true;
    notice('正在读取记忆…');
    $('lw-memory-for').textContent = workspace() ? workspace().name + ' · ' + workspace().path : '当前聊天未绑定项目；使用全局记忆';
    const params = new URLSearchParams({scope: memoryScope, query: $('lw-query').value}); if (workspace()) params.set('workspace_id', workspace().id);
    params.set('offset', String(offset)); params.set('limit', '30');
    let result;
    try { result = await api('/memory-catalog?' + params); }
    finally { if (request === memoryRequest) moreButton.disabled = false; }
    if (request !== memoryRequest) return;
    notice('');
    const rows = result.items; memoryOffset = offset + rows.length;
    moreButton.hidden = !result.has_more;
    $('lw-memory-count').textContent = '已显示 ' + memoryOffset + ' / ' + result.total + ' 条记忆';
    const list = $('lw-memory-list'); if (!more) list.replaceChildren();
    if (!rows.length) list.append(element('p', '这个范围还没有记忆。可在下方添加，或在聊天里说“请记住”。', 'lw-empty'));
    for (const m of rows) {
      const card = element('article', undefined, 'lw-memory-card');
      const source = m.path?.startsWith('imports/codex/') ? 'Codex 导入' : m.type === 'user' ? '全局偏好' : '项目 / 上下文';
      const category = m.path ? m.path.split('/').slice(-2).join('/') : '未分类';
      const meta = element('small', source + ' · ' + category, 'lw-memory-meta'); meta.title = m.path || ''; card.append(meta);
      const content = element('p', m.content);
      const disclosure = element('details', undefined, 'lw-memory-content');
      const excerpt = m.content.split('\n').filter(line => !/^(Codex 导入资料|来源[:：]|SHA256[:：]|thread_id:|updated_at:|rollout_path:|cwd:|# |---$|name:|description:)/.test(line.trim())).join(' ').replace(/\s+/g, ' ').trim() || m.content;
      const preview = element('summary', excerpt.slice(0, 120) + (excerpt.length > 120 ? '…' : ''));
      disclosure.append(preview, content); card.append(disclosure);
      const actions = element('div', undefined, 'lw-memory-actions');
      const edit = element('button', '编辑'); edit.type = 'button'; edit.onclick = () => {
        const textarea = element('textarea'); textarea.value = m.content; textarea.rows = 4; disclosure.open = true; content.replaceWith(textarea); edit.hidden = true;
        const save = element('button', '保存'); save.type = 'button'; save.onclick = () => safe(async () => { await api('/memories', 'PATCH', {workspace_id: m.path?.match(/^workspaces\/([^/]+)/)?.[1] || workspace()?.id || null, operations: [{action: 'replace', id: m.id, content: textarea.value}]}); await loadMemories(); notice('修改已保存，所有 Agent 下次读取时生效。'); });
        const cancel = element('button', '取消'); cancel.type = 'button'; cancel.onclick = () => safe(loadMemories); actions.prepend(save, cancel);
      };
      const remove = element('button', '删除'); remove.type = 'button'; remove.onclick = () => {
        remove.hidden = true; const hint = element('span', '删除记忆？原聊天保留。');
        const confirm = element('button', '确认删除'); confirm.type = 'button'; confirm.onclick = () => safe(async () => {
          await api('/memories', 'PATCH', {workspace_id: m.path?.match(/^workspaces\/([^/]+)/)?.[1] || workspace()?.id || null, operations: [{action: 'remove', id: m.id}]});
          await loadMemories(); notice('记忆已删除；原聊天和历史备份保留。');
        });
        const cancel = element('button', '取消'); cancel.type = 'button'; cancel.onclick = () => safe(loadMemories); actions.prepend(hint, confirm, cancel);
      };
      actions.append(edit, remove); card.append(actions); list.append(card);
    }
  }
  let scheduled = false;
  new MutationObserver(() => { if (!scheduled) { scheduled = true; requestAnimationFrame(() => { scheduled = false; mount(); }); } }).observe(document.documentElement, {childList: true, subtree: true});
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh().catch(() => {}); });
  // Svelte navigation can reuse DOM nodes; URL changes must refresh workspace state.
  for (const method of ['pushState','replaceState']) {
    const original=history[method];
    history[method]=function(...args){const result=original.apply(this,args);window.dispatchEvent(new Event('perch:navigate'));return result;};
  }
  window.addEventListener('popstate',()=>window.dispatchEvent(new Event('perch:navigate')));
  window.addEventListener('perch:navigate',mount);
  mount();
})();
