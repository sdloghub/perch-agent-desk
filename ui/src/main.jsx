import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  Theme,
  Button,
  IconButton,
  TextField,
  Select,
  Dialog,
  AlertDialog,
  Spinner,
} from "@radix-ui/themes";
import {
  Plus,
  ChatCircle,
  Brain,
  Folder,
  ArrowRight,
  ArrowLeft,
  MagnifyingGlass,
  Sun,
  Moon,
  SidebarSimple,
  X,
  ArrowClockwise,
  PencilSimple,
  Trash,
  Check,
  ArrowSquareOut,
} from "@phosphor-icons/react";
import "@radix-ui/themes/styles.css";
import "./style.css";
const api = async (path, body, method) => {
  const r = await fetch(path, {
    method: method || (body ? "POST" : "GET"),
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.token || ""}`,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  let d = await r.json();
  if (!r.ok)
    throw Error(
      typeof d.detail === "string" ? d.detail : `请求失败 (${r.status})`,
    );
  return d;
};
function memoryTitle(m) {
  const lines = m.content.split("\n");
  if ((m.path || "").startsWith("imports/codex/"))
    return (
      lines.find((x) => /^#{1,3} /.test(x))?.replace(/^#+\s*/, "") ||
      m.path.replace(/\/L\d+$/, "").replace(/^.*\//, "").replace(/\.md$/, "")
    );
  return lines.find((x) => x.trim())?.replace(/^#+\s*/, "") || "记忆记录";
}
function App() {
  const initial = new URLSearchParams(location.search).get("chat");
  const [ready, R] = useState(false),
    [error, E] = useState(""),
    [dark, D] = useState(localStorage.perchTheme === "dark"),
    [page, P] = useState("chat"),
    [mobile, M] = useState(false),
    [chat, C] = useState(initial),
    [src, S] = useState(initial ? `/c/${encodeURIComponent(initial)}` : "/"),
    [title, T] = useState("新对话"),
    [model, MO] = useState("选择 Agent"),
    [draft, DR] = useState(false),
    [pending, PN] = useState(null),
    [history, H] = useState([]),
    [query, Q] = useState(""),
    [historyPage, HP] = useState(1),
    [more, HM] = useState(false),
    [loading, L] = useState(false),
    [historyError, HE] = useState(""),
    [spaces, WS] = useState([]),
    [selection, SE] = useState(null),
    [manager, MG] = useState(false),
    [path, PATH] = useState(""),
    [name, N] = useState(""),
    [overview, O] = useState(null),
    [memories, MM] = useState([]),
    [mq, MQ] = useState(""),
    [scope, SC] = useState("all"),
    [offset, OFF] = useState(0),
    [memTotal, MT] = useState(0),
    [memMore, MMO] = useState(false),
    [memBusy, MB] = useState(false),
    [memError, ME] = useState(""),
    [edit, ED] = useState(null),
    [editText, ET] = useState(""),
    [remove, RM] = useState(null),
    [saving, SV] = useState(false);
  const frame = useRef(null),
    sequence = useRef(0),
    memSequence = useRef(0);
  const send = (type, extra = {}) =>
    frame.current?.contentWindow?.postMessage(
      { type, ...extra },
      location.origin,
    );
  useEffect(() => {
    api("/api/v1/auths/signin", { email: "", password: "" })
      .then((d) => {
        if (d.token) localStorage.token = d.token;
        R(true);
      })
      .catch((e) => E(e.message));
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.perchTheme = dark ? "dark" : "light";
    send("perch:theme", { dark });
  }, [dark]);
  const loadSpaces = () =>
    api(
      "/api/local-workspaces" +
        (chat ? `?chat_id=${encodeURIComponent(chat)}` : ""),
    )
      .then((d) => {
        WS(d.workspaces);
        SE(d.selection.workspace);
      })
      .catch((e) => E(e.message));
  useEffect(() => {
    if (ready) loadSpaces();
  }, [ready, chat]);
  useEffect(() => {
    if (!ready) return;
    const seq = ++sequence.current;
    L(true);
    HE("");
    const timer = setTimeout(
      () => {
        const url = query.trim()
          ? `/api/v1/chats/search?text=${encodeURIComponent(query.trim())}&page=${historyPage}`
          : `/api/v1/chats/list?page=${historyPage}&include_pinned=true&include_folders=true`;
        api(url)
          .then((d) => {
            if (seq !== sequence.current) return;
            const rows = Array.isArray(d) ? d : d.items || [];
            H((prev) =>
              historyPage === 1
                ? rows
                : [
                    ...prev,
                    ...rows.filter((x) => !prev.some((y) => x.id === y.id)),
                  ],
            );
            HM(rows.length >= 60);
          })
          .catch((e) => {
            if (seq === sequence.current) HE(e.message);
          })
          .finally(() => {
            if (seq === sequence.current) L(false);
          });
      },
      query ? 220 : 0,
    );
    return () => clearTimeout(timer);
  }, [ready, query, historyPage, chat]);
  useEffect(() => {
    function receive(e) {
      if (
        e.origin !== location.origin ||
        e.source !== frame.current?.contentWindow ||
        e.data?.type !== "perch:state"
      )
        return;
      const d = e.data;
      C(d.chatId || null);
      T(d.title || "新对话");
      MO(d.model || "选择 Agent");
      DR(!!d.draft);
      const u = new URL(location.href);
      d.chatId
        ? u.searchParams.set("chat", d.chatId)
        : u.searchParams.delete("chat");
      historyReplace(u);
    }
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, []);
  function historyReplace(u) {
    window.history.replaceState({}, "", u);
  }
  function navigate(id) {
    if (draft) {
      PN({ id });
      return;
    }
    go(id);
  }
  function go(id) {
    C(id);
    S(id ? `/c/${encodeURIComponent(id)}` : "/");
    DR(false);
    P("chat");
    M(false);
    T(id ? "正在打开…" : "新对话");
    const u = new URL(location.href);
    id ? u.searchParams.set("chat", id) : u.searchParams.delete("chat");
    historyReplace(u);
  }
  const changeWorkspace = async (id) => {
    try {
      E("");
      await api(
        "/api/local-workspaces/selection",
        { workspace_id: id === "none" ? null : id, chat_id: chat },
        "PUT",
      );
      await loadSpaces();
      send("perch:ping");
    } catch (e) {
      E(e.message);
    }
  };
  useEffect(() => {
    if (!ready || page !== "memory") return;
    api("/api/local-workspaces/overview")
      .then(O)
      .catch((e) => ME(e.message));
    const seq = ++memSequence.current;
    MB(true);
    ME("");
    const timer = setTimeout(
      () =>
        api(
          `/api/local-workspaces/memory-catalog?scope=${scope}&workspace_id=${selection?.id || ""}&query=${encodeURIComponent(mq)}&offset=${offset}`,
        )
          .then((d) => {
            if (seq !== memSequence.current) return;
            MM((prev) => (offset ? [...prev, ...d.items] : d.items));
            MT(d.total);
            MMO(d.has_more);
          })
          .catch((e) => {
            if (seq === memSequence.current) ME(e.message);
          })
          .finally(() => {
            if (seq === memSequence.current) MB(false);
          }),
      mq ? 200 : 0,
    );
    return () => clearTimeout(timer);
  }, [ready, page, scope, mq, offset, selection?.id]);
  function refreshMemory() {
    OFF(0);
    P("chat");
    setTimeout(() => P("memory"), 0);
  }
  async function mutateMemory(op) {
    SV(true);
    ME("");
    try {
      const record = edit || remove;
      const target = record?.path?.startsWith("workspaces/")
        ? record.path.split("/")[1]
        : null;
      await api(
        "/api/local-workspaces/memories",
        {
          operations: [op],
          scope: target ? "current" : "global",
          workspace_id: target,
        },
        "PATCH",
      );
      ED(null);
      RM(null);
      refreshMemory();
    } catch (e) {
      ME(e.message);
    } finally {
      SV(false);
    }
  }
  async function register(e) {
    e.preventDefault();
    SV(true);
    try {
      await api("/api/local-workspaces", {
        name,
        path,
        create_directory: false,
      });
      await loadSpaces();
      MG(false);
      PATH("");
      N("");
    } catch (e) {
      E(e.message);
    } finally {
      SV(false);
    }
  }
  if (!ready)
    return (
      <Theme appearance={dark ? "dark" : "light"}>
        <div className="boot">
          <div className="brand-mark">栖</div>
          <h1>Perch</h1>
          {error ? (
            <>
              <p role="alert">{error}</p>
              <Button onClick={() => location.reload()}>重新连接</Button>
            </>
          ) : (
            <>
              <Spinner />
              <p>连接本机工作区</p>
            </>
          )}
        </div>
      </Theme>
    );
  return (
    <Theme
      appearance={dark ? "dark" : "light"}
      accentColor="grass"
      grayColor="sage"
      radius="medium"
      scaling="100%"
    >
      <div className={`app ${mobile ? "nav-open" : ""}`}>
        {mobile && (
          <button
            className="scrim"
            aria-label="关闭侧栏"
            onClick={() => M(false)}
          />
        )}
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-mark">栖</span>
            <div>
              <strong>Perch</strong>
              <span>你的 Agent 工作台</span>
            </div>
            <IconButton
              className="mobile-only"
              variant="ghost"
              aria-label="关闭侧栏"
              onClick={() => M(false)}
            >
              <X size={20} />
            </IconButton>
          </div>
          <Button size="3" className="new-chat" onClick={() => navigate(null)}>
            <Plus size={18} />
            新对话
          </Button>
          <div className="nav-tabs">
            <button
              className={page === "chat" ? "active" : ""}
              onClick={() => {
                P("chat");
                M(false);
              }}
            >
              <ChatCircle size={19} />
              对话
            </button>
            <button
              className={page === "memory" ? "active" : ""}
              onClick={() => {
                P("memory");
                M(false);
              }}
            >
              <Brain size={19} />
              记忆
            </button>
          </div>
          <div className="section-label">
            <span>继续历史对话</span>
            <span>{history.length}</span>
          </div>
          <TextField.Root
            aria-label="搜索历史对话"
            placeholder="搜索标题或内容"
            value={query}
            onChange={(e) => {
              Q(e.target.value);
              HP(1);
            }}
          >
            <TextField.Slot>
              <MagnifyingGlass size={16} />
            </TextField.Slot>
            {query && (
              <TextField.Slot>
                <IconButton
                  aria-label="清空搜索"
                  size="1"
                  variant="ghost"
                  onClick={() => {
                    Q("");
                    HP(1);
                  }}
                >
                  <X />
                </IconButton>
              </TextField.Slot>
            )}
          </TextField.Root>
          <div className="history" aria-busy={loading}>
            {historyError ? (
              <p className="error" role="alert">
                {historyError}
                <button
                  onClick={() => {
                    HP(1);
                    Q(query + " ");
                  }}
                >
                  重试
                </button>
              </p>
            ) : (
              history.map((item) => (
                <button
                  key={item.id}
                  className={`history-item ${chat === item.id ? "selected" : ""}`}
                  onClick={() => navigate(item.id)}
                  title={item.title}
                >
                  <ChatCircle size={16} />
                  <span>{item.title || "未命名对话"}</span>
                  <ArrowRight className="history-arrow" size={14} />
                </button>
              ))
            )}
            {loading && (
              <div className="quiet-status">
                <Spinner size="1" />
                读取历史记录
              </div>
            )}
            {!loading && !history.length && !historyError && (
              <p className="empty-small">
                {query
                  ? "没有找到匹配的对话"
                  : "开始第一段对话，它会保存在这里。"}
              </p>
            )}
            {more && (
              <Button
                variant="ghost"
                onClick={() => HP((x) => x + 1)}
                disabled={loading}
              >
                加载更早的对话
              </Button>
            )}
          </div>
          <div className="sidebar-bottom">
            <div className="workspace-label">
              <Folder size={16} />
              <span>工作目录</span>
              <IconButton
                size="1"
                variant="ghost"
                aria-label="添加工作区"
                onClick={() => MG(true)}
              >
                <Plus size={16} />
              </IconButton>
            </div>
            <Select.Root
              value={selection?.id || "none"}
              onValueChange={changeWorkspace}
            >
              <Select.Trigger aria-label="切换工作区" />
              <Select.Content position="popper">
                <Select.Item value="none">独立临时目录</Select.Item>
                {spaces.map((w) => (
                  <Select.Item value={w.id} key={w.id}>
                    {w.name}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
            <p className="workspace-path" title={selection?.path}>
              {selection?.path || "对话使用独立目录"}
            </p>
            <div className="foundation">
              <span>
                Built on{" "}
                <a
                  href="https://github.com/open-webui/open-webui"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open WebUI
                </a>{" "}
                +{" "}
                <a
                  href="https://github.com/yetone/magpie"
                  target="_blank"
                  rel="noreferrer"
                >
                  Magpie
                </a>
              </span>
              <IconButton
                variant="ghost"
                aria-label={dark ? "切换浅色" : "切换深色"}
                onClick={() => D(!dark)}
              >
                {dark ? <Sun size={18} /> : <Moon size={18} />}
              </IconButton>
            </div>
          </div>
        </aside>
        <main className="content">
          <header className="topbar">
            <IconButton
              className="mobile-only"
              variant="ghost"
              aria-label="打开侧栏"
              onClick={() => M(true)}
            >
              <SidebarSimple size={21} />
            </IconButton>
            <div className="top-title">
              <span className="eyebrow">
                {page === "memory" ? "SHARED MEMORY" : "AGENT WORKSPACE"}
              </span>
              <h1>{page === "memory" ? "记忆库" : title}</h1>
            </div>
            <div className="top-actions">
              {page === "chat" ? (
                <Button
                  variant="soft"
                  onClick={() => send("perch:model")}
                  title="在聊天中选择模型与来源"
                >
                  {model}
                  <span className="status-dot" />
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  onClick={refreshMemory}
                  aria-label="刷新记忆"
                >
                  <ArrowClockwise size={18} />
                </Button>
              )}
            </div>
          </header>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <IconButton
                variant="ghost"
                size="1"
                aria-label="关闭错误"
                onClick={() => E("")}
              >
                <X />
              </IconButton>
            </div>
          )}
          <div
            className="chat-surface"
            style={{ display: page === "chat" ? "flex" : "none" }}
          >
            <iframe
              ref={frame}
              src={ready ? src : undefined}
              title="Open WebUI 聊天"
              onLoad={() => {
                send("perch:theme", { dark });
                send("perch:ping");
              }}
            />
          </div>
          {page === "memory" && (
            <section className="memory-page">
              <div className="memory-intro">
                <div>
                  <span className="eyebrow">CONTINUITY, WITH CONTEXT</span>
                  <h2>让每一次继续，都有所依据。</h2>
                  <p>同一份记忆，供各个 Agent 使用。展开记录查看内容与来源。</p>
                </div>
                <div className="memory-number">
                  <strong>{overview?.total ?? "…"}</strong>
                  <span>条共享记忆</span>
                </div>
              </div>
              <div className="stats-row">
                <div>
                  <span>Codex 导入</span>
                  <strong>{overview?.groups.codex ?? "…"}</strong>
                </div>
                <div>
                  <span>项目记录</span>
                  <strong>{overview?.groups.workspace ?? "…"}</strong>
                </div>
                <div>
                  <span>其他与全局</span>
                  <strong>{overview?.groups.global ?? "…"}</strong>
                </div>
                <div>
                  <span>工作区</span>
                  <strong>{overview?.workspaces ?? "…"}</strong>
                </div>
              </div>
              <div className="memory-controls">
                <TextField.Root
                  value={mq}
                  placeholder="搜索记忆内容"
                  aria-label="搜索记忆"
                  onChange={(e) => {
                    MQ(e.target.value);
                    OFF(0);
                  }}
                >
                  <TextField.Slot>
                    <MagnifyingGlass size={18} />
                  </TextField.Slot>
                </TextField.Root>
                <Select.Root
                  value={scope}
                  onValueChange={(v) => {
                    SC(v);
                    OFF(0);
                  }}
                >
                  <Select.Trigger aria-label="记忆范围" />
                  <Select.Content>
                    <Select.Item value="all">全部记忆</Select.Item>
                    <Select.Item value="current">当前工作区与全局</Select.Item>
                    <Select.Item value="global">仅全局</Select.Item>
                  </Select.Content>
                </Select.Root>
              </div>
              <div className="section-label">
                <span>{mq ? "搜索结果（最多 100 条）" : "最近更新"}</span>
                <span>{memTotal} 条</span>
              </div>
              {memError && (
                <p role="alert" className="error">
                  {memError}
                </p>
              )}
              <div className="memory-list" aria-busy={memBusy}>
                {memories.map((m) => (
                  <details key={m.id} className="memory-card">
                    <summary>
                      <span className="memory-kind">
                        {m.type === "user" ? "偏好" : "上下文"}
                      </span>
                      <div>
                        <strong>{memoryTitle(m)}</strong>
                        <span>{m.path || "全局 · 未设置来源路径"}</span>
                      </div>
                      <span className="memory-date">
                        {new Date(m.updated_at * 1000).toLocaleDateString(
                          "zh-CN",
                        )}
                      </span>
                    </summary>
                    <div className="memory-detail">
                      <pre>{m.content}</pre>
                      <div className="memory-record-actions">
                        <Button
                          variant="soft"
                          size="1"
                          onClick={() => {
                            ED(m);
                            ET(m.content);
                          }}
                        >
                          <PencilSimple />
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          color="red"
                          size="1"
                          onClick={() => RM(m)}
                        >
                          <Trash />
                          删除
                        </Button>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
              {memBusy && (
                <div className="quiet-status">
                  <Spinner />
                  读取记忆
                </div>
              )}
              {!memBusy && !memories.length && (
                <div className="empty">
                  <Brain size={32} />
                  <h3>{mq ? "没有匹配的记忆" : "这个范围还没有记忆"}</h3>
                  <p>可更换范围，或在聊天中让 Agent 记住重要信息。</p>
                </div>
              )}
              {memMore && (
                <Button
                  variant="soft"
                  disabled={memBusy}
                  onClick={() => OFF((x) => x + 40)}
                >
                  加载更多
                </Button>
              )}
            </section>
          )}
        </main>
      </div>
      <Dialog.Root open={manager} onOpenChange={MG}>
        <Dialog.Content maxWidth="480px">
          <Dialog.Title>添加本机工作区</Dialog.Title>
          <Dialog.Description>
            将现有目录登记为工作区。Agent 将在选定目录执行任务。
          </Dialog.Description>
          <form className="dialog-form" onSubmit={register}>
            <label>
              名称
              <TextField.Root
                value={name}
                onChange={(e) => N(e.target.value)}
                placeholder="例如：我的项目"
              />
            </label>
            <label>
              绝对路径
              <TextField.Root
                required
                value={path}
                onChange={(e) => PATH(e.target.value)}
                placeholder="/Users/yourname/Projects/example"
              />
            </label>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <Button variant="soft" type="button" onClick={() => MG(false)}>
                取消
              </Button>
              <Button disabled={saving} type="submit">
                {saving ? <Spinner /> : <Check />}登记目录
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Root>
      <AlertDialog.Root open={!!pending} onOpenChange={(v) => !v && PN(null)}>
        <AlertDialog.Content maxWidth="420px">
          <AlertDialog.Title>继续其他对话？</AlertDialog.Title>
          <AlertDialog.Description>
            当前输入框还有未发送的内容。继续切换会丢弃这段草稿。
          </AlertDialog.Description>
          <div className="dialog-actions">
            <AlertDialog.Cancel>
              <Button variant="soft">保留草稿</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action>
              <Button
                onClick={() => {
                  go(pending.id);
                  PN(null);
                }}
              >
                继续切换
              </Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Root>
      <Dialog.Root open={!!edit} onOpenChange={(v) => !v && ED(null)}>
        <Dialog.Content maxWidth="700px">
          <Dialog.Title>编辑记忆</Dialog.Title>
          <Dialog.Description>
            保留原记录的类型和项目归属。修改将写入本机修订记录。
          </Dialog.Description>
          <textarea
            aria-label="记忆内容"
            className="memory-editor"
            value={editText}
            onChange={(e) => ET(e.target.value)}
          />
          {memError && (
            <p className="error" role="alert">
              {memError}
            </p>
          )}
          <div className="dialog-actions">
            <Button variant="soft" onClick={() => ED(null)}>
              取消
            </Button>
            <Button
              disabled={saving || !editText.trim()}
              onClick={() =>
                mutateMemory({
                  action: "replace",
                  id: edit.id,
                  content: editText,
                })
              }
            >
              保存
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
      <AlertDialog.Root open={!!remove} onOpenChange={(v) => !v && RM(null)}>
        <AlertDialog.Content maxWidth="420px">
          <AlertDialog.Title>删除这条记忆？</AlertDialog.Title>
          <AlertDialog.Description>
            记录将从共享记忆中移除，本机修订日志会保留删除前的内容。
          </AlertDialog.Description>
          {memError && (
            <p className="error" role="alert">
              {memError}
            </p>
          )}
          <div className="dialog-actions">
            <AlertDialog.Cancel>
              <Button variant="soft">取消</Button>
            </AlertDialog.Cancel>
            <Button
              color="red"
              disabled={saving}
              onClick={() => mutateMemory({ action: "remove", id: remove.id })}
            >
              删除记忆
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </Theme>
  );
}
createRoot(document.getElementById("root")).render(<App />);
