# Perch · 栖

把历史对话、项目目录和共享记忆放进同一个本机 Agent 工作台。

Perch **基于 Open WebUI 与 Magpie**：Open WebUI 保存聊天与记忆，Magpie 提供模型网关，Perch 负责整合界面、工作区、各个 harness 和按项目隔离的记忆工具。这是独立整合项目，与上游无官方隶属关系。

- 左侧直接搜索和继续历史对话；切换前保护未发送的草稿。
- 同一聊天绑定工作目录，切换 Agent 后延续同一项目上下文。
- 记忆页显示总量、来源、项目范围，支持搜索、分页、展开、修改和删除；本机保留修订记录。
- 独立 Electron / Chromium 客户端，浅色、深色和窄屏界面。
- Magpie 插件为 Perch 分配独立 Agent Key，内部 harness 通过 Magpie 的请求统一记到 `perch`。

支持的接线包括 DeepSeek Harness、Step Code、Claude Code、Z Code、本机 Codex 与 Antigravity。模型来源详见 [English README](README.md)。Codex / Gemini 的本机登录直连不经过 Magpie，因此不会计入 Magpie 的 Perch 用量。

这是 macOS 上的早期整合，需要自行安装与登录上游 CLI、配置模型来源。安装步骤见 [SETUP](docs/SETUP.md)。客户端入口为 `desktop/Perch.app`；网页入口为 `http://127.0.0.1:8080/desk`。仅限本机单用户使用，无登录界面，不应直接开放公网。

仓库只包含源码与文档，不包含聊天、记忆、密钥、登录状态、工作目录、模型权重、日志或历史备份。记忆中按范围选出的片段会随任务发送给你所选择的模型来源。

原生 CLI 与共享记忆通过本机假模型做回归测试；真实模型可用性取决于账号、额度、地区和上游版本。验证边界见 [VERIFICATION](docs/VERIFICATION.md)。

感谢 [Open WebUI](https://github.com/open-webui/open-webui)、[Magpie](https://github.com/yetone/magpie) 和各上游 Agent。Perch 原创整合代码为 MIT；上游保留各自许可证，详见 [NOTICE](NOTICE)。
