# AIVectorMemory 桌面客户端 - 任务文档

## 第 1 组：项目脚手架

- [x] 1.1 安装 Wails 2 CLI，运行 `wails init -n desktop -t vue-ts` 初始化项目
- [x] 1.2 配置 go.mod，添加依赖：mattn/go-sqlite3、wails/v2
- [x] 1.3 创建 Go 后端目录结构：internal/db、internal/embedding、internal/settings、internal/webserver、internal/backup
- [x] 1.4 创建 app.go，定义 App struct 和 startup/shutdown 生命周期方法
- [x] 1.5 配置 wails.json（窗口标题、尺寸 1200x800、应用图标）
- [x] 1.6 配置 frontend/vite.config.ts，安装前端依赖：vue-router、pinia、vue-i18n
- [x] 1.7 验证 `wails dev` 能正常启动空白应用窗口

## 第 2 组：Go 后端 - 数据库层

- [x] 2.1 实现 internal/db/connection.go：SQLite 连接管理（WAL 模式、busy_timeout=5000、MaxOpenConns=1、RWMutex）
- [x] 2.2 实现 sqlite-vec 扩展加载（编译 vec0 动态库，startup 时 LoadExtension）
- [x] 2.3 实现 internal/db/projects.go：GetProjects（含 memories/issues/tags 计数）、AddProject、DeleteProject（级联删除记忆+向量+问题+归档+状态）
- [x] 2.4 实现 internal/db/memories.go：GetMemories（分页+scope+query 筛选）、GetMemoryDetail、UpdateMemory（同步更新 vec 表 embedding）、DeleteMemory（同步删除 vec 表）、DeleteMemoriesBatch
- [x] 2.5 实现 internal/db/memories.go 续：ExportMemories（含 embedding 数据）、ImportMemories（自动补生成 embedding）
- [x] 2.6 实现 internal/db/memories.go 续：SearchMemories（调用 embedding 引擎生成查询向量，vec_distance_cosine 搜索）
- [x] 2.7 实现 internal/db/issues.go：GetIssues（分页+状态+日期+关键词筛选）、GetIssueDetail、CreateIssue（含去重检测）、UpdateIssue（全字段）、ArchiveIssue、DeleteIssue（活跃+归档）
- [x] 2.8 实现 internal/db/tasks.go：GetTasks（按 feature_id 分组+树形结构+状态筛选+关键词）、GetArchivedTasks、CreateTasks（batch_create）、UpdateTask、DeleteTask、DeleteTasksByFeature
- [x] 2.9 实现 internal/db/tags.go：GetTags（项目计数+全局计数+搜索）、RenameTag、MergeTags、DeleteTags
- [x] 2.10 实现 internal/db/status.go：GetStatus、UpdateStatus（支持 clear_fields）
- [x] 2.11 实现 internal/db/health.go：HealthCheck（memories vs vec_memories 一致性、user_memories vs vec_user_memories 一致性、孤立向量检测）、GetDBStats（各表记录数、文件大小、embedding 维度、项目分布、scope 分布）
- [x] 2.12 编写 Go 数据库层单元测试（使用内存 SQLite）

## 第 3 组：Go 后端 - 功能模块

- [x] 3.1 实现 internal/embedding/engine.go：Python 子进程调用 EmbeddingEngine（Encode 方法，临时 JSON 文件传参，解析输出）
- [x] 3.2 实现 embedding Python 路径自动检测（用户配置 > which python3 > which python > 常见路径）
- [x] 3.3 实现 embedding 批量修复（BatchRepair，分批 50 条，通过 Wails EventsEmit 推送进度）
- [x] 3.4 实现 embedding 全量重建（RebuildAllEmbeddings，异步 goroutine + 进度事件）
- [x] 3.5 实现 internal/settings/manager.go：Load/Save desktop.json、默认值填充、路径展开（~）
- [x] 3.6 实现开机自启动：macOS Launch Agent plist 写入/删除
- [x] 3.7 实现开机自启动：Windows 注册表 Run key 写入/删除
- [x] 3.8 实现开机自启动：Linux XDG autostart desktop 文件写入/删除
- [x] 3.9 实现 internal/backup/backup.go：BackupDB（复制 memory.db 到目标目录+时间戳命名）、RestoreDB（覆盖前自动备份当前 db）、ListBackups
- [x] 3.10 实现 internal/webserver/launcher.go：Start（Python 子进程 detach 模式）、Stop、IsRunning、waitAndOpenBrowser
- [x] 3.11 实现 App 的 BrowseDirectory 方法（列出子目录）和 SelectDirectory 方法（调用 Wails runtime.OpenDirectoryDialog）
- [x] 3.12 在 app.go 中将所有 Go 方法绑定到 Wails（确认前端可通过 window.go 调用）

