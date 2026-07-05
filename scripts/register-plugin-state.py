#!/usr/bin/env python3
"""Register the local CodexUsage plugin in Noctalia's plugins.json."""

from __future__ import annotations

import json
import os
from pathlib import Path


MANIFEST_PATH = Path(__file__).resolve().parents[1] / "manifest.json"


def load_default_widget_settings() -> dict[str, object]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    defaults = ((manifest.get("metadata") or {}).get("defaultSettings") or {})
    return defaults if isinstance(defaults, dict) else {}


DEFAULT_WIDGET_SETTINGS = load_default_widget_settings()


def _coerce_scale(value):
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return None
    return scale if 0.1 <= scale <= 10.0 else None


def sync_widget_defaults(widget: dict[str, object]) -> bool:
    changed = False
    defaults = widget.get("defaultSettings")
    merged_defaults = dict(defaults) if isinstance(defaults, dict) else {}
    for key, value in DEFAULT_WIDGET_SETTINGS.items():
        if merged_defaults.get(key) != value:
            merged_defaults[key] = value
            changed = True
    if defaults != merged_defaults:
        widget["defaultSettings"] = merged_defaults
        changed = True

    scale = _coerce_scale(widget.get("scale"))
    normalized_scale = 1 if scale is None else scale
    if widget.get("scale") != normalized_scale:
        widget["scale"] = normalized_scale
        changed = True
    return changed


def sync_existing_widget_settings(config_home: Path) -> bool:
    settings_json = config_home / "noctalia" / "settings.json"
    if not settings_json.exists():
        return False

    data = json.loads(settings_json.read_text(encoding="utf-8"))
    performance = data.setdefault("noctaliaPerformance", {})
    if performance.get("disableDesktopWidgets") is True:
        performance["disableDesktopWidgets"] = False
        changed = True
    else:
        changed = False

    widgets_by_monitor = (
        data.get("desktopWidgets", {})
        .get("monitorWidgets", [])
    )

    for monitor in widgets_by_monitor:
        for widget in monitor.get("widgets", []):
            if widget.get("id") != "plugin:codexusage":
                continue
            changed = sync_widget_defaults(widget) or changed

    if changed:
        settings_json.write_text(
            json.dumps(data, ensure_ascii=False, indent=4, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Updated CodexUsage desktop widget defaults in {settings_json}")
    return changed


def ensure_plugin_state(config_home: Path) -> bool:
    plugins_json = config_home / "noctalia" / "plugins.json"
    plugins_json.parent.mkdir(parents=True, exist_ok=True)

    if plugins_json.exists():
        data = json.loads(plugins_json.read_text(encoding="utf-8"))
    else:
        data = {"sources": [], "states": {}, "version": 2}

    data.setdefault("sources", [])
    data.setdefault("states", {})
    data.setdefault("version", 2)
    desired_state = {
        "enabled": True,
        "sourceUrl": "local"
    }
    if data["states"].get("codexusage") == desired_state:
        return False

    data["states"]["codexusage"] = desired_state
    plugins_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Registered CodexUsage in {plugins_json}")
    return True


def main() -> int:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    ensure_plugin_state(config_home)
    sync_existing_widget_settings(config_home)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
