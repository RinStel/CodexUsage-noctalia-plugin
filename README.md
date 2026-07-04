# codexU for Noctalia

这是一个面向 Noctalia v4 的 Codex 用量统计桌面小组件插件。

它读取本机 `~/.codex` 与 `codex app-server`，展示账户额度、token 用量、本月 API 等效价值和任务看板。

## 文件结构

```text
manifest.json
DesktopWidget.qml
Settings.qml
scripts/codexu-json
scripts/codexu_json.py
tests/test_codexu_json.py
```

## 安装

将仓库克隆到 Noctalia 的插件目录：

```sh
git clone <repository-url> ~/.config/noctalia/plugins/codexu
```

如果 `~/.config/noctalia/plugins.json` 里还没有 `codexu`，加入：

```json
{
  "states": {
    "codexu": {
      "enabled": true,
      "sourceUrl": "local"
    }
  }
}
```

重启 Noctalia 后，可以在插件页启用 `codexU`，再到桌面小组件中添加。

## 运行依赖

插件默认读取：

```text
~/.codex/state_5.sqlite
~/.codex/sqlite/state_5.sqlite
~/.codex/automations/**/automation.toml
codex app-server
```

系统需要提供 `python3`。

如果 `codex app-server` 不可用，插件会进入 partial-data 模式，继续显示本地统计和任务看板。

如果 Codex 数据目录位于其他位置：

```sh
CODEXU_CODEX_HOME=/path/to/.codex scripts/codexu-json
```

## 本地检查

```sh
command -v python3
scripts/codexu-json
python3 -m unittest tests.test_codexu_json
```