## 第 4 组：前端基础 - 框架与通用组件

- [x] 4.1 创建 CSS 变量文件 styles/variables.css（暗色主题为默认，定义全部颜色、间距、字体变量）
- [x] 4.2 创建 styles/light.css（亮色主题 [data-theme="light"] 变量覆盖）
- [x] 4.3 创建 styles/base.css（Reset、滚动条、全局样式，从现有 Web 看板 style.css 迁移）
- [x] 4.4 实现 stores/theme.ts（Pinia store：主题切换 dark/light/system、跟随系统 prefers-color-scheme 监听、持久化到 settings）
- [x] 4.5 实现 stores/project.ts（Pinia store：当前项目、项目列表、切换项目、记住上次项目）
- [x] 4.6 实现 stores/settings.ts（Pinia store：从 Go GetSettings 加载、SaveSettings 保存）
- [x] 4.7 实现 i18n 模块：index.ts + 7 个语言文件（zh-CN 为默认，从现有 Web 看板 i18n.js 迁移翻译内容）
- [x] 4.8 实现 router/index.ts（路由定义：项目选择页 + 项目内 9 个 Tab 页）
- [x] 4.9 实现 App.vue 根组件（路由视图容器、主题应用、语言初始化）
- [x] 4.10 实现 components/layout/Sidebar.vue（导航列表 9 项 + Web 看板按钮 + 主题切换 + 项目信息返回按钮）
- [x] 4.11 实现 components/layout/Modal.vue（通用模态弹窗：标题+内容插槽+保存/取消按钮+确认弹窗+危险样式）
- [x] 4.12 实现 components/common/Toast.vue（消息通知：success/error/warning，自动消失 3s）
- [x] 4.13 实现 components/common/SearchBox.vue（搜索图标+input+清空按钮+防抖 300ms+emit search 事件）
- [x] 4.14 实现 components/common/Pager.vue（页码+省略号+总数信息+emit page-change 事件）
- [x] 4.15 实现 components/common/Badge.vue（warning/info/success/muted 样式）
- [x] 4.16 实现 utils/formatTime.ts 时间格式化工具函数（ISO → yyyy-MM-dd HH:mm:ss）
- [x] 4.17 验证前端基础框架运行正常：主题切换、语言切换、路由跳转均工作

## 第 5 组：前端视图 - 项目管理与统计

- [x] 5.1 实现 views/ProjectSelect.vue（项目卡片网格：名称+路径+统计+添加按钮+删除按钮+进入动画+语言切换器）
- [x] 5.2 实现项目选择页的添加项目弹窗（手动输入路径+目录浏览选择+上级导航）
- [x] 5.3 实现项目选择页的删除确认弹窗（确认后调用 DeleteProject）
- [x] 5.4 实现空项目欢迎引导页（无项目时显示使用说明）
- [x] 5.5 实现 components/stats/BlockAlert.vue（阻塞/正常状态横幅，点击跳转状态页）
- [x] 5.6 实现 components/stats/StatsGrid.vue（6 个统计卡片：项目记忆/全局记忆/4 个问题状态，可点击弹出筛选弹窗）
- [x] 5.7 实现 components/stats/VectorNetwork.vue（3D 标签云球体：SVG 渲染+鼠标拖拽旋转+自动旋转+点击标签弹出记忆列表）
- [x] 5.8 实现 views/StatsView.vue（组合 BlockAlert + StatsGrid + VectorNetwork + 查看更多标签弹窗 + 空数据引导）

## 第 6 组：前端视图 - 记忆管理

