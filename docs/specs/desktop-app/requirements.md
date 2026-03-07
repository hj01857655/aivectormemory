# AIVectorMemory 桌面客户端 - 需求文档

## 背景

当前 AIVectorMemory 的 Web 看板需要通过命令行启动 HTTP 服务（`python -m aivectormemory web --port 9080`），每次查看数据都要先启动服务再打开浏览器。用户需要一个**免启动、开箱即用**的桌面应用，能直接查看和管理所有记忆数据，并提供数据维护能力。

## 核心需求

### 1. 免启动直接访问

- 双击打开即可使用，无需命令行启动服务
- 直接读取本地 SQLite 数据库（`~/.aivectormemory/memory.db`）
- 跨平台支持：macOS、Windows、Linux

### 2. 看板功能完整迁移

现有 Web 看板的所有功能都应在桌面端可用：

#### 2.1 统计概览（首页）
- 项目记忆数、全局记忆数（可点击卡片弹出对应记忆列表弹窗）
- 问题状态分布卡片（pending/in_progress/completed/archived，可点击弹出对应状态的问题列表弹窗）
- 阻塞状态告警横幅（首页醒目展示当前是否阻塞、阻塞原因、当前任务，点击跳转会话状态页）
- 3D 向量网络可视化（标签云球体，支持鼠标拖拽旋转、自动旋转、点击标签节点弹出该标签下的记忆列表）
- "查看更多"展开完整标签列表弹窗（含标签名和使用频率）
- 空数据引导（无数据时显示欢迎引导提示）

#### 2.2 记忆管理
- 分页查看项目记忆 / 全局记忆（两个独立视图）
- 按项目筛选
- 搜索记忆（关键词 + 语义向量搜索）
- 查看记忆详情（content、tags、scope、source、session_id、similarity、创建/更新时间）
- 编辑记忆（修改 content、tags、scope）
- 删除记忆（单条 / 批量）
- 导入 / 导出记忆（JSON 格式，含 embedding 数据）
- 点击行任意位置触发编辑弹窗

#### 2.3 问题追踪（Issues/Track）
- 查看活跃问题列表（支持按状态筛选、按日期筛选、关键词搜索）
- 快捷筛选按钮（今日、全部、各状态快捷切换：pending/in_progress/completed/archived）
- 查看归档问题列表（归档问题只读查看详情弹窗 + 删除）
- 问题详情弹窗（完整字段：description、content、investigation、root_cause、solution、files_changed、test_result、notes、feature_id）
- 创建问题（title、content、tags），后端去重检测（重复时显示警告提示）
- 编辑问题（所有字段，含状态切换，"更多字段"折叠展开）
- 归档问题（独立归档操作，区别于删除）
- 删除问题（活跃和归档均支持）
- 父问题关联（显示 "关联 #N" 标签）
- 任务进度显示（关联 task 时显示 done/total）
- 分页浏览

#### 2.4 任务管理（Tasks）
- 按 feature_id 分组显示任务（卡片式分组，含进度统计 done/total）
- 树形结构支持（parent/children 层级，父任务可折叠/展开子任务列表）
- 功能组折叠/展开控制
- 任务状态更新（点击复选框切换 completed/pending）
- 按 feature_id 筛选、按状态筛选、关键词搜索
- 创建功能组（新增 feature group + 首个任务）
- 向功能组添加任务（支持添加到父任务下作为子任务）
- 编辑任务标题
- 删除单个任务
- 按 feature_id 批量删除整个功能组
- 查看归档任务（只读展示）

#### 2.5 会话状态
- 查看当前会话状态（is_blocked、block_reason、current_task、next_step、progress、recent_changes、pending、updated_at）
- 查看各项目的状态（通过项目切换实现）
- 注：Web 看板仅支持只读展示，编辑功能见 3.5

#### 2.6 项目管理
- 项目选择页（启动首页，卡片式布局，含进入动画）
- 查看所有注册项目（含记忆数、问题数、标签数统计）
- 添加项目（支持手动输入路径 + 目录浏览选择，含上级目录导航）
- 切换项目视图（点击项目卡片进入，侧边栏显示当前项目名，点击可返回）
- 删除项目及其关联数据（记忆 + 向量 + 问题 + 归档 + 会话状态）
- 空项目欢迎引导页（无项目时显示使用说明和安装命令）
- URL hash 记住当前项目（刷新后自动恢复）

#### 2.7 标签管理
- 表格展示所有标签及使用频率（区分项目计数 📁 / 全局计数 🌐）
- 按标签筛选记忆（点击"查看"按钮弹出该标签下的记忆列表）
- 标签重命名（点击行任意位置或"重命名"按钮触发）
- 批量选择（全选复选框 + 单个复选框，选中后显示批量操作栏）
- 标签合并（批量选择多个源标签，合并为一个目标标签）
- 标签批量删除（从所有相关记忆中移除）
- 标签搜索过滤（实时搜索 + 清空按钮）
- 取消批量选择

