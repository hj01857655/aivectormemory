<p align="center">
  <h1 align="center">🧠 AIVectorMemory</h1>
  <p align="center">
    <strong>给 AI 编程助手装上记忆 — 跨会话持久化记忆 MCP Server</strong>
  </p>
  <p align="center">
    <a href="https://pypi.org/project/aivectormemory/"><img src="https://img.shields.io/pypi/v/aivectormemory?color=blue&label=PyPI" alt="PyPI"></a>
    <a href="https://pypi.org/project/aivectormemory/"><img src="https://img.shields.io/pypi/pyversions/aivectormemory" alt="Python"></a>
    <a href="https://github.com/Edlineas/aivectormemory/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
    <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-purple" alt="MCP"></a>
  </p>
</p>

---

> **问题**：AI 助手每次新会话都"失忆"，反复踩同样的坑、忘记项目约定、丢失开发进度。
>
> **AIVectorMemory**：通过 MCP 协议为 AI 提供本地向量记忆库，让它记住一切 — 项目知识、踩坑记录、开发决策、工作进度 — 跨会话永不丢失。

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🔍 **语义搜索** | 基于向量相似度，搜"数据库超时"能找到"MySQL 连接池踩坑" |
| 🏠 **完全本地** | ONNX Runtime 本地推理，无需 API Key，数据不出本机 |
| 🔄 **智能去重** | 余弦相似度 > 0.95 自动更新，不会重复存储 |
| 📊 **Web 看板** | 内置管理界面，3D 向量网络可视化 |
| 🔌 **全 IDE 支持** | Cursor / Kiro / Claude Code / Windsurf / VSCode / Trae / OpenCode / Codex CLI 等 |
| 📁 **项目隔离** | 多项目共用一个 DB，通过 project_dir 自动隔离 |
| 🏷️ **标签体系** | 记忆分类管理，支持标签搜索、重命名、合并 |
| 📋 **问题追踪** | 轻量级 issue tracker，AI 自动记录和归档 |

## 🏗️ 架构

```
┌─────────────────────────────────────────────────┐
│                   AI IDE                         │
│  Cursor / Kiro / Claude Code / Windsurf / ...   │
└──────────────────────┬──────────────────────────┘
                       │ MCP Protocol (stdio)
┌──────────────────────▼──────────────────────────┐
│              AIVectorMemory Server                    │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ remember │ │  recall   │ │   auto_save      │ │
│  │ forget   │ │  digest   │ │   status/track   │ │
│  └────┬─────┘ └────┬─────┘ └───────┬──────────┘ │
│       │            │               │             │
│  ┌────▼────────────▼───────────────▼──────────┐  │
│  │         Embedding Engine (ONNX)            │  │
│  │      intfloat/multilingual-e5-small        │  │
│  └────────────────────┬───────────────────────┘  │
│                       │                          │
│  ┌────────────────────▼───────────────────────┐  │
│  │     SQLite + sqlite-vec (向量索引)          │  │
│  │     ~/.aivectormemory/memory.db                 │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```


## 🚀 快速开始

### 方式一：pip 安装

```bash
pip install aivectormemory
cd /path/to/your/project
run install          # 交互式选择 IDE，一键配置
```

### 方式二：uvx 运行（零安装）

```bash
cd /path/to/your/project
uvx aivectormemory install
```

### 方式三：Codex CLI 一键接入

```bash
cd /path/to/your/project
run install          # 交互式选择 Codex CLI
```

### 方式四：手动配置

```json
{
  "mcpServers": {
    "aivectormemory": {
      "command": "run",
      "args": ["--project-dir", "/path/to/your/project"]
    }
  }
}
```

<details>
<summary>📍 各 IDE 配置文件位置</summary>

