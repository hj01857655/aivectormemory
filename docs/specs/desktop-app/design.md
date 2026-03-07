# AIVectorMemory 桌面客户端 - 设计文档

## 1. 架构概览

```
┌──────────────────────────────────────────────────────┐
│                    Wails 2 Runtime                    │
│  ┌────────────────────┐  ┌─────────────────────────┐ │
│  │   Go Backend        │  │   Frontend (WebView)    │ │
│  │                     │  │                         │ │
│  │  ┌───────────────┐  │  │  ┌───────────────────┐  │ │
│  │  │ DB Layer      │◄─┼──┼──│ Vue 3 + Vite      │  │ │
│  │  │ (SQLite+vec)  │  │  │  │                   │  │ │
│  │  └───────────────┘  │  │  │ - Router (页面)    │  │ │
│  │  ┌───────────────┐  │  │  │ - Pinia (状态)     │  │ │
│  │  │ Embedding     │  │  │  │ - i18n (多语言)    │  │ │
│  │  │ Engine        │  │  │  │ - Theme (主题)     │  │ │
│  │  └───────────────┘  │  │  └───────────────────┘  │ │
│  │  ┌───────────────┐  │  │                         │ │
│  │  │ Settings      │  │  │                         │ │
│  │  │ Manager       │  │  │                         │ │
│  │  └───────────────┘  │  │                         │ │
│  │  ┌───────────────┐  │  │                         │ │
│  │  │ Web Server    │  │  │                         │ │
│  │  │ Launcher      │  │  │                         │ │
│  │  └───────────────┘  │  │                         │ │
│  └────────────────────┘  └─────────────────────────┘ │
│                                                       │
│  ~/.aivectormemory/memory.db  (SQLite + WAL mode)     │
│  ~/.aivectormemory/desktop.json (设置文件)              │
└──────────────────────────────────────────────────────┘
```

### 通信方式

Wails 2 提供 Go ↔ JS 双向绑定：
- **Go → JS**：Go struct 的公开方法自动生成 JS 调用接口
- **JS → Go**：前端通过 `window.go.main.App.MethodName()` 调用 Go 方法
- **事件系统**：`runtime.EventsEmit` / `runtime.EventsOn` 用于异步通知（如修复进度）

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 桌面框架 | Wails 2 | Go + WebView，跨平台 |
| 后端语言 | Go 1.21+ | 数据库操作、文件系统、子进程管理 |
| 前端框架 | Vue 3 + Vite | 组件化开发，HMR 热重载 |
| 状态管理 | Pinia | 轻量级状态管理 |
| UI 组件 | 自定义组件 | 复用现有 Web 看板设计系统 |
| SQLite | mattn/go-sqlite3 (CGo) | 支持 sqlite-vec 扩展加载 |
| Embedding | Python 子进程 | 调用 `aivectormemory` 的 EmbeddingEngine |
| 配置存储 | JSON 文件 | `~/.aivectormemory/desktop.json` |

### 为什么选 Vue 3 而非 Vanilla JS

- Wails 2 官方模板原生支持 Vue 3 + Vite
- 桌面端页面比 Web 看板更复杂（多了设置、数据维护），组件化管理更清晰
- Vue 3 的 `<script setup>` + Composition API 轻量且高效
- Pinia 状态管理简化跨组件数据共享（当前项目、主题、语言）

## 3. Go 后端模块设计

### 3.1 项目结构

