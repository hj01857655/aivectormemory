# CI/CD Release 工作流设计文档

## 架构总览

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│  私有仓库: aivectormemory-dev   │     │  公开仓库: aivectormemory     │
│                                 │     │                              │
│  源码 + .github/workflows/     │     │  README*.md                  │
│                                 │     │  Releases/                   │
│  push tag v* ──────────────────────▶  │    ├── v1.0.6-macos-arm64.zip│
│               GitHub Actions    │     │    ├── v1.0.6-macos-x64.zip │
│               构建 3 平台       │     │    ├── v1.0.6-windows.zip   │
│               发布到公开仓库 ───────▶  │    └── v1.0.6-linux.tar.gz  │
└─────────────────────────────────┘     └──────────────────────────────┘
```

## 1. 仓库迁移方案

### 1.1 创建私有仓库

```bash
# GitHub CLI 创建私有仓库
gh repo create Edlineas/aivectormemory-dev --private

# 添加新 remote
git remote add private https://github.com/Edlineas/aivectormemory-dev.git

# 推送所有分支到私有仓库
git push private dev
git push private main
```

### 1.2 Remote 管理

迁移后本地 git remote 配置：

| Remote | URL | 用途 |
|--------|-----|------|
| `origin` | `Edlineas/aivectormemory-dev` (私有) | 日常开发，推送源码 |
| `public` | `Edlineas/aivectormemory` (公开) | 推送 README，接收 Release |

将 `origin` 切换到私有仓库，公开仓库改名为 `public`：

```bash
git remote set-url origin https://github.com/Edlineas/aivectormemory-dev.git
git remote rename origin origin  # 保持不变
git remote add public https://github.com/Edlineas/aivectormemory.git
# 或者直接：
git remote set-url origin https://github.com/Edlineas/aivectormemory-dev.git
git remote add public https://github.com/Edlineas/aivectormemory.git
```

## 2. GitHub Actions Workflow 设计

### 2.1 Workflow 文件

`.github/workflows/release.yml` — 存放在私有仓库

### 2.2 触发条件

```yaml
on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      tag:
        description: 'Tag to build (e.g. v1.0.6)'
        required: true
```

### 2.3 构建矩阵

| Job | Runner | GOOS/GOARCH | 产物 | 特殊依赖 |
|-----|--------|-------------|------|---------|
| build-macos-arm64 | `macos-14` (Apple Silicon) | darwin/arm64 | `AIVectorMemory-{ver}-macos-arm64.zip` | Xcode CLT (自带) |
| build-macos-x64 | `macos-13` (Intel) | darwin/amd64 | `AIVectorMemory-{ver}-macos-x64.zip` | Xcode CLT (自带) |
| build-windows | `windows-latest` | windows/amd64 | `AIVectorMemory-{ver}-windows.zip` | mingw-w64 (choco install) |
| build-linux | `ubuntu-latest` | linux/amd64 | `AIVectorMemory-{ver}-linux.tar.gz` | gcc, webkit2gtk-4.0, pkg-config |

### 2.4 sqlite-vec 扩展处理

桌面端通过 `load_extension()` 动态加载 vec0。构建时需要：

1. 从 sqlite-vec GitHub Release 下载对应平台的预编译二进制
2. 打包到产物 zip 中（与可执行文件同级目录）
3. 安装时由安装脚本/用户放置到 `~/.aivectormemory/`

**sqlite-vec 下载源**：`https://github.com/asg017/sqlite-vec/releases`

| 平台 | 文件 |
|------|------|
| macOS arm64 | `sqlite-vec-{ver}-loadable-macos-aarch64.tar.gz` → `vec0.dylib` |
| macOS x64 | `sqlite-vec-{ver}-loadable-macos-x86_64.tar.gz` → `vec0.dylib` |
| Windows x64 | `sqlite-vec-{ver}-loadable-windows-x86_64.zip` → `vec0.dll` |
| Linux x64 | `sqlite-vec-{ver}-loadable-linux-x86_64.tar.gz` → `vec0.so` |

### 2.5 单个 Job 构建步骤

```
1. Checkout 代码
2. Setup Go 1.23
3. Setup Node.js (前端构建)
4. Install Wails CLI
5. Install 平台依赖 (Linux: webkit2gtk, Windows: mingw-w64)
6. cd desktop && wails build
7. 下载 sqlite-vec 预编译二进制
8. 打包产物 (可执行文件 + vec0 扩展 + README)
9. Upload artifact
```