### 3. 数据维护功能（Web 看板没有的新功能）

#### 3.1 数据健康检查
- 检测 memories 表与 vec_memories 表的一致性（找出缺失 embedding 的记忆）
- 检测 user_memories 表与 vec_user_memories 表的一致性
- 显示健康状态摘要（总数、缺失数、异常数）

#### 3.2 数据修复
- 一键为缺失 embedding 的记忆补生成向量
- 批量重建 embedding（当模型升级后需要重新编码）
- 修复进度显示

#### 3.3 数据库统计
- 各表记录数（memories、user_memories、vec_memories、vec_user_memories、issues、issues_archive、tasks、tasks_archive、session_state）
- 数据库文件大小
- 各项目记忆分布
- 各 scope 记忆分布
- embedding 维度信息
- 孤立数据检测（vec 表有记录但 memories 表无对应记录）

#### 3.4 数据库备份
- 一键备份数据库文件（复制 memory.db 到指定目录，带时间戳）
- 从备份恢复

#### 3.5 会话状态编辑（Web 看板没有的新功能）
- 编辑会话状态字段（is_blocked、block_reason、current_task、next_step 等）
- API 已支持 `PUT /api/status`，桌面端需提供编辑 UI

#### 3.6 内置 Web 看板启动
- 一键启动 Web 看板服务（调用 `python -m aivectormemory web --port <port>`）
- 自动打开浏览器访问看板
- 关闭桌面端不影响已启动的 Web 看板服务（子进程 detach）

### 4. 多语言支持

- 现有 Web 看板支持 7 种语言（简体中文、繁体中文、英文、西班牙语、德语、法语、日语），桌面端需延续
- **默认语言为简体中文**（Web 看板和桌面端统一）
- 语言切换器（项目选择页 + 侧边栏各一个）
- 内置标签分类翻译（decision/modification/pitfall/todo/preference 等标签的本地化显示）

### 5. 通用交互

- Toast 消息通知（成功/错误/警告，自动消失）
- 模态弹窗系统（标题 + 内容 + 保存/取消，支持确认弹窗和危险操作样式）
- 搜索输入框统一交互（防抖搜索 + 清空按钮）
- 分页组件（页码 + 省略号 + 总数/当前页信息）
- 时间格式化显示（ISO → yyyy-MM-dd HH:mm:ss）

### 6. 应用设置

- **开机自启动**：支持跟随系统启动（macOS Launch Agent / Windows 注册表 / Linux autostart）
- **主题切换**：亮色 / 暗色主题切换，支持跟随系统主题
- **数据库路径**：自定义 `memory.db` 路径（默认 `~/.aivectormemory/memory.db`）
- **Web 看板端口**：配置 Web 看板启动端口（默认 9080）
- **语言设置**：语言偏好持久化

## 技术约束

- **技术栈**：Go + Wails 2（后端 Go，前端 Web 技术）
- 必须能直接读写 `~/.aivectormemory/memory.db`（SQLite + sqlite-vec 扩展）
- embedding 生成：Go 端集成 ONNX Runtime（通过 cgo 或调用 Python 子进程），用于数据修复场景
- 不依赖 Web 看板服务，直接操作数据库
- 跨平台构建：通过 Wails 2 的 `wails build` 生成各平台安装包（macOS .app、Windows .exe、Linux AppImage）
- **UI 统一**：桌面端与现有 Web 看板使用同一套设计系统（设计稿中的暗色/亮色主题、组件样式）。桌面端开发完成后，Web 看板也需同步更新为相同样式，保持视觉一致
- 前端可复用现有 Web 看板的 UI 组件和样式
- SQLite 并发安全：MCP Server 和桌面应用可能同时访问同一个 db 文件，需使用 WAL 模式 + 合理的锁策略
- 数据库路径：默认 `~/.aivectormemory/memory.db`，支持通过设置自定义路径

## 验收标准

1. macOS/Windows/Linux 上双击可启动，无需命令行
2. 所有 Web 看板现有功能可用
3. 数据健康检查能检测出缺失 embedding 的记忆
4. 一键修复能为缺失的记忆补生成 embedding
5. 修复后 recall 搜索能命中之前搜不到的记忆
6. 应用退出不影响 MCP Server 正常运行（只读/写同一个 SQLite 文件，注意并发锁）

## 非目标（不在本次范围）

- 不需要替代 MCP Server 本身的功能（remember/recall/track 等工具调用仍通过 MCP）
- 不需要实时监听数据变化（手动刷新即可）
- 不需要远程访问能力（仅本地使用）