```
desktop/
├── main.go                 # 入口，Wails 初始化
├── app.go                  # App struct，生命周期
├── internal/
│   ├── db/
│   │   ├── connection.go   # SQLite 连接管理（WAL 模式）
│   │   ├── memories.go     # memories + vec_memories CRUD
│   │   ├── issues.go       # issues + issues_archive CRUD
│   │   ├── tasks.go        # tasks + tasks_archive CRUD
│   │   ├── tags.go         # 标签聚合、重命名、合并、删除
│   │   ├── projects.go     # 项目注册表管理
│   │   ├── status.go       # session_state CRUD
│   │   └── health.go       # 健康检查、孤立数据检测
│   ├── embedding/
│   │   └── engine.go       # Python 子进程调用 EmbeddingEngine
│   ├── settings/
│   │   └── manager.go      # 配置读写 + 开机自启动
│   ├── webserver/
│   │   └── launcher.go     # Web 看板服务启动/停止
│   └── backup/
│       └── backup.go       # 数据库备份/恢复
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── stores/
│   │   │   ├── project.ts  # 当前项目状态
│   │   │   ├── theme.ts    # 主题状态
│   │   │   └── settings.ts # 设置状态
│   │   ├── composables/
│   │   │   ├── useMemories.ts
│   │   │   ├── useIssues.ts
│   │   │   ├── useTasks.ts
│   │   │   ├── useTags.ts
│   │   │   └── useHealth.ts
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.vue
│   │   │   │   ├── TopBar.vue
│   │   │   │   └── Modal.vue
│   │   │   ├── common/
│   │   │   │   ├── Pager.vue
│   │   │   │   ├── SearchBox.vue
│   │   │   │   ├── Toast.vue
│   │   │   │   └── Badge.vue
│   │   │   ├── stats/
│   │   │   │   ├── StatsGrid.vue
│   │   │   │   ├── BlockAlert.vue
│   │   │   │   └── VectorNetwork.vue
│   │   │   ├── memories/
│   │   │   │   ├── MemoryCard.vue
│   │   │   │   └── MemoryEditModal.vue
│   │   │   ├── issues/
│   │   │   │   ├── IssueCard.vue
│   │   │   │   └── IssueEditModal.vue
│   │   │   ├── tasks/
│   │   │   │   ├── TaskGroup.vue
│   │   │   │   └── TaskNode.vue
│   │   │   └── tags/
│   │   │       ├── TagTable.vue
│   │   │       └── TagBatchBar.vue
│   │   ├── views/
│   │   │   ├── ProjectSelect.vue
│   │   │   ├── StatsView.vue
│   │   │   ├── MemoriesView.vue
│   │   │   ├── IssuesView.vue
│   │   │   ├── TasksView.vue
│   │   │   ├── TagsView.vue
│   │   │   ├── StatusView.vue
│   │   │   ├── MaintenanceView.vue
│   │   │   └── SettingsView.vue
│   │   ├── i18n/
│   │   │   ├── index.ts
│   │   │   ├── zh-CN.ts
│   │   │   ├── zh-TW.ts
│   │   │   ├── en.ts
│   │   │   ├── es.ts
│   │   │   ├── de.ts
│   │   │   ├── fr.ts
│   │   │   └── ja.ts
│   │   └── styles/
│   │       ├── variables.css   # CSS 变量（主题色）
│   │       ├── dark.css
│   │       ├── light.css
│   │       └── base.css
│   └── package.json
├── build/
│   ├── appicon.png
│   └── darwin/              # macOS 特定资源
├── wails.json
└── go.mod
```

### 3.2 App 生命周期

```go
type App struct {
    ctx      context.Context
    db       *db.Connection
    settings *settings.Manager
    launcher *webserver.Launcher
}

func (a *App) startup(ctx context.Context) {
    a.ctx = ctx
    // 1. 加载设置
    a.settings = settings.Load()
    // 2. 打开数据库（WAL 模式）
    a.db = db.Open(a.settings.DBPath)
    // 3. 加载 sqlite-vec 扩展
    a.db.LoadExtension("vec0")
}

func (a *App) shutdown(ctx context.Context) {
    // 关闭数据库连接（不影响 MCP Server）
    a.db.Close()
    // 注意：不杀 Web 看板子进程（detach 模式）
}
```

### 3.3 数据库连接管理

```go
// internal/db/connection.go
type Connection struct {
    db   *sql.DB
    mu   sync.RWMutex  // 应用内读写锁
}

func Open(path string) *Connection {
    db, _ := sql.Open("sqlite3", path + "?_journal_mode=WAL&_busy_timeout=5000")
    // WAL 模式：允许 MCP Server 并发读写
    // busy_timeout：等待锁释放，避免 SQLITE_BUSY
    db.SetMaxOpenConns(1)  // SQLite 单写者模型
    return &Connection{db: db}
}
```

