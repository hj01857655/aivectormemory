# CI/CD Release 工作流需求文档

## 背景

项目当前公开仓库 `Edlineas/aivectormemory` 包含全部源码。用户希望：
- **不再公开源码**：公开仓库保留当前状态，后续只更新 README 和发布 Release
- **私有仓库开发**：全部源码存放在私有仓库，日常开发在私有仓库进行
- **自动化构建**：通过 GitHub Actions 在对应平台 runner 上构建桌面端应用
- **跨仓库发布**：构建产物发布到公开仓库的 Release

## 项目构成

| 组件 | 技术栈 | 产物 |
|------|--------|------|
| MCP Server（Python） | Python 3.10+, sqlite-vec, onnxruntime | PyPI 包 (`aivectormemory`) |
| 桌面端应用（Wails） | Go 1.23, Wails 2.11, Vue 3, mattn/go-sqlite3 | macOS .app/.dmg, Windows .exe, Linux AppImage |

## 需求范围

### 1. 仓库架构

- **私有仓库**（新建）：`Edlineas/aivectormemory-dev`（或用户指定名称）
  - 存放全部源码
  - 包含 GitHub Actions workflow 文件
  - 日常开发分支：`dev`，发布分支：`main`
- **公开仓库**（现有）：`Edlineas/aivectormemory`
  - 只维护 README 系列文件
  - 接收来自私有仓库的 Release 发布

### 2. 桌面端构建（GitHub Actions）

**构建平台**：
| 平台 | Runner | 产物格式 | CGO 依赖 |
|------|--------|---------|---------|
| macOS (Intel + Apple Silicon) | `macos-latest` | `.app` 压缩为 `.zip` 或 `.dmg` | mattn/go-sqlite3 需要 CGO |
| Windows | `windows-latest` | `.exe` | mingw-w64 gcc |
| Linux | `ubuntu-latest` | `AppImage` 或 `.tar.gz` | gcc + webkit2gtk-4.0 |

**构建依赖**：
- Go 1.23+
- Node.js（前端构建）
- Wails CLI (`wails build`)
- CGO 编译器（各平台不同）
- sqlite-vec 扩展（嵌入到 Go 二进制中，通过 mattn/go-sqlite3 编译）

**触发条件**：
- 推送 tag `v*`（如 `v1.0.6`）到私有仓库
- 手动触发（workflow_dispatch）

### 3. 跨仓库 Release 发布

- 构建完成后，使用 GitHub API 将产物发布到公开仓库 `Edlineas/aivectormemory` 的 Release
- 需要 Personal Access Token (PAT) 存储在私有仓库的 Secrets 中
- Release 包含：
  - 各平台安装包
  - 版本更新说明（从 tag message 或 CHANGELOG 提取）

### 4. README 同步（可选）

- 手动方式：在 `main` 分支 checkout 公开仓库，更新 README 后推送
- 自动方式（可选）：私有仓库的 workflow 检测 README 变更时自动同步到公开仓库

### 5. PyPI 发布（可选扩展）

- 当前手动发布流程不变
- 后续可在私有仓库 Actions 中增加 PyPI 自动发布

## 验收标准

1. 私有仓库创建完成，源码推送成功
2. 推送 `v*` tag 后，Actions 自动在 3 个平台构建桌面端应用
3. 构建产物自动发布到公开仓库的 Release 页面
4. 公开仓库 fork 用户只能看到 README + Release，看不到源码
5. README 更新流程可用（手动或自动）

## 注意事项

- CGO 交叉编译是主要技术风险，需要每个平台原生 runner
- macOS 构建可能需要处理 code signing（无证书时可跳过）
- sqlite-vec 扩展需要在各平台编译通过
- PAT 权限需要 `repo` scope（能操作公开仓库的 Release）
