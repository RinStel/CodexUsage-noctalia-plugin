# CodexUsage for Noctalia

这个目录提供 Noctalia 与 Quickshell 版本的 CodexUsage 小组件。它保留 macOS 版本的数据语义，使用独立数据提供器读取本机 `~/.codex` 和 `codex app-server`，再由 QML 组件展示额度、token 用量、本月 API 等效价值和今日任务看板。

## 文件结构

```text
noctalia/
  manifest.json
  DesktopWidget.qml
  scripts/codexusage-json
  scripts/codexusage_json.py
  tests/test_codexusage_json.py
```

`scripts/codexusage-json` 输出 JSON，字段与 macOS 版本的 `make probe` 基本一致。QML 层只消费这些字段，避免重复实现 Codex 数据解析。

## 集成方式

将 `noctalia/` 作为插件目录链接到 Noctalia 的插件目录：

```sh
cd ~/Develop/codexusage-noctalia-plugin
noctalia/scripts/install-plugin
```

该命令会建立插件目录链接，并向 `~/.config/noctalia/plugins.json` 登记 `codexusage`：

```json
{
  "states": {
    "codexusage": {
      "enabled": true,
      "sourceUrl": "local"
    }
  }
}
```

重启 Noctalia 后，插件页会显示 `CodexUsage`。启用后可以在桌面小组件列表中添加。

数据提供器默认读取：

```text
~/.codex/state_5.sqlite
~/.codex/sqlite/state_5.sqlite
~/.codex/automations/**/automation.toml
codex app-server
```

如果 Codex 数据目录位于其他位置，可以设置：

```sh
CODEXUSAGE_CODEX_HOME=/path/to/.codex noctalia/scripts/codexusage-json
```

在 NixOS 上，插件运行时需要能找到 Python。推荐将 `python3` 加入系统或 Home Manager 包，让 Noctalia 刷新小组件时使用常驻运行时。

示例：

```nix
home.packages = with pkgs; [
  python3
];
```

## 本地检查

```sh
command -v python3
noctalia/scripts/codexusage-json
python3 -m unittest noctalia.tests.test_codexusage_json
```

输出 JSON 中的核心字段：

```text
primary.remainingPercent
secondary.remainingPercent
local.todayTokens
local.sevenDayTokens
local.lifetimeTokens
local.detailedUsage.month.estimatedCostUSD
local.valueProjection.projectedUSD
local.valueProjection.elapsedFraction
taskBoard.columns
messages
```

## 独立仓库发布

如果准备先以独立 GitHub 仓库发布 Noctalia 插件，可以先导出一份干净的插件仓库目录：

```sh
make noctalia-export-repo
```

默认会生成：

```text
dist/codexusage-noctalia-plugin
```

这个目录只保留适合独立插件仓库发布的文件：

```text
DesktopWidget.qml
Settings.qml
manifest.json
README.md
LICENSE
scripts/codexusage-json
scripts/codexusage_json.py
tests/test_codexusage_json.py
```

如果已经有独立仓库地址和预览图，也可以在导出时一起写入：

```sh
noctalia/scripts/export-standalone-repo \
  --repository-url https://github.com/<you>/codexusage-noctalia-plugin \
  --preview /path/to/preview.png
```

建议后续在该独立仓库里补齐：

1. `preview.png`，建议 `960x540`
2. release tag
3. 面向 Noctalia 用户的安装说明

## 与 macOS 版本的关系

macOS 版本继续由 `Sources/CodexUsageWidget/main.swift`、`Resources/` 和 `Makefile` 构建。Noctalia 版本位于独立目录，复用同一套数据含义，并用 Python 数据提供器替代 SwiftUI/AppKit 应用外壳。