**并发安全策略：**
- WAL 模式：允许多个读者 + 一个写者并发
- `_busy_timeout=5000`：写入冲突时等待 5s 而非立即报错
- `MaxOpenConns(1)`：桌面端单连接，避免自身死锁
- 应用内 `sync.RWMutex`：保护 Go 侧并发调用

### 3.4 Embedding 引擎

桌面端不内嵌 ONNX Runtime（体积大、CGo 交叉编译复杂），改用 Python 子进程：

```go
// internal/embedding/engine.go
type Engine struct {
    pythonPath string  // 自动检测或用户配置
}

func (e *Engine) Encode(texts []string) ([][]float32, error) {
    // 写入临时 JSON 文件
    input := map[string]any{"texts": texts}
    tmpFile := writeTempJSON(input)
    defer os.Remove(tmpFile)

    // 调用 Python
    cmd := exec.Command(e.pythonPath, "-c",
        "import json,sys;from aivectormemory.embedding.engine import EmbeddingEngine;"+
        "e=EmbeddingEngine();d=json.load(open(sys.argv[1]));"+
        "r=[e.encode(t).tolist() for t in d['texts']];print(json.dumps(r))",
        tmpFile)

    output, err := cmd.Output()
    // 解析 JSON 输出为 [][]float32
    return parseEmbeddings(output), err
}

func (e *Engine) BatchRepair(ids []string, contents []string, onProgress func(done, total int)) error {
    // 分批处理，每批 50 条
    // 通过 Wails EventsEmit 推送进度到前端
}
```

**Python 路径检测顺序：**
1. 用户设置中的自定义路径
2. `which python3`
3. `which python`
4. 常见路径（`/usr/bin/python3`、`/usr/local/bin/python3`）

### 3.5 Go Binding 接口设计

前端通过 Wails binding 调用 Go 方法，按模块组织：

```go
// === 项目 ===
func (a *App) GetProjects() []Project
func (a *App) AddProject(dir string) error
func (a *App) DeleteProject(dir string) error

// === 统计 ===
func (a *App) GetStats(projectDir string) Stats

// === 记忆 ===
func (a *App) GetMemories(projectDir string, scope string, query string, page int, pageSize int) MemoryPage
func (a *App) GetMemoryDetail(id string, projectDir string) Memory
func (a *App) UpdateMemory(id string, content string, tags []string) error
func (a *App) DeleteMemory(id string, projectDir string) error
func (a *App) DeleteMemoriesBatch(ids []string, projectDir string) error
func (a *App) SearchMemories(projectDir string, query string, topK int) []Memory
func (a *App) ExportMemories(projectDir string, scope string) ExportData
func (a *App) ImportMemories(projectDir string, data ImportData) ImportResult

// === 问题 ===
func (a *App) GetIssues(projectDir string, opts IssueFilter) IssuePage
func (a *App) GetIssueDetail(issueNumber int, projectDir string) Issue
func (a *App) CreateIssue(projectDir string, issue IssueInput) CreateResult
func (a *App) UpdateIssue(issueNumber int, projectDir string, data IssueUpdate) error
func (a *App) ArchiveIssue(issueNumber int, projectDir string) error
func (a *App) DeleteIssue(issueNumber int, projectDir string, isArchived bool) error

// === 任务 ===
func (a *App) GetTasks(projectDir string, opts TaskFilter) []TaskGroup
func (a *App) GetArchivedTasks(projectDir string, featureID string) []TaskGroup
func (a *App) CreateTasks(projectDir string, featureID string, tasks []TaskInput) error
func (a *App) UpdateTask(id int, data TaskUpdate) error
func (a *App) DeleteTask(id int) error
func (a *App) DeleteTasksByFeature(projectDir string, featureID string) error

// === 标签 ===
func (a *App) GetTags(projectDir string, query string) TagList
func (a *App) RenameTag(projectDir string, oldName string, newName string) int
func (a *App) MergeTags(projectDir string, sources []string, target string) int
func (a *App) DeleteTags(projectDir string, names []string) int

// === 会话状态 ===
func (a *App) GetStatus(projectDir string) SessionState
func (a *App) UpdateStatus(projectDir string, data StatusUpdate) error

// === 数据维护 ===
func (a *App) HealthCheck() HealthReport
func (a *App) RepairMissingEmbeddings() // 异步，通过事件推送进度
func (a *App) RebuildAllEmbeddings()    // 异步
func (a *App) GetDBStats() DBStats
func (a *App) BackupDB(targetDir string) string
func (a *App) RestoreDB(backupPath string) error

// === Web 看板 ===
func (a *App) LaunchWebDashboard() error
func (a *App) StopWebDashboard() error
func (a *App) IsWebDashboardRunning() bool

// === 设置 ===
func (a *App) GetSettings() Settings
func (a *App) SaveSettings(s Settings) error

// === 系统 ===
func (a *App) BrowseDirectory(path string) BrowseResult
func (a *App) SelectDirectory() string  // 调用原生文件对话框
```

