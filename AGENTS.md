# AIVectorMemory - AGENTS 工作说明

## 1. 项目定位
- 这是一个基于 Python 的 MCP Server，提供跨会话持久化记忆能力。
- 入口命令是 `run`（定义在 `pyproject.toml` 的 `project.scripts`）。
- 三种运行模式：
  - `run`：stdio MCP Server
  - `run web --port 9080`：Web 看板
  - `run install`：交互式写入各 IDE 的 MCP/Steering 配置

## 2. 目录速览
- `aivectormemory/__main__.py`：CLI 入口与子命令分发
- `aivectormemory/server.py`：MCP 消息循环，`initialize/tools/list/tools/call`
- `aivectormemory/protocol.py`：JSON-RPC 读写封装
- `aivectormemory/tools/`：7 个 MCP 工具及 schema 注册
- `aivectormemory/db/`：SQLite 连接、schema 初始化、Repo 层
- `aivectormemory/embedding/engine.py`：ONNX embedding 推理
- `aivectormemory/web/`：HTTP API + 静态前端
- `docs/`：README 截图资源

## 3. 本地开发命令
1. 安装依赖
```bash
pip install -e .
```
2. 本地启动 MCP Server（stdio）
```bash
run --project-dir .
```
3. 启动 Web 看板
```bash
run web --project-dir . --port 9080
```
4. 为当前项目写入 IDE 配置
```bash
run install --project-dir .
```

## 4. 关键实现约束
- 新增或修改工具时，必须同时更新：
  - `aivectormemory/tools/<tool>.py`
  - `aivectormemory/tools/__init__.py` 的 `TOOL_DEFINITIONS`
  - `aivectormemory/tools/__init__.py` 的 `TOOL_HANDLERS`
- MCP 协议当前是“一行一个 JSON”（stdio），不要引入与当前客户端不兼容的 framing。
- `EmbeddingEngine` 为懒加载；不要在模块导入阶段触发模型下载或推理会话初始化。
- 所有数据库结构变更必须放在 `aivectormemory/db/schema.py:init_db()` 中，保证旧库可迁移。
- `scope=user` 必须统一落到 `USER_SCOPE_DIR`（`@user@`），避免与 project 作用域混淆。

## 5. 代码风格
- 保持现有分层：`tools -> repo -> sqlite`，避免在工具层写复杂 SQL。
- API 返回风格保持兼容：工具层通过 `success_response` 生成 JSON 字符串。
- 仅在关键流程添加简洁中文注释，避免冗余注释。

## 6. 验证清单（提交前）
1. 语法检查
```bash
python -m compileall aivectormemory
```
2. 冒烟验证 MCP 入口可启动
```bash
run --project-dir .
```
3. 若改动 Web API/前端，至少本地打开一次 `http://localhost:9080`
4. 若涉及 schema/repo 改动，确认旧数据库可正常启动并读写

## 7. 已知现状
- `pyproject.toml` 已声明 `pytest testpaths = ["tests"]`，但当前仓库默认没有 `tests/` 目录。
- 若新增测试，请直接创建 `tests/` 并保证 `pytest` 可运行。

<!-- aivectormemory-steering -->
# AIVectorMemory - 跨会话持久记忆

本项目已配置 AIVectorMemory MCP Server，提供以下 7 个工具。请在合适的时机主动调用。

## 启动检查

每次新会话开始时，按以下顺序执行：

1. 调用 `status`（不传参数）读取会话状态，检查 `is_blocked` 和 `block_reason`
2. 调用 `recall`（tags: ["项目知识"], scope: "project", top_k: 100）加载项目知识
3. 调用 `recall`（tags: ["preference"], scope: "user", top_k: 20）加载用户偏好

⚠️ 阻塞状态优先级最高：有阻塞 → 等用户反馈，禁止执行任何操作

## 何时调用

- 新会话开始时：调用 `status`（不传参数）读取上次的工作状态，了解进度和阻塞情况
- 遇到踩坑/技术要点时：调用 `remember` 记录，标签加 "踩坑"
- 需要查找历史经验时：调用 `recall` 语义搜索，或按标签精确查询
- 发现 bug 或待处理事项时：调用 `track`（action: create）记录问题
- 修复问题后：调用 `track`（action: update）更新排查内容和结论
- 问题关闭时：调用 `track`（action: archive）归档
- 任务进度变化时：调用 `status`（传 state 参数）更新当前任务、进度、最近修改
- 对话结束前：调用 `auto_save` 保存本次对话的决策、修改、踩坑、待办、偏好

## 工具速查

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| remember | 存入记忆 | content, tags, scope(project/user) |
| recall | 语义搜索记忆 | query, tags, scope, top_k |
| forget | 删除记忆 | memory_id / memory_ids |
| status | 会话状态管理 | state(不传=读取, 传=更新) |
| track | 问题跟踪 | action(create/update/archive/list) |
| digest | 记忆摘要 | scope, since_sessions, tags |
| auto_save | 自动保存会话 | decisions, modifications, pitfalls, todos, preferences |

## 会话状态管理

status 字段说明：
- `is_blocked`：是否阻塞
- `block_reason`：阻塞原因
- `current_task`：当前任务
- `next_step`：下一步（只能由用户确认后填写，禁止擅自填写）
- `progress`：进度列表
- `recent_changes`：最近修改（不超过10条）
- `pending`：待处理事项

何时设置阻塞（is_blocked: true）：修复完成等用户验证、方案待用户确认、需要用户决策
何时清除阻塞（is_blocked: false）：用户确认验证通过、用户确认方案、用户做出决策

更新时机：任务开始、完成子任务、遇到问题转向、任务完成

## 知识库管理

- 遇到问题必记：命令失败、框架踩坑、技术要点 → `remember`（标签：踩坑）
- 查询踩坑记录：`recall`（query: 关键词, tags: ["踩坑"]）
- 禁止猜测用户意图，必须有用户明确表态才能记录

## 问题追踪

问题处理原则：
- 一次只修一个问题
- 修复过程中发现新问题 → `track create` 记录标题后继续当前问题
- 当前问题修复完成后，再按顺序处理新问题

问题记录流程：
1. `track create`：记录问题标题，`status` 更新 pending
2. 排查问题原因，`track update` 更新 content（根因、方案）
3. 向用户说明问题和方案
4. 修改代码并自测
5. 自测通过后 `track update` 更新结论，等用户验证
6. 用户确认没问题 → `track archive` 归档

## 核心原则

1. 任何操作前必须验证，不能假设，不能靠记忆
2. 遇到问题禁止盲目测试，必须找到根本原因
3. 禁止口头承诺，一切以测试通过为准
4. 任何文件修改前必须查看代码严谨思考
5. 开发、自测过程中禁止让用户手动操作，能自己执行的不要让用户做

## 自测要求

- 代码修改后必须自测验证
- 自测通过后才能说"等待验证"
- 禁止模糊表述："基本完成"、"差不多"、"应该是"等词汇禁止使用
- 任务只有两种状态：完成 或 未完成

## auto_save 规范

对话结束前调用 `auto_save`，分类保存：
- decisions：本次对话的关键决策
- modifications：修改的文件和内容摘要（每个文件一条）
- pitfalls：遇到的坑和解决方案
- todos：产生的待办事项
- preferences：用户表达的技术偏好（scope 固定 user，跨项目通用）

规则：每条内容必须具体可追溯，没有的分类传空数组，不要编造