### 2.6 Release Job

所有平台构建完成后，单独的 `release` job：

```
1. Download 所有平台的 artifacts
2. 使用 softprops/action-gh-release 发布到公开仓库
3. 需要 PAT (Personal Access Token) 作为 secret
```

## 3. Secrets 配置

私有仓库需要配置的 Secrets：

| Secret 名称 | 说明 |
|-------------|------|
| `PUBLIC_REPO_TOKEN` | GitHub PAT，需要 `repo` scope，用于向公开仓库发布 Release |

PAT 创建方式：GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
- Repository access: `Edlineas/aivectormemory`
- Permissions: Contents (Read and write)

## 4. README 同步方案

手动方式（推荐，简单可控）：

```bash
# 更新 README 到公开仓库
git checkout main
git checkout dev -- README.md README_EN.md README_JA.md
git add README*.md
git commit -m "docs: 更新README"
git push public main
```

可选：在私有仓库增加 `sync-readme.yml` workflow 自动同步。

## 5. 产物命名规范

```
AIVectorMemory-v{version}-{platform}-{arch}.{ext}

示例：
AIVectorMemory-v1.0.6-macos-arm64.zip
AIVectorMemory-v1.0.6-macos-x64.zip
AIVectorMemory-v1.0.6-windows-x64.zip
AIVectorMemory-v1.0.6-linux-x64.tar.gz
```

zip/tar.gz 内容：
```
AIVectorMemory-v1.0.6-macos-arm64/
├── AIVectorMemory.app/  (macOS) 或 AIVectorMemory.exe (Windows) 或 AIVectorMemory (Linux)
├── vec0.dylib           (macOS) 或 vec0.dll (Windows) 或 vec0.so (Linux)
├── install.sh           (macOS/Linux) 或 install.bat (Windows)
└── README.md
```

`install.sh` 脚本功能：
- 将 vec0 扩展复制到 `~/.aivectormemory/`
- macOS: 将 .app 复制到 `/Applications/`（可选）
- Linux: 创建 .desktop 文件（可选）

## 6. Workflow YAML 核心结构

```yaml
name: Build and Release Desktop App

on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      tag:
        required: true

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: macos-14
            goos: darwin
            goarch: arm64
            platform: macos-arm64
          - os: macos-13
            goos: darwin
            goarch: amd64
            platform: macos-x64
          - os: windows-latest
            goos: windows
            goarch: amd64
            platform: windows-x64
          - os: ubuntu-latest
            goos: linux
            goarch: amd64
            platform: linux-x64
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version: '1.23' }
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - name: Install Wails
        run: go install github.com/wailsapp/wails/v2/cmd/wails@latest
      - name: Install Linux deps
        if: matrix.goos == 'linux'
        run: sudo apt-get update && sudo apt-get install -y libgtk-3-dev libwebkit2gtk-4.0-dev
      - name: Build
        working-directory: desktop
        run: wails build
      - name: Download sqlite-vec
        # 下载对应平台的 vec0 预编译二进制
      - name: Package
        # 打包可执行文件 + vec0 + install 脚本
      - uses: actions/upload-artifact@v4

  release:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
      - uses: softprops/action-gh-release@v2
        with:
          repository: Edlineas/aivectormemory
          token: ${{ secrets.PUBLIC_REPO_TOKEN }}
          files: |
            artifacts/*
```

## 7. 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| macOS 无签名 | Gatekeeper 警告 | 用户右键打开或 `xattr -d` 清除 |
| sqlite-vec 版本不匹配 | 扩展加载失败 | 固定 sqlite-vec 版本号，与 Go sqlite3 版本对齐 |
| Windows CGO | 编译失败 | 使用 choco install mingw，设置 CGO_ENABLED=1 |
| Linux webkit2gtk | 构建失败 | apt-get 安装 libwebkit2gtk-4.0-dev |
| GitHub Actions 免费额度 | 构建超限 | macOS runner 10x 计费，注意控制触发频率 |

## 8. 免费额度说明

GitHub Free 账户每月 2000 分钟：
- Linux: 1x 计费
- Windows: 2x 计费
- macOS: 10x 计费

一次完整构建预估：
- macOS arm64: ~5 min × 10 = 50 min
- macOS x64: ~5 min × 10 = 50 min
- Windows: ~5 min × 2 = 10 min
- Linux: ~3 min × 1 = 3 min
- **单次发布约 113 分钟额度**，每月可发布 ~17 次
