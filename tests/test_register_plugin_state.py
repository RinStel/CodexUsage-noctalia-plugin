#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "register-plugin-state.py"
SPEC = importlib.util.spec_from_file_location("register_plugin_state", MODULE_PATH)
register_plugin_state = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["register_plugin_state"] = register_plugin_state
SPEC.loader.exec_module(register_plugin_state)


class RegisterPluginStateTests(unittest.TestCase):
    def test_sync_widget_defaults_normalizes_scale_and_defaults(self) -> None:
        widget = {
            "id": "plugin:codexusage",
            "defaultSettings": {"showMessages": False},
            "scale": "invalid",
        }

        changed = register_plugin_state.sync_widget_defaults(widget)

        self.assertTrue(changed)
        self.assertEqual(widget["scale"], 1)
        self.assertEqual(widget["defaultSettings"], register_plugin_state.DEFAULT_WIDGET_SETTINGS)

    def test_sync_widget_defaults_is_idempotent(self) -> None:
        widget = {
            "id": "plugin:codexusage",
            "defaultSettings": dict(register_plugin_state.DEFAULT_WIDGET_SETTINGS),
            "scale": 1.0,
        }

        changed = register_plugin_state.sync_widget_defaults(widget)

        self.assertFalse(changed)
        self.assertEqual(widget["defaultSettings"], register_plugin_state.DEFAULT_WIDGET_SETTINGS)
        self.assertEqual(widget["scale"], 1.0)

    def test_ensure_plugin_state_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp)

            changed_first = register_plugin_state.ensure_plugin_state(config_home)
            changed_second = register_plugin_state.ensure_plugin_state(config_home)

            plugins_json = config_home / "noctalia" / "plugins.json"
            payload = json.loads(plugins_json.read_text(encoding="utf-8"))

            self.assertTrue(changed_first)
            self.assertFalse(changed_second)
            self.assertEqual(
                payload["states"]["codexusage"],
                {"enabled": True, "sourceUrl": "local"},
            )

    def test_sync_existing_widget_settings_updates_noctalia_settings_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp)
            settings_json = config_home / "noctalia" / "settings.json"
            settings_json.parent.mkdir(parents=True, exist_ok=True)
            settings_json.write_text(
                json.dumps(
                    {
                        "noctaliaPerformance": {"disableDesktopWidgets": True},
                        "desktopWidgets": {
                            "monitorWidgets": [
                                {
                                    "widgets": [
                                        {
                                            "id": "plugin:codexusage",
                                            "defaultSettings": {},
                                            "scale": "bad",
                                        }
                                    ]
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            changed_first = register_plugin_state.sync_existing_widget_settings(config_home)
            changed_second = register_plugin_state.sync_existing_widget_settings(config_home)
            payload = json.loads(settings_json.read_text(encoding="utf-8"))
            widget = payload["desktopWidgets"]["monitorWidgets"][0]["widgets"][0]

            self.assertTrue(changed_first)
            self.assertFalse(changed_second)
            self.assertEqual(payload["noctaliaPerformance"]["disableDesktopWidgets"], False)
            self.assertEqual(widget["defaultSettings"], register_plugin_state.DEFAULT_WIDGET_SETTINGS)
            self.assertEqual(widget["scale"], 1)


if __name__ == "__main__":
    unittest.main()
