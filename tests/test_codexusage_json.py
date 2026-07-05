#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "codexusage_json.py"
SPEC = importlib.util.spec_from_file_location("codexusage_json", MODULE_PATH)
codexusage_json = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["codexusage_json"] = codexusage_json
SPEC.loader.exec_module(codexusage_json)


class CodexUsageJsonTests(unittest.TestCase):
    def test_estimated_cost_uses_split_token_prices(self) -> None:
        tokens = codexusage_json.TokenBreakdown(
            input_tokens=1_000_000,
            cached_input_tokens=400_000,
            output_tokens=50_000,
            total_tokens=1_050_000,
        )

        pricing = codexusage_json.model_token_price("gpt-5.5")
        cost = codexusage_json.estimated_cost_usd(tokens, pricing, request_input_tokens=32_000)

        self.assertAlmostEqual(cost, 4.7)

    def test_estimated_cost_uses_long_context_prices_for_large_requests(self) -> None:
        tokens = codexusage_json.TokenBreakdown(
            input_tokens=200_000,
            cached_input_tokens=80_000,
            output_tokens=10_000,
            total_tokens=210_000,
        )

        pricing = codexusage_json.model_token_price("gpt-5.4")
        cost = codexusage_json.estimated_cost_usd(tokens, pricing, request_input_tokens=140_000)

        self.assertAlmostEqual(cost, 0.865)

    def test_model_token_price_uses_table_aliases(self) -> None:
        self.assertEqual(codexusage_json.model_token_price("chat-latest").label, "gpt-5.5")
        self.assertEqual(codexusage_json.model_token_price("gpt-5.2-codex").label, "gpt-5.2-codex")
        self.assertEqual(codexusage_json.model_token_price("gpt-5").label, "gpt-5")

    def test_model_token_price_falls_back_to_default_pricing(self) -> None:
        self.assertEqual(
            codexusage_json.model_token_price("unknown-model").label,
            codexusage_json.DEFAULT_MODEL_PRICING.label,
        )

    def test_monthly_value_projection_is_empty_without_month_usage(self) -> None:
        projection = codexusage_json.monthly_value_projection_object(None)

        self.assertEqual(projection["source"], "none")
        self.assertEqual(projection["currentUSD"], 0.0)
        self.assertEqual(projection["projectedUSD"], 0.0)

    def test_monthly_value_projection_uses_month_run_rate(self) -> None:
        usage = codexusage_json.PricedUsage(
            codexusage_json.TokenBreakdown(
                input_tokens=1_000_000,
                cached_input_tokens=0,
                output_tokens=0,
                total_tokens=1_000_000,
            ),
            estimated_cost_usd=10.0,
        )

        projection = codexusage_json.monthly_value_projection_object(
            usage,
            datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(projection["source"], "monthlyRunRate")
        self.assertEqual(projection["currentUSD"], 10.0)
        self.assertAlmostEqual(projection["elapsedFraction"], 0.5)
        self.assertAlmostEqual(projection["projectedUSD"], 20.0)

    def test_token_delta_resets_on_negative_values(self) -> None:
        previous = codexusage_json.TokenBreakdown(input_tokens=100, cached_input_tokens=20, output_tokens=30, total_tokens=130)
        current = codexusage_json.TokenBreakdown(input_tokens=10, cached_input_tokens=2, output_tokens=3, total_tokens=13)

        delta = current.delta_from(previous)

        self.assertEqual(delta.input_tokens, 10)
        self.assertEqual(delta.cached_input_tokens, 2)
        self.assertEqual(delta.output_tokens, 3)
        self.assertEqual(delta.total_tokens, 13)

    def test_rollout_usage_parses_token_count_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            events = [
                {
                    "timestamp": "2026-07-04T01:00:00Z",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100,
                                "cached_input_tokens": 20,
                                "output_tokens": 40,
                                "reasoning_output_tokens": 5,
                                "total_tokens": 140,
                            }
                        },
                    },
                },
                {
                    "timestamp": "2026-07-04T01:10:00Z",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 150,
                                "cached_input_tokens": 30,
                                "output_tokens": 70,
                                "reasoning_output_tokens": 9,
                                "total_tokens": 220,
                            }
                        },
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

            deltas, count = codexusage_json.parse_rollout_usage(path)

            self.assertEqual(count, 2)
            self.assertEqual(len(deltas), 2)
            self.assertEqual(deltas[0].tokens.visible_total_tokens, 140)
            self.assertEqual(deltas[1].tokens.input_tokens, 50)
            self.assertEqual(deltas[1].tokens.output_tokens, 30)
            self.assertEqual(deltas[1].request_input_tokens, 150)

    def test_cached_rollout_usage_reuses_file_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-07-04T01:00:00Z",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 20,
                                    "output_tokens": 40,
                                    "reasoning_output_tokens": 5,
                                    "total_tokens": 140,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            cache_entries: dict[str, object] = {}
            _, events_first, changed_first = codexusage_json.cached_rollout_usage(path, cache_entries)
            deltas_second, events_second, changed_second = codexusage_json.cached_rollout_usage(path, cache_entries)

            self.assertTrue(changed_first)
            self.assertEqual(events_first, 1)
            self.assertFalse(changed_second)
            self.assertEqual(events_second, 1)
            self.assertEqual(len(deltas_second), 1)
            self.assertEqual(deltas_second[0].request_input_tokens, 100)
            self.assertIn(str(path), cache_entries)

    def test_read_local_usage_from_fixture_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex"
            root.mkdir()
            db = root / "state_5.sqlite"
            rollout = root / "rollout.jsonl"
            now = int(datetime.now(timezone.utc).timestamp())
            rollout.write_text(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1000,
                                    "cached_input_tokens": 100,
                                    "output_tokens": 200,
                                    "reasoning_output_tokens": 20,
                                    "total_tokens": 1200,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            connection = sqlite3.connect(db)
            connection.execute(
                """
                CREATE TABLE threads (
                    id TEXT,
                    title TEXT,
                    preview TEXT,
                    cwd TEXT,
                    tokens_used INTEGER,
                    updated_at INTEGER,
                    recency_at INTEGER,
                    created_at INTEGER,
                    archived INTEGER,
                    archived_at INTEGER,
                    model TEXT,
                    rollout_path TEXT
                );
                """
            )
            connection.execute(
                """
                INSERT INTO threads VALUES (
                    'thread-1',
                    'Test title',
                    'Preview',
                    '/tmp/project',
                    1200,
                    ?,
                    ?,
                    ?,
                    0,
                    NULL,
                    'gpt-5',
                    ?
                );
                """,
                (now, now, now, str(rollout)),
            )
            connection.commit()
            connection.close()

            old_env = codexusage_json.os.environ.get("CODEXUSAGE_CODEX_HOME")
            codexusage_json.os.environ["CODEXUSAGE_CODEX_HOME"] = str(root)
            try:
                messages: list[str] = []
                local = codexusage_json.read_local_usage(messages)
                board = codexusage_json.read_task_board(messages)
            finally:
                if old_env is None:
                    codexusage_json.os.environ.pop("CODEXUSAGE_CODEX_HOME", None)
                else:
                    codexusage_json.os.environ["CODEXUSAGE_CODEX_HOME"] = old_env

            self.assertIsNotNone(local)
            self.assertEqual(local["todayTokens"], 1200)
            self.assertEqual(local["detailedUsage"]["today"]["tokens"]["totalTokens"], 1200)
            self.assertEqual(board["columns"][0]["count"], 1)
            self.assertEqual(board["columns"][0]["items"][0]["kind"], "active")

    def test_task_board_keeps_threads_with_title_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex"
            root.mkdir()
            db = root / "state_5.sqlite"
            now = int(datetime.now(timezone.utc).timestamp())
            connection = sqlite3.connect(db)
            connection.execute(
                """
                CREATE TABLE threads (
                    id TEXT,
                    title TEXT,
                    preview TEXT,
                    cwd TEXT,
                    tokens_used INTEGER,
                    updated_at INTEGER,
                    recency_at INTEGER,
                    created_at INTEGER,
                    archived INTEGER,
                    archived_at INTEGER,
                    model TEXT,
                    rollout_path TEXT
                );
                """
            )
            connection.execute(
                """
                INSERT INTO threads VALUES (
                    'thread-title-only',
                    'Title only task',
                    '',
                    '/tmp/project',
                    42,
                    ?,
                    ?,
                    ?,
                    0,
                    NULL,
                    'gpt-5',
                    ''
                );
                """,
                (now, now, now),
            )
            connection.commit()
            connection.close()

            old_env = codexusage_json.os.environ.get("CODEXUSAGE_CODEX_HOME")
            codexusage_json.os.environ["CODEXUSAGE_CODEX_HOME"] = str(root)
            try:
                messages: list[str] = []
                board = codexusage_json.read_task_board(messages)
            finally:
                if old_env is None:
                    codexusage_json.os.environ.pop("CODEXUSAGE_CODEX_HOME", None)
                else:
                    codexusage_json.os.environ["CODEXUSAGE_CODEX_HOME"] = old_env

            self.assertEqual(board["columns"][0]["count"], 1)
            self.assertEqual(board["columns"][0]["items"][0]["title"], "Title only task")


if __name__ == "__main__":
    unittest.main()