## 4. 前端设计

### 4.1 路由结构

```
/                       → ProjectSelect（项目选择首页）
/:projectDir/           → 进入项目后的布局
  ├── stats             → 统计概览
  ├── status            → 会话状态
  ├── issues            → 问题追踪
  ├── tasks             → 任务管理
  ├── project-memories  → 项目记忆
  ├── user-memories     → 全局记忆
  ├── tags              → 标签管理
  ├── maintenance       → 数据维护（新增）
  └── settings          → 应用设置（新增）
```

### 4.2 主题系统

通过 CSS 变量实现亮色/暗色切换：

```css
/* variables.css */
:root {
    --bg-primary: #0F172A;
    --bg-surface: #1E293B;
    --bg-sidebar: #0B1120;
    --text-primary: #F1F5F9;
    --text-secondary: #94A3B8;
    --text-muted: #64748B;
    --border: #334155;
    --accent: #3B82F6;
    --accent-hover: #2563EB;
    /* ... */
}

[data-theme="light"] {
    --bg-primary: #F8FAFC;
    --bg-surface: #FFFFFF;
    --bg-sidebar: #F1F5F9;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #94A3B8;
    --border: #E2E8F0;
    --accent: #2563EB;
    --accent-hover: #1D4ED8;
    /* ... */
}
```

**主题跟随系统：**
```ts
// stores/theme.ts
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
mediaQuery.addEventListener('change', (e) => {
    if (settings.theme === 'system') {
        applyTheme(e.matches ? 'dark' : 'light')
    }
})
```

### 4.3 侧边栏导航

桌面端相比 Web 看板增加两个导航项：

| 导航项 | 图标 | 对应需求 |
|--------|------|----------|
| 统计概览 | grid | 2.1 |
| 会话状态 | activity | 2.5 + 3.5 |
| 问题跟踪 | alert-circle | 2.3 |
| 任务管理 | check-square | 2.4 |
| 项目记忆 | folder | 2.2 |
| 全局记忆 | user | 2.2 |
| 标签管理 | tag | 2.7 |
| **数据维护** | **wrench** | **3.1-3.4** |
| **设置** | **settings** | **6** |

底部固定：
- Web 看板启动按钮（3.6）
- 主题切换开关

### 4.4 新增页面设计

#### 数据维护页（MaintenanceView）