- [x] 6.1 实现 components/memories/MemoryCard.vue（ID+标签+时间+内容预览 3 行+编辑/删除按钮+点击行编辑）
- [x] 6.2 实现 components/memories/MemoryEditModal.vue（编辑弹窗：content textarea + tags 逗号分隔输入 + scope 下拉选择(project/user)，详情展示 source、session_id、similarity、创建/更新时间）
- [x] 6.3 实现 composables/useMemories.ts（封装 GetMemories/UpdateMemory/DeleteMemory/SearchMemories 调用+分页状态）
- [x] 6.4 实现 views/MemoriesView.vue - 项目记忆 Tab（按项目筛选下拉+搜索+列表+分页+导出按钮+导入按钮）
- [x] 6.5 实现 views/MemoriesView.vue - 全局记忆 Tab（搜索+列表+分页）
- [x] 6.6 实现导出功能（调用 ExportMemories → 下载 JSON 文件）
- [x] 6.7 实现导入功能（文件选择 → 读取 JSON → 调用 ImportMemories → 显示导入结果）
- [x] 6.8 实现批量删除记忆功能（多选 checkbox + 批量删除按钮）

## 第 7 组：前端视图 - 问题追踪

- [x] 7.1 实现 components/issues/IssueCard.vue（编号+标题+状态 badge+parent 标签+task 进度+展开/折叠+结构化字段+操作按钮）
- [x] 7.2 实现 components/issues/IssueEditModal.vue（全字段编辑：title/status/content + "更多字段"折叠区：description/investigation/root_cause/solution/files_changed/test_result/notes/feature_id + tags）
- [x] 7.3 实现 composables/useIssues.ts（封装全部 Issue API 调用+分页+筛选状态）
- [x] 7.4 实现 views/IssuesView.vue（工具栏：日期筛选+状态下拉+搜索+快捷按钮（今日/全部/各状态）+添加按钮 + 列表+分页）
- [x] 7.5 实现创建问题弹窗（title+content+tags，去重检测 toast 警告）
- [x] 7.6 实现归档问题操作（确认弹窗+调用 ArchiveIssue）
- [x] 7.7 实现归档问题只读详情弹窗（全字段展示+底部删除按钮）
- [x] 7.8 实现删除问题操作（活跃+归档，确认弹窗）

## 第 8 组：前端视图 - 任务管理

- [x] 8.1 实现 components/tasks/TaskGroup.vue（功能组卡片：标题+日期+进度+状态 badge+折叠/展开+添加/删除按钮）
- [x] 8.2 实现 components/tasks/TaskNode.vue（任务节点：checkbox 切换状态+标题+状态 badge+编辑/删除按钮+子任务列表折叠）
- [x] 8.3 实现 composables/useTasks.ts（封装全部 Task API 调用+筛选状态+展开状态管理）
- [x] 8.4 实现 views/TasksView.vue（工具栏：feature 筛选+状态筛选+搜索+新增功能组按钮 + 任务组列表）
- [x] 8.5 实现创建功能组弹窗（功能组名称+首个任务标题）
- [x] 8.6 实现向功能组添加任务弹窗（支持添加到父任务下）
- [x] 8.7 实现编辑任务标题弹窗
- [x] 8.8 实现删除任务/删除功能组确认弹窗
- [x] 8.9 实现归档任务视图（status=archived 时只读展示）

## 第 9 组：前端视图 - 标签管理

- [x] 9.1 实现 components/tags/TagTable.vue（表格：全选 checkbox+标签名+项目计数/全局计数+操作按钮+点击行重命名）
- [x] 9.2 实现 components/tags/TagBatchBar.vue（已选数量+合并按钮+批量删除按钮+取消按钮）
- [x] 9.3 实现 composables/useTags.ts（封装全部 Tag API 调用+选择状态管理）
- [x] 9.4 实现 views/TagsView.vue（搜索+总数+批量操作栏+表格）
- [x] 9.5 实现重命名标签弹窗（当前名+新名输入）
- [x] 9.6 实现合并标签弹窗（显示源标签列表+目标标签输入）
- [x] 9.7 实现删除标签确认弹窗
- [x] 9.8 实现点击"查看"按钮弹出该标签下的记忆列表弹窗（分页）

