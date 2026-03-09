# Codex CLI 使用教程（AIVectorMemory）

本教程面向日常使用，目标是：

- 只配置一次 MCP
- 之后在任意项目目录直接使用
- 让 AI 在会话里自动记住偏好、状态和问题记录

## 1. 一次性配置（推荐）

在 PowerShell 执行：

```powershell
codex mcp remove aivectormemory
codex mcp add aivectormemory -- uvx -q --no-progress --from aivectormemory@latest run --project-dir .
codex mcp get aivectormemory
```

看到 `args` 里包含 `--project-dir .`，表示配置成功。

说明：

- `uvx --from aivectormemory@latest`：使用远端包版本（非本地源码直跑）
- `--project-dir .`：按当前目录动态分项目，不需要每个项目重配
- `-q --no-progress`：避免安装输出干扰 MCP stdio 通道

> 2026-03-09 实测：以上配置可在 Codex 中正常调用 `status` 与 `auto_save`。

## 2. 日常使用流程

每次进入一个项目：

```powershell
cd E:\VSCodeSpace\your-project
codex
```

进入 Codex 后，让 AI 先调用启动检查：

```text
调用aivectormemory
```

默认会按顺序执行：

1. `status`：读会话状态
2. `recall(tags=["项目知识"], scope="project")`：读项目知识
3. `recall(tags=["preference"], scope="user")`：读用户偏好

## 3. 8 个工具何时用

1. `status`：开场读取；任务进度变化时更新
2. `remember`：出现明确经验/踩坑/约定时记录
3. `recall`：开始前或遇到类似问题时检索历史
4. `track`：问题生命周期管理（create/update/archive/list）
5. `task`：任务拆解与任务状态联动
6. `readme`：按工具定义/依赖自动生成 README 片段
7. `forget`：删除错误或过期记忆
8. `auto_save`：每轮对话结束前保存偏好

## 4. 常用检查命令

```powershell
codex mcp list
codex mcp get aivectormemory
```

关注点：

- `enabled: true`
- `command: uvx`
- `args` 包含 `--project-dir .`
- `Status` 显示 `enabled`
- `Auth` 显示 `Unsupported` 属于正常现象（stdio MCP 不走 OAuth）

## 5. 常见问题

### Q1：每个项目都要重新 `mcp add` 吗？

不用。只有以下情况才需要重配一次：

- 你执行了 `codex mcp remove aivectormemory`
- 你把参数改回了固定目录
- Codex 全局配置被重置

### Q2：`remove: codex mcp remove aivectormemory` 是已经删除了吗？

不是。那只是提示可执行的删除命令，配置仍在。

### Q3：为什么有时看起来不是当前项目？

如果配置是固定目录（例如 `--project-dir E:/xxx`），记忆会写入固定项目分区。  
改成 `--project-dir .` 后会按启动目录动态分区。

### Q4：出现 `Transport closed` 怎么办？

按下面顺序排查：

1. 先确认配置是 quiet uvx：
   ```powershell
   codex mcp get aivectormemory --json
   ```
   重点看 `command=uvx`，`args` 里有 `-q --no-progress --from ... run --project-dir .`。
2. 完全退出当前 Codex 会话，重新 `codex` 启动新会话（避免旧连接残留）。
3. 新会话里先让 AI 只调用一次：
   - `status`
4. 再调用：
   - `auto_save`

如果新会话两步都成功，通常就是上一会话连接已失效，不是服务端逻辑错误。

## 6. 一键诊断（推荐）

新增 `doctor codex` 子命令后，可直接做完整健康检查：

```powershell
run doctor codex
```

会检查：

1. `codex mcp get` 是否可读
2. `command/args` 是否符合推荐（`uvx -q --no-progress --from ... --project-dir .`）
3. stdio 探针是否能完成 `initialize -> tools/list -> status -> auto_save`

如果你只想检查配置，不跑探针：

```powershell
run doctor codex --no-probe
```

## 7. 项目重命名迁移（ace-lite -> ace）

新增 `migrate-project` 子命令后，重命名可直接迁移分区数据：

```powershell
# 先演练，不落库
run migrate-project --from E:/VSCodeSpace/ace-lite --to E:/VSCodeSpace/ace --dry-run

# 再正式执行（默认自动备份数据库）
run migrate-project --from E:/VSCodeSpace/ace-lite --to E:/VSCodeSpace/ace
```

默认行为：

1. 自动备份 `~/.aivectormemory/memory.db`
2. 迁移所有含 `project_dir` 的表
3. `session_state` 若目标已存在会自动合并，避免唯一键冲突

## 8. 可选：切回本地源码模式

如果你在开发 AIVectorMemory 本身，希望改代码后立即生效，可改为本地源码运行：

```powershell
codex mcp remove aivectormemory
codex mcp add aivectormemory -- uv run --project E:/VSCodeSpace/aivectormemory python -m aivectormemory --project-dir .
```

生产日常使用建议仍保留远端包模式（更稳定）。