| IDE | 配置文件路径 |
|-----|------------|
| Kiro | `.kiro/settings/mcp.json` |
| Cursor | `.cursor/mcp.json` |
| Claude Code | `.mcp.json` |
| Windsurf | `.windsurf/mcp.json` |
| VSCode | `.vscode/mcp.json` |
| Trae | `.trae/mcp.json` |
| OpenCode | `opencode.json` |
| Codex CLI | 通过 `codex mcp add` 注册（写入用户级 Codex MCP 配置） |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |

</details>

## 🛠️ 7 个 MCP 工具

### `remember` — 存入记忆

```
content (string, 必填)   记忆内容，Markdown 格式
tags    (string[], 必填)  标签，如 ["踩坑", "python"]
scope   (string)          "project"（默认）/ "user"（跨项目）
```

相似度 > 0.95 自动更新已有记忆，不重复存储。

### `recall` — 语义搜索

```
query   (string)     语义搜索关键词
tags    (string[])   标签精确过滤
scope   (string)     "project" / "user" / "all"
top_k   (integer)    返回数量，默认 5
```

向量相似度匹配，用词不同也能找到相关记忆。

### `forget` — 删除记忆

```
memory_id  (string)     单个 ID
memory_ids (string[])   批量 ID
```

### `status` — 会话状态

```
state (object, 可选)   不传=读取，传=更新
  is_blocked, block_reason, current_task,
  next_step, progress[], recent_changes[], pending[]
```

跨会话保持工作进度，新会话自动恢复上下文。

### `track` — 问题跟踪

```
action   (string)   "create" / "update" / "archive" / "list"
title    (string)   问题标题
issue_id (integer)  问题 ID
status   (string)   "pending" / "in_progress" / "completed"
content  (string)   排查内容
```

### `digest` — 记忆摘要

```
scope          (string)    范围
since_sessions (integer)   最近 N 次会话
tags           (string[])  标签过滤
```

### `auto_save` — 自动保存

```
decisions[]      关键决策
modifications[]  文件修改摘要
pitfalls[]       踩坑记录
todos[]          待办事项
```

每次对话结束自动分类存储，打标签，去重。

## 📊 Web 看板

```bash
run web --port 9080
```

浏览器访问 `http://localhost:9080`

- 多项目切换，记忆浏览/搜索/编辑/删除
- 会话状态、问题跟踪
- 标签管理（重命名、合并、批量删除）
- 3D 向量记忆网络可视化

<p align="center">
  <img src="docs/dashboard-projects.png" alt="项目选择" width="100%">
  <br>
  <em>项目选择</em>
</p>

<p align="center">
  <img src="docs/dashboard-overview.png" alt="统计概览 & 向量网络可视化" width="100%">
  <br>
  <em>统计概览 & 向量网络可视化</em>
</p>

## ⚡ 配合 Steering 规则

AIVectorMemory 是存储层，通过 Steering 规则告诉 AI 何时调用：

```markdown
# 记忆管理
- 新会话开始：调用 status 读取状态
- 遇到踩坑：调用 remember 记录
- 查找经验：调用 recall 搜索
- 对话结束：调用 auto_save 保存
```

| IDE | Steering 位置 |
|-----|--------------|
| Kiro | `.kiro/steering/*.md` |
| Cursor | `.cursor/rules/*.md` |
| Claude Code | `CLAUDE.md` |
| Codex CLI | `AGENTS.md` |

## 🇨🇳 中国大陆用户

首次运行自动下载 Embedding 模型（~200MB），如果慢：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

或在 MCP 配置中加 env：

```json
{
  "env": { "HF_ENDPOINT": "https://hf-mirror.com" }
}
```

## 📦 技术栈

| 组件 | 技术 |
|------|------|
| 运行时 | Python >= 3.10 |
| 向量数据库 | SQLite + sqlite-vec |
| Embedding | ONNX Runtime + intfloat/multilingual-e5-small |
| 分词器 | HuggingFace Tokenizers |
| 协议 | Model Context Protocol (MCP) |
| Web | 原生 HTTPServer + Vanilla JS |

## License

MIT