## 第 10 组：前端视图 - 会话状态

- [x] 10.1 实现 views/StatusView.vue 只读展示（状态网格：blocked/current_task/next_step/updated_at + 列表区：progress/recent_changes/pending）
- [x] 10.2 实现会话状态编辑功能：每个字段右侧编辑按钮 → 行内编辑模式
- [x] 10.3 实现 is_blocked Toggle Switch 切换（联动 block_reason 输入）
- [x] 10.4 实现 progress/recent_changes/pending 列表增删条目

## 第 11 组：前端视图 - 数据维护

- [x] 11.1 实现 views/MaintenanceView.vue 数据库概览区（文件大小+路径+各表记录数+embedding 维度+项目数）
- [x] 11.2 实现健康检查区（memories/user_memories 一致性状态+孤立向量检测+刷新按钮）
- [x] 11.3 实现修复缺失 embedding 按钮（调用 RepairMissingEmbeddings + 监听 repair:progress 事件 + 进度条显示）
- [x] 11.4 实现重建全部 embedding 按钮（确认弹窗 + 调用 RebuildAllEmbeddings + 进度条）
- [x] 11.5 实现备份管理区（备份按钮+恢复按钮+备份列表展示文件名+大小）
- [x] 11.6 实现从备份恢复确认弹窗（文件选择+确认覆盖警告）

## 第 12 组：前端视图 - 设置

- [x] 12.1 实现 views/SettingsView.vue 外观设置（主题下拉 dark/light/system + 语言下拉 7 种）
- [x] 12.2 实现数据设置（数据库路径输入+浏览按钮 + Python 路径输入+浏览按钮+自动检测标记）
- [x] 12.3 实现 Web 看板设置（端口输入）
- [x] 12.4 实现系统设置（开机自启动 Toggle Switch）
- [x] 12.5 实现关于信息（版本号+技术栈+GitHub 链接）
- [x] 12.6 实现设置保存（变更即保存，调用 SaveSettings）

## 第 13 组：集成与联调

- [x] 13.1 侧边栏底部 Web 看板按钮（调用 LaunchWebDashboard/StopWebDashboard，状态指示灯）
- [ ] 13.2 统计卡片点击弹窗联调（点击项目记忆数→弹出项目记忆列表弹窗，问题状态→弹出对应状态问题列表弹窗）
- [ ] 13.3 3D 向量网络点击标签→弹出记忆列表弹窗联调
- [x] 13.4 记住上次打开的项目（settings.last_project，启动时自动进入）
- [ ] 13.5 窗口尺寸/位置保存恢复（shutdown 时保存到 desktop.json，startup 时恢复）
- [ ] 13.6 全应用错误处理（Go binding 调用失败→Toast 错误提示）
- [ ] 13.7 全流程冒烟测试：启动→选择项目→浏览各页面→编辑数据→切换主题→切换语言→退出

## 第 14 组：构建与分发

- [ ] 14.1 准备应用图标（appicon.png 1024x1024 + 各平台所需尺寸）
- [ ] 14.2 编译 sqlite-vec 动态库（macOS .dylib / Windows .dll / Linux .so），配置打包包含
- [ ] 14.3 macOS 构建：`wails build -platform darwin/universal`，生成 .app，验证双击启动
- [ ] 14.4 Windows 构建：`wails build -platform windows/amd64`，生成 .exe，验证双击启动
- [ ] 14.5 Linux 构建：`wails build -platform linux/amd64`，生成可执行文件/AppImage，验证启动
- [ ] 14.6 验证并发安全：同时运行桌面端和 MCP Server，确认读写不冲突
- [ ] 14.7 验证桌面端关闭后 Web 看板子进程仍在运行

## 第 15 组：Web 看板样式同步

- [ ] 15.1 将桌面端 CSS 变量体系（variables.css）反向移植到 Web 看板 style.css
- [ ] 15.2 Web 看板添加亮色主题支持（[data-theme="light"] 变量覆盖）
- [ ] 15.3 Web 看板添加主题切换 UI（跟随桌面端设计）
- [ ] 15.4 Web 看板默认语言改为简体中文
- [ ] 15.5 验证 Web 看板所有页面在两种主题下显示正常