```
┌─────────────────────────────────────────────────┐
│  数据维护                                        │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌── 数据库概览 ─────────────────────────────┐   │
│  │  文件大小: 12.5 MB                         │   │
│  │  路径: ~/.aivectormemory/memory.db         │   │
│  │                                            │   │
│  │  memories: 184    vec_memories: 182         │   │
│  │  user_memories: 23  vec_user_memories: 23   │   │
│  │  issues: 12      issues_archive: 45         │   │
│  │  tasks: 28       tasks_archive: 15          │   │
│  │  session_state: 3                           │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
│  ┌── 健康检查 ───────────────────────────────┐   │
│  │  ● memories: 184 条, 缺失 embedding 2 条   │   │
│  │  ● user_memories: 23 条, 全部正常           │   │
│  │  ● 孤立向量: 0 条                          │   │
│  │                                            │   │
│  │  [修复缺失 embedding]  [重建全部 embedding]  │   │
│  │                                            │   │
│  │  ████████████░░░░░░░░  45/184 (24%)        │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
│  ┌── 备份管理 ───────────────────────────────┐   │
│  │  [备份数据库]  [从备份恢复]                  │   │
│  │                                            │   │
│  │  最近备份:                                  │   │
│  │  - memory_20260307_143022.db  (12.5 MB)    │   │
│  │  - memory_20260305_091500.db  (11.8 MB)    │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
└─────────────────────────────────────────────────┘
```

#### 设置页（SettingsView）

```
┌─────────────────────────────────────────────────┐
│  设置                                            │
├─────────────────────────────────────────────────┤
│                                                  │
│  外观                                            │
│  ┌────────────────────────────────────────────┐   │
│  │  主题        [暗色 ▾]  (暗色/亮色/跟随系统)  │   │
│  │  语言        [简体中文 ▾]                    │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
│  数据                                            │
│  ┌────────────────────────────────────────────┐   │
│  │  数据库路径   ~/.aivectormemory/memory.db    │   │
│  │              [浏览...]                      │   │
│  │  Python 路径  /usr/bin/python3  (自动检测)   │   │
│  │              [浏览...]                      │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
│  Web 看板                                        │
│  ┌────────────────────────────────────────────┐   │
│  │  端口         [9080]                        │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
│  系统                                            │
│  ┌────────────────────────────────────────────┐   │
│  │  开机自启动   [  OFF  ]                     │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
│  关于                                            │
│  ┌────────────────────────────────────────────┐   │
│  │  版本 1.0.0 · Go 1.21 · Wails 2.9         │   │
│  │  GitHub: github.com/Edlineas/aivectormemory │   │
│  └────────────────────────────────────────────┘   │
│                                                  │
└─────────────────────────────────────────────────┘
```

#### 会话状态编辑（StatusView 增强）

在现有只读展示基础上增加编辑能力：
- 每个字段右侧显示编辑按钮
- 点击进入行内编辑模式
- `is_blocked` 用 Toggle Switch 切换
- `progress`、`recent_changes`、`pending` 列表支持增删条目

## 5. 设置管理

### 配置文件

```json
// ~/.aivectormemory/desktop.json
{
    "theme": "system",           // "dark" | "light" | "system"
    "language": "zh-CN",
    "db_path": "~/.aivectormemory/memory.db",
    "python_path": "",           // 空 = 自动检测
    "web_port": 9080,
    "auto_start": false,
    "window": {
        "width": 1200,
        "height": 800,
        "x": -1,
        "y": -1
    },
    "last_project": ""           // 记住上次打开的项目
}
```

### 开机自启动实现

| 平台 | 方案 | 路径 |
|------|------|------|
| macOS | Launch Agent plist | `~/Library/LaunchAgents/com.aivectormemory.desktop.plist` |
| Windows | 注册表 Run key | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| Linux | XDG autostart desktop 文件 | `~/.config/autostart/aivectormemory-desktop.desktop` |

## 6. Web 看板启动器

```go
// internal/webserver/launcher.go
type Launcher struct {
    cmd    *exec.Cmd
    port   int
    mu     sync.Mutex
}

func (l *Launcher) Start(pythonPath string, port int) error {
    l.mu.Lock()
    defer l.mu.Unlock()

    if l.cmd != nil && l.cmd.Process != nil {
        return errors.New("already running")
    }

    l.cmd = exec.Command(pythonPath, "-m", "aivectormemory", "web", "--port", strconv.Itoa(port))
    // Detach: 桌面端关闭后子进程继续运行
    l.cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
    err := l.cmd.Start()
    if err != nil {
        return err
    }

    l.port = port
    // 等待服务就绪后打开浏览器
    go l.waitAndOpenBrowser()
    return nil
}

func (l *Launcher) waitAndOpenBrowser() {
    url := fmt.Sprintf("http://localhost:%d", l.port)
    for i := 0; i < 30; i++ {
        resp, err := http.Get(url)
        if err == nil {
            resp.Body.Close()
            runtime.BrowserOpenURL(l.ctx, url)
            return
        }
        time.Sleep(500 * time.Millisecond)
    }
}
```

