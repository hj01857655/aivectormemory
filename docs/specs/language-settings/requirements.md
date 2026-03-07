# Language Settings - 需求文档

## 背景

当前规则（STEERING_CONTENT、inject-workflow-rules.sh）中的语言是硬编码的。compact/context transfer 后 AI 回复语言会漂移。需要一个可配置的语言设置机制，安装时选择，运行时动态生效。

## 功能范围

### 1. 安装时语言选择
- `aivectormemory install` 增加语言选择步骤
- 可选语言：中文、English、日本語 等（可扩展）
- 选择结果写入数据库

### 2. 数据库存储
- `session_state` 表增加 `language` 字段
- 新增 migration（v08）添加字段，默认值为空字符串
- 空值 = 未设置，运行时默认中文

### 3. 规则注入动态化
- `inject-workflow-rules.sh`（包源）从数据库读取 language，动态注入 Language 行
- 有值 → 注入用户选的语言
- 无值 → 默认注入中文
- install.py 安装 hook 时同步更新
- CLAUDE.md / STEERING_CONTENT 中的语言规则改为动态占位符或移除（由 hook 注入覆盖）

### 4. 看板/桌面端 UI 语言
- 读取数据库 language 字段作为默认 UI 语言
- 看板和桌面端设置页面可修改语言
- 修改后写回数据库，下次规则注入即生效

### 5. 升级兼容
- 老用户升级后 language 为空，默认中文，行为不变
- 用户可通过重新 install 或设置页面设置语言
- 不强制、不阻断

## 验收标准

1. `aivectormemory install` 时可选语言，选择结果持久化
2. inject-workflow-rules.sh 根据数据库语言设置动态注入 Language 行
3. 看板/桌面端设置页面可查看和修改语言
4. 老用户升级后默认中文，无感知
5. 修改语言后下次对话即生效（无需重启 IDE）