## 7. 构建与分发

### Wails 构建命令

```bash
# 开发模式（热重载）
wails dev

# 生产构建
wails build -platform darwin/universal  # macOS (Intel + Apple Silicon)
wails build -platform windows/amd64     # Windows
wails build -platform linux/amd64       # Linux
```

### 产物

| 平台 | 格式 | 说明 |
|------|------|------|
| macOS | `.app` → `.dmg` | Universal Binary (arm64 + amd64) |
| Windows | `.exe` | 可选 NSIS 安装包 |
| Linux | `AppImage` | 便携格式，无需安装 |

### CGo 依赖

`mattn/go-sqlite3` 需要 CGo 编译：
- macOS：Xcode Command Line Tools
- Windows：MinGW-w64 或 MSYS2
- Linux：`gcc` + `libsqlite3-dev`

sqlite-vec 扩展：
- 编译为动态库（`.dylib` / `.dll` / `.so`），随应用打包
- 应用启动时通过 `sqlite3_load_extension` 加载

## 8. 数据流示例

### 记忆搜索（语义向量）

```
用户输入搜索词
  → Vue SearchBox 组件 @input (防抖 300ms)
  → 调用 window.go.main.App.SearchMemories(projectDir, query, 20)
  → Go: SearchMemories()
    → db.QueryEmbedding(query)  // 先生成搜索词的 embedding
      → embedding.Engine.Encode([query])
    → db.VectorSearch(embedding, topK)
      → SQL: SELECT m.*, vec_distance_cosine(v.embedding, ?) AS distance
              FROM memories m JOIN vec_memories v ON m.id = v.id
              WHERE m.project_dir = ? ORDER BY distance LIMIT ?
    → 返回 []Memory（含 similarity 分数）
  → Vue 渲染 MemoryCard 列表
```

### 修复缺失 embedding

```
用户点击 [修复缺失 embedding]
  → 调用 window.go.main.App.RepairMissingEmbeddings()
  → Go: RepairMissingEmbeddings()（异步 goroutine）
    → 查询缺失列表: SELECT id, content FROM memories
                     WHERE id NOT IN (SELECT id FROM vec_memories)
    → 分批调用 embedding.Engine.Encode(batch)
    → 逐条 INSERT INTO vec_memories (id, embedding)
    → runtime.EventsEmit(ctx, "repair:progress", {done: 45, total: 184})
  → 前端监听 "repair:progress" 事件更新进度条
  → 完成后 runtime.EventsEmit(ctx, "repair:done")
```

## 9. 需求覆盖矩阵

| 需求章节 | 对应前端视图 | 对应 Go 模块 |
|----------|-------------|-------------|
| 2.1 统计概览 | StatsView | db/memories, db/issues |
| 2.2 记忆管理 | MemoriesView | db/memories |
| 2.3 问题追踪 | IssuesView | db/issues |
| 2.4 任务管理 | TasksView | db/tasks |
| 2.5 会话状态 | StatusView | db/status |
| 2.6 项目管理 | ProjectSelect | db/projects |
| 2.7 标签管理 | TagsView | db/tags |
| 3.1 健康检查 | MaintenanceView | db/health |
| 3.2 数据修复 | MaintenanceView | embedding/engine |
| 3.3 数据库统计 | MaintenanceView | db/health |
| 3.4 备份恢复 | MaintenanceView | backup/backup |
| 3.5 状态编辑 | StatusView | db/status |
| 3.6 Web 看板 | Sidebar (底部按钮) | webserver/launcher |
| 4. 多语言 | i18n/* | - |
| 5. 通用交互 | components/common/* | - |
| 6. 应用设置 | SettingsView | settings/manager |
