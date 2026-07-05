#!/usr/bin/env python3
"""Produce CodexUsage JSON for Noctalia and other QML shells."""

from __future__ import annotations

import json
import os
import select
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


LONG_CONTEXT_INPUT_THRESHOLD = 128_000


@dataclass(frozen=True)
class PriceTier:
    input_price: float
    cached_input_price: float | None
    output_price: float

    @property
    def effective_cached_input_price(self) -> float:
        return self.input_price if self.cached_input_price is None else self.cached_input_price


@dataclass(frozen=True)
class ModelPricing:
    short_context: PriceTier
    long_context: PriceTier | None = None
    long_context_input_threshold: int = LONG_CONTEXT_INPUT_THRESHOLD
    label: str = ""

    def tier_for_request(self, request_input_tokens: int) -> PriceTier:
        if self.long_context and request_input_tokens >= self.long_context_input_threshold:
            return self.long_context
        return self.short_context


DEFAULT_MODEL_PRICING = ModelPricing(
    short_context=PriceTier(5.0, 0.5, 30.0),
    label="gpt-5.5",
)


TOKEN_PRICE_TABLE = (
    (
        ("gpt-5.5-pro",),
        ModelPricing(
            short_context=PriceTier(30.0, None, 180.0),
            long_context=PriceTier(60.0, None, 270.0),
            label="gpt-5.5-pro",
        ),
    ),
    (
        ("gpt-5.5",),
        ModelPricing(
            short_context=PriceTier(5.0, 0.5, 30.0),
            long_context=PriceTier(10.0, 1.0, 45.0),
            label="gpt-5.5",
        ),
    ),
    (
        ("gpt-5.4-pro",),
        ModelPricing(
            short_context=PriceTier(30.0, None, 180.0),
            long_context=PriceTier(60.0, None, 270.0),
            label="gpt-5.4-pro",
        ),
    ),
    (
        ("gpt-5.4",),
        ModelPricing(
            short_context=PriceTier(2.5, 0.25, 15.0),
            long_context=PriceTier(5.0, 0.5, 22.5),
            label="gpt-5.4",
        ),
    ),
    (
        ("gpt-5.4-mini",),
        ModelPricing(
            short_context=PriceTier(0.75, 0.075, 4.5),
            label="gpt-5.4-mini",
        ),
    ),
    (
        ("gpt-5.4-nano",),
        ModelPricing(
            short_context=PriceTier(0.2, 0.02, 1.25),
            label="gpt-5.4-nano",
        ),
    ),
    (
        ("gpt-5.2-pro",),
        ModelPricing(
            short_context=PriceTier(21.0, None, 168.0),
            label="gpt-5.2-pro",
        ),
    ),
    (
        ("gpt-5.3-codex", "gpt-5.2-codex", "gpt-5.3-chat", "gpt-5.2",),
        ModelPricing(
            short_context=PriceTier(1.75, 0.175, 14.0),
            label="gpt-5.2-codex",
        ),
    ),
    (
        ("gpt-5.1",),
        ModelPricing(
            short_context=PriceTier(1.25, 0.125, 10.0),
            label="gpt-5.1",
        ),
    ),
    (
        ("gpt-5-codex", "gpt-5",),
        ModelPricing(
            short_context=PriceTier(1.25, 0.125, 10.0),
            label="gpt-5",
        ),
    ),
    (
        ("gpt-5-mini",),
        ModelPricing(
            short_context=PriceTier(0.25, 0.025, 2.0),
            label="gpt-5-mini",
        ),
    ),
    (
        ("gpt-5-nano",),
        ModelPricing(
            short_context=PriceTier(0.05, 0.005, 0.40),
            label="gpt-5-nano",
        ),
    ),
    (
        ("gpt-5-pro",),
        ModelPricing(
            short_context=PriceTier(15.0, None, 120.0),
            label="gpt-5-pro",
        ),
    ),
)

CACHE_VERSION = 1
ENV_APP_SERVER_TIMEOUT_SECONDS = "CODEXUSAGE_APP_SERVER_TIMEOUT_SECONDS"
ENV_CODEX_HOME = "CODEXUSAGE_CODEX_HOME"
ENV_TASK_WINDOW_DAYS = "CODEXUSAGE_TASK_WINDOW_DAYS"

MESSAGE_CODEX_NOT_FOUND = "未找到 codex 可执行文件"
MESSAGE_APP_SERVER_START_FAILED = "app-server 启动失败"
MESSAGE_APP_SERVER_TIMED_OUT = "app-server 响应超时"
MESSAGE_STATE_DB_NOT_FOUND = "未找到 Codex state_5.sqlite"
MESSAGE_SQLITE_QUERY_FAILED = "SQLite 查询失败"
MESSAGE_SESSION_LOGS_NOT_FOUND = "未找到 Codex session 日志"
MESSAGE_TOKEN_EVENTS_NOT_FOUND = "未找到 Codex token_count 事件"
MESSAGE_TASK_BOARD_SQLITE_FAILED = "任务看板 SQLite 查询失败"
MESSAGE_TASK_BOARD_SOURCE_MISSING = "任务看板未找到 SQLite 数据源"

APP_SERVER_TIMEOUT_SECONDS = float(os.environ.get(ENV_APP_SERVER_TIMEOUT_SECONDS, "5"))


def new_rollout_cache() -> dict[str, Any]:
    return {"version": CACHE_VERSION, "entries": {}}


@dataclass
class TokenBreakdown:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0

    @property
    def billable_cached_input_tokens(self) -> int:
        return min(max(self.cached_input_tokens, 0), max(self.input_tokens, 0))

    @property
    def uncached_input_tokens(self) -> int:
        return max(0, self.input_tokens - self.billable_cached_input_tokens)

    @property
    def visible_total_tokens(self) -> int:
        return max(self.total_tokens, self.input_tokens + self.output_tokens)

    def add(self, other: "TokenBreakdown") -> None:
        self.input_tokens += other.input_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.output_tokens += other.output_tokens
        self.reasoning_output_tokens += other.reasoning_output_tokens
        self.total_tokens += other.total_tokens

    def delta_from(self, previous: "TokenBreakdown") -> "TokenBreakdown":
        delta = TokenBreakdown(
            self.input_tokens - previous.input_tokens,
            self.cached_input_tokens - previous.cached_input_tokens,
            self.output_tokens - previous.output_tokens,
            self.reasoning_output_tokens - previous.reasoning_output_tokens,
            self.total_tokens - previous.total_tokens,
        )
        if delta.has_negative_value:
            return self
        return delta

    @property
    def has_negative_value(self) -> bool:
        return any(
            value < 0
            for value in (
                self.input_tokens,
                self.cached_input_tokens,
                self.output_tokens,
                self.reasoning_output_tokens,
                self.total_tokens,
            )
        )

    @property
    def is_zero(self) -> bool:
        return not any(
            (
                self.input_tokens,
                self.cached_input_tokens,
                self.output_tokens,
                self.reasoning_output_tokens,
                self.total_tokens,
            )
        )


@dataclass
class PricedUsage:
    tokens: TokenBreakdown
    estimated_cost_usd: float = 0.0

    def add(self, tokens: TokenBreakdown, cost_usd: float) -> None:
        self.tokens.add(tokens)
        self.estimated_cost_usd += cost_usd


@dataclass(frozen=True)
class RolloutUsageDelta:
    timestamp: datetime
    tokens: TokenBreakdown
    request_input_tokens: int


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def iso_from_epoch(value: Any) -> str | None:
    timestamp = float(value or 0)
    if timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp).astimezone().isoformat()


def parse_iso_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def find_codex() -> str | None:
    candidates = [
        shutil.which("codex"),
        "/Applications/Codex.app/Contents/Resources/codex",
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
        "/usr/bin/codex",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def codex_home() -> Path:
    return Path(os.environ.get(ENV_CODEX_HOME, Path.home() / ".codex")).expanduser()


def state_db_path() -> Path | None:
    root = codex_home()
    for path in (root / "state_5.sqlite", root / "sqlite" / "state_5.sqlite"):
        if path.exists():
            return path
    return None


def rollout_cache_path() -> Path:
    return codex_home() / "cache" / f"codexusage-rollout-cache-v{CACHE_VERSION}.json"


def load_rollout_cache() -> dict[str, Any]:
    path = rollout_cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return new_rollout_cache()
    if payload.get("version") != CACHE_VERSION or not isinstance(payload.get("entries"), dict):
        return new_rollout_cache()
    return payload


def save_rollout_cache(cache: dict[str, Any]) -> None:
    path = rollout_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except OSError:
        return


def token_breakdown_to_object(tokens: TokenBreakdown) -> dict[str, int]:
    return {
        "inputTokens": tokens.input_tokens,
        "cachedInputTokens": tokens.cached_input_tokens,
        "outputTokens": tokens.output_tokens,
        "reasoningOutputTokens": tokens.reasoning_output_tokens,
        "totalTokens": tokens.total_tokens,
    }


def token_breakdown_from_object(payload: dict[str, Any]) -> TokenBreakdown:
    return TokenBreakdown(
        input_tokens=int(payload.get("inputTokens") or 0),
        cached_input_tokens=int(payload.get("cachedInputTokens") or 0),
        output_tokens=int(payload.get("outputTokens") or 0),
        reasoning_output_tokens=int(payload.get("reasoningOutputTokens") or 0),
        total_tokens=int(payload.get("totalTokens") or 0),
    )


def deserialize_cached_rollout(entry: dict[str, Any]) -> tuple[list[RolloutUsageDelta], int] | None:
    try:
        deltas = [
            RolloutUsageDelta(
                timestamp=parse_iso_timestamp(item["timestamp"]),
                tokens=token_breakdown_from_object(item["tokens"]),
                request_input_tokens=int(
                    item.get("requestInputTokens")
                    or (item.get("tokens") or {}).get("inputTokens")
                    or 0
                ),
            )
            for item in entry.get("deltas", [])
            if isinstance(item, dict) and isinstance(item.get("tokens"), dict)
        ]
        if any(item.timestamp is None for item in deltas):
            return None
        return [
            RolloutUsageDelta(item.timestamp, item.tokens, item.request_input_tokens)
            for item in deltas
            if item.timestamp is not None
        ], int(entry.get("tokenEventCount") or 0)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def cached_rollout_usage(
    path: Path,
    cache_entries: dict[str, Any],
) -> tuple[list[RolloutUsageDelta], int, bool]:
    key = str(path)
    try:
        stat = path.stat()
    except OSError:
        return [], 0, False

    cached = cache_entries.get(key)
    if (
        isinstance(cached, dict)
        and cached.get("fileSize") == stat.st_size
        and cached.get("modifiedNs") == stat.st_mtime_ns
    ):
        restored = deserialize_cached_rollout(cached)
        if restored is not None:
            deltas, events = restored
            return deltas, events, False

    deltas, events = parse_rollout_usage(path)
    cache_entries[key] = {
        "fileSize": stat.st_size,
        "modifiedNs": stat.st_mtime_ns,
        "tokenEventCount": events,
        "deltas": [
            {
                "timestamp": delta.timestamp.isoformat(),
                "tokens": token_breakdown_to_object(delta.tokens),
                "requestInputTokens": delta.request_input_tokens,
            }
            for delta in deltas
        ],
    }
    return deltas, events, True


def read_app_server(messages: list[str]) -> dict[str, Any]:
    codex = find_codex()
    if not codex:
        messages.append(MESSAGE_CODEX_NOT_FOUND)
        return {}

    try:
        process = subprocess.Popen(
            [codex, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except OSError:
        messages.append(MESSAGE_APP_SERVER_START_FAILED)
        return {}

    def send(payload: dict[str, Any]) -> None:
        if process.stdin:
            process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            process.stdin.flush()

    send(
        {
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "codexusage-noctalia", "title": "CodexUsage", "version": "0.2.0"},
                "capabilities": {"experimentalApi": True, "optOutNotificationMethods": []},
            },
        }
    )

    snapshot: dict[str, Any] = {}
    completed: set[int] = set()
    initialized = False
    deadline = time.monotonic() + max(1.0, APP_SERVER_TIMEOUT_SECONDS)

    try:
        while time.monotonic() < deadline and {2, 3, 4} - completed:
            assert process.stdout is not None
            ready, _, _ = select.select([process.stdout], [], [], 0.25)
            if not ready:
                continue
            line = process.stdout.readline()
            if not line:
                break
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            response_id = response.get("id")
            if response_id == 1 and not initialized:
                initialized = True
                send({"method": "initialized"})
                send({"id": 2, "method": "account/read", "params": {"refreshToken": False}})
                send({"id": 3, "method": "account/rateLimits/read"})
                send({"id": 4, "method": "account/usage/read"})
                continue
            if response_id in (2, 3, 4):
                if "error" in response:
                    message = response.get("error", {}).get("message", "未知错误")
                    messages.append(f"app-server {response_id}: {message}")
                else:
                    parse_app_server_result(snapshot, response_id, response.get("result") or {})
                completed.add(response_id)
    finally:
        if process.stdin:
            process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()

    if {2, 3, 4} - completed:
        messages.append(MESSAGE_APP_SERVER_TIMED_OUT)
    return snapshot


def parse_app_server_result(snapshot: dict[str, Any], response_id: int, result: dict[str, Any]) -> None:
    if response_id == 2:
        account = result.get("account") or {}
        if account.get("type"):
            snapshot["account"] = {
                "type": account.get("type"),
                "planType": account.get("planType"),
                "emailPresent": account.get("email") is not None,
            }
        return

    if response_id == 3:
        selected = (result.get("rateLimitsByLimitId") or {}).get("codex") or result.get("rateLimits") or {}
        if selected:
            snapshot["limitId"] = selected.get("limitId")
            snapshot["limitName"] = selected.get("limitName")
            primary = parse_rate_window(selected.get("primary"))
            secondary = parse_rate_window(selected.get("secondary"))
            if primary:
                snapshot["primary"] = primary
            if secondary:
                snapshot["secondary"] = secondary
            credits = selected.get("credits")
            reset = result.get("rateLimitResetCredits") or {}
            if credits or reset.get("availableCount") is not None:
                snapshot["credits"] = {
                    "hasCredits": bool((credits or {}).get("hasCredits", False)),
                    "unlimited": bool((credits or {}).get("unlimited", False)),
                    "balance": (credits or {}).get("balance"),
                    "resetCredits": reset.get("availableCount"),
                }
        return

    if response_id == 4:
        summary = result.get("summary") or {}
        if summary.get("lifetimeTokens") is not None:
            snapshot["cloudLifetimeTokens"] = int(summary.get("lifetimeTokens") or 0)


def parse_rate_window(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("usedPercent") is None:
        return None
    used = float(value.get("usedPercent") or 0)
    reset = value.get("resetsAt")
    return {
        "usedPercent": used,
        "remainingPercent": max(0.0, min(100.0, 100.0 - used)),
        "windowDurationMins": value.get("windowDurationMins"),
        "resetsAt": iso_from_epoch(reset) if reset is not None else None,
    }


def connect_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def read_local_usage(messages: list[str]) -> dict[str, Any] | None:
    db_path = state_db_path()
    if not db_path:
        messages.append(MESSAGE_STATE_DB_NOT_FOUND)
        return None

    try:
        connection = connect_db(db_path)
    except sqlite3.Error:
        messages.append(MESSAGE_SQLITE_QUERY_FAILED)
        return None

    now = datetime.now().astimezone()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_day_start = day_start - timedelta(days=6)

    try:
        totals = connection.execute(
            """
            SELECT
              COALESCE(SUM(tokens_used), 0) AS lifetimeTokens,
              COALESCE(SUM(CASE WHEN updated_at >= ? THEN tokens_used ELSE 0 END), 0) AS todayTokens,
              COALESCE(SUM(CASE WHEN updated_at >= ? THEN tokens_used ELSE 0 END), 0) AS sevenDayTokens,
              COUNT(*) AS threadCount,
              COALESCE(MAX(updated_at), 0) AS lastUpdatedAt
            FROM threads;
            """,
            (int(day_start.timestamp()), int(seven_day_start.timestamp())),
        ).fetchone()
        recent = connection.execute(
            """
            SELECT id, title, tokens_used AS tokens, updated_at AS updatedAt, model, cwd, archived
            FROM threads
            ORDER BY updated_at DESC
            LIMIT 5;
            """
        ).fetchall()
        daily = connection.execute(
            """
            SELECT date(updated_at, 'unixepoch', 'localtime') AS day,
                   COALESCE(SUM(tokens_used), 0) AS tokens
            FROM threads
            WHERE updated_at >= ?
            GROUP BY day
            ORDER BY day ASC;
            """,
            (int(seven_day_start.timestamp()),),
        ).fetchall()
    except sqlite3.Error:
        connection.close()
        messages.append(MESSAGE_SQLITE_QUERY_FAILED)
        return None

    tokens_by_day = {row["day"]: int(row["tokens"] or 0) for row in daily}
    daily_buckets = []
    for offset in range(7):
        date = day_start + timedelta(days=offset - 6)
        key = date.strftime("%Y-%m-%d")
        daily_buckets.append(
            {
                "day": key,
                "label": "今天" if offset == 6 else f"{date.month}/{date.day}",
                "tokens": tokens_by_day.get(key, 0),
            }
        )

    detailed = read_detailed_usage(connection, day_start, seven_day_start, messages)
    connection.close()

    local: dict[str, Any] = {
        "todayTokens": int(totals["todayTokens"] or 0),
        "sevenDayTokens": int(totals["sevenDayTokens"] or 0),
        "lifetimeTokens": int(totals["lifetimeTokens"] or 0),
        "threadCount": int(totals["threadCount"] or 0),
        "lastUpdatedAt": iso_from_epoch(totals["lastUpdatedAt"]),
        "dailyBuckets": daily_buckets,
        "recentThreads": [
            {
                "id": row["id"],
                "title": row["title"] or "Untitled",
                "tokens": int(row["tokens"] or 0),
                "updatedAt": iso_from_epoch(row["updatedAt"]),
                "model": row["model"],
                "cwd": row["cwd"] or "",
                "archived": bool(row["archived"]),
            }
            for row in recent
        ],
    }
    if detailed:
        local["detailedUsage"] = detailed
        local["valueProjection"] = detailed["valueProjection"]
    else:
        local["valueProjection"] = monthly_value_projection_object(None)
    return local


def read_detailed_usage(
    connection: sqlite3.Connection,
    day_start: datetime,
    seven_day_start: datetime,
    messages: list[str],
) -> dict[str, Any] | None:
    try:
        rows = connection.execute(
            """
            SELECT rollout_path AS rolloutPath, model
            FROM threads
            WHERE rollout_path IS NOT NULL
              AND rollout_path <> ''
              AND tokens_used > 0
            ORDER BY updated_at ASC;
            """
        ).fetchall()
    except sqlite3.Error:
        return None

    seen: set[str] = set()
    sources = []
    for row in rows:
        path = row["rolloutPath"]
        if path and path not in seen:
            seen.add(path)
            sources.append((Path(path).expanduser(), row["model"]))

    if not sources:
        messages.append(MESSAGE_SESSION_LOGS_NOT_FOUND)
        return None

    now = datetime.now().astimezone()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = {
        "today": PricedUsage(TokenBreakdown()),
        "sevenDay": PricedUsage(TokenBreakdown()),
        "month": PricedUsage(TokenBreakdown()),
        "lifetime": PricedUsage(TokenBreakdown()),
    }
    cache = load_rollout_cache()
    cache_entries = cache["entries"]
    cache_dirty = False
    active_cache_keys: set[str] = set()
    parsed_file_count = 0
    token_event_count = 0

    for path, model in sources:
        if not path.exists():
            continue
        active_cache_keys.add(str(path))
        deltas, events, changed = cached_rollout_usage(path, cache_entries)
        cache_dirty = cache_dirty or changed
        if events:
            parsed_file_count += 1
            token_event_count += events
        pricing = model_token_price(model)
        for delta in deltas:
            cost = estimated_cost_usd(delta.tokens, pricing, delta.request_input_tokens)
            usage["lifetime"].add(delta.tokens, cost)
            if delta.timestamp >= month_start:
                usage["month"].add(delta.tokens, cost)
            if delta.timestamp >= seven_day_start:
                usage["sevenDay"].add(delta.tokens, cost)
            if delta.timestamp >= day_start:
                usage["today"].add(delta.tokens, cost)

    stale_keys = [key for key in cache_entries.keys() if key not in active_cache_keys]
    for key in stale_keys:
        del cache_entries[key]
    if cache_dirty or stale_keys:
        save_rollout_cache(cache)

    if parsed_file_count == 0 or token_event_count == 0:
        messages.append(MESSAGE_TOKEN_EVENTS_NOT_FOUND)
        return None

    return {
        "today": priced_usage_object(usage["today"]),
        "sevenDay": priced_usage_object(usage["sevenDay"]),
        "month": priced_usage_object(usage["month"]),
        "lifetime": priced_usage_object(usage["lifetime"]),
        "valueProjection": monthly_value_projection_object(usage["month"], now),
        "parsedFileCount": parsed_file_count,
        "tokenEventCount": token_event_count,
    }


def parse_rollout_usage(path: Path) -> tuple[list[RolloutUsageDelta], int]:
    previous = TokenBreakdown()
    deltas: list[RolloutUsageDelta] = []
    events = 0
    with path.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            if '"type":"token_count"' not in line and '"type": "token_count"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ((event.get("payload") or {}).get("type")) != "token_count":
                continue
            date = parse_iso_timestamp(event.get("timestamp") or "")
            info = (event.get("payload") or {}).get("info") or {}
            usage = info.get("total_token_usage") or {}
            last_usage = info.get("last_token_usage") or {}
            if not date or not usage:
                continue
            current = TokenBreakdown(
                input_tokens=int(usage.get("input_tokens") or 0),
                cached_input_tokens=int(usage.get("cached_input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                reasoning_output_tokens=int(usage.get("reasoning_output_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
            )
            delta = current.delta_from(previous)
            previous = current
            events += 1
            if not delta.is_zero:
                deltas.append(
                    RolloutUsageDelta(
                        timestamp=date,
                        tokens=delta,
                        request_input_tokens=int(last_usage.get("input_tokens") or usage.get("input_tokens") or 0),
                    )
                )
    return deltas, events


def model_token_price(model: str | None) -> ModelPricing:
    normalized = (model or "").lower()
    for aliases, pricing in TOKEN_PRICE_TABLE:
        if any(alias in normalized for alias in aliases):
            return pricing
    return DEFAULT_MODEL_PRICING


def estimated_cost_usd(tokens: TokenBreakdown, pricing: ModelPricing, request_input_tokens: int | None = None) -> float:
    tier = pricing.tier_for_request(int(request_input_tokens or 0))
    return (
        tokens.uncached_input_tokens / 1_000_000 * tier.input_price
        + tokens.billable_cached_input_tokens / 1_000_000 * tier.effective_cached_input_price
        + max(tokens.output_tokens, 0) / 1_000_000 * tier.output_price
    )


def next_month_start(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return value.replace(month=value.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_value_projection_object(month_usage: PricedUsage | None, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now().astimezone()
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = next_month_start(current_time)
    month_seconds = max((month_end - month_start).total_seconds(), 1.0)
    elapsed_seconds = max((current_time - month_start).total_seconds(), 1.0)
    elapsed_fraction = min(max(elapsed_seconds / month_seconds, 0.0), 1.0)

    current_value = float((month_usage and month_usage.estimated_cost_usd) or 0.0)
    projected_value = current_value / elapsed_fraction if current_value > 0 and elapsed_fraction > 0 else 0.0
    return {
        "currentUSD": current_value,
        "projectedUSD": projected_value,
        "elapsedFraction": elapsed_fraction,
        "monthStart": month_start.isoformat(),
        "monthEnd": month_end.isoformat(),
        "source": "monthlyRunRate" if projected_value > 0 else "none",
    }


def priced_usage_object(usage: PricedUsage) -> dict[str, Any]:
    tokens = usage.tokens
    return {
        "estimatedCostUSD": usage.estimated_cost_usd,
        "tokens": {
            "inputTokens": tokens.input_tokens,
            "cachedInputTokens": tokens.billable_cached_input_tokens,
            "uncachedInputTokens": tokens.uncached_input_tokens,
            "outputTokens": tokens.output_tokens,
            "reasoningOutputTokens": tokens.reasoning_output_tokens,
            "totalTokens": tokens.visible_total_tokens,
        },
    }


def read_task_board(messages: list[str]) -> dict[str, Any] | None:
    db_path = state_db_path()
    active_items: list[dict[str, Any]] = []
    pending_items: list[dict[str, Any]] = []
    done_items: list[dict[str, Any]] = []

    now = datetime.now().astimezone()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    active_cutoff = now - timedelta(hours=2)

    window_days = max(1, int(os.environ.get(ENV_TASK_WINDOW_DAYS, "1")))
    window_start = day_start - timedelta(days=window_days - 1)

    if db_path:
        try:
            connection = connect_db(db_path)
            today_rows = connection.execute(
                """
                SELECT id, title, preview, cwd, tokens_used AS tokens, updated_at AS updatedAt,
                       recency_at AS recencyAt, model
                FROM threads
                WHERE archived = 0
                  AND (
                    updated_at >= ?
                    OR recency_at >= ?
                    OR created_at >= ?
                  )
                ORDER BY recency_at DESC, updated_at DESC
                LIMIT 24;
                """,
                (int(window_start.timestamp()), int(window_start.timestamp()), int(window_start.timestamp())),
            ).fetchall()
            done_rows = connection.execute(
                """
                SELECT id, title, preview, cwd, tokens_used AS tokens,
                       COALESCE(archived_at, updated_at) AS updatedAt, model
                FROM threads
                WHERE archived = 1
                  AND COALESCE(archived_at, updated_at) >= ?
                ORDER BY COALESCE(archived_at, updated_at) DESC
                LIMIT 12;
                """,
                (int(window_start.timestamp()),),
            ).fetchall()
            connection.close()
        except sqlite3.Error:
            today_rows = []
            done_rows = []
            messages.append(MESSAGE_TASK_BOARD_SQLITE_FAILED)

        for row in today_rows:
            iso = iso_from_epoch(row["recencyAt"] or row["updatedAt"])
            updated = datetime.fromisoformat(iso) if iso else datetime.min.astimezone()
            kind = "active" if updated >= active_cutoff else "pending"
            item = make_thread_task_item(row, kind)
            if kind == "active":
                active_items.append(item)
            else:
                pending_items.append(item)
        done_items = [make_thread_task_item(row, "done") for row in done_rows]
    else:
        messages.append(MESSAGE_TASK_BOARD_SOURCE_MISSING)

    scheduled_items = read_automation_tasks()
    columns = [
        make_task_column("active", "进行中", active_items),
        make_task_column("pending", "待处理", pending_items),
        make_task_column("scheduled", "定时", scheduled_items),
        make_task_column("done", "完成", done_items),
    ]
    return {
        "refreshedAt": iso_now(),
        "totalCount": sum(column["count"] for column in columns),
        "columns": columns,
    }


def make_task_column(kind: str, title: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": kind, "title": title, "count": len(items), "items": items[:3]}


def make_thread_task_item(row: sqlite3.Row, kind: str) -> dict[str, Any]:
    raw_id = row["id"] or f"thread-{time.time_ns()}"
    tokens = int(row["tokens"] or 0)
    code = "COD-" + raw_id.replace("-", "")[-4:].upper()
    title = normalized_title(row["title"], row["preview"] if "preview" in row.keys() else None)
    if kind == "active":
        chip = "High" if tokens >= 5_000_000 else "Active"
    elif kind == "pending":
        chip = "Medium" if tokens >= 2_000_000 else "Idle"
    elif kind == "scheduled":
        chip = "Cron"
    else:
        chip = "Done"
    detail = " · ".join(part for part in (short_workspace_name(row["cwd"] or ""), format_tokens(tokens)) if part)
    return {
        "id": raw_id + kind,
        "code": code,
        "title": title,
        "detail": detail,
        "chip": chip,
        "updatedAt": iso_from_epoch(row["updatedAt"]),
        "tokens": tokens,
        "kind": kind,
    }


def read_automation_tasks() -> list[dict[str, Any]]:
    root = codex_home() / "automations"
    if not root.exists():
        return []
    items = []
    for path in root.rglob("automation.toml"):
        fields = parse_simple_toml(path.read_text(encoding="utf-8", errors="ignore"))
        if (fields.get("status") or "").upper() != "ACTIVE":
            continue
        automation_id = fields.get("id") or path.parent.name
        kind = fields.get("kind") or "cron"
        schedule = schedule_summary(fields.get("rrule"))
        detail = " · ".join(part for part in (kind.upper(), schedule) if part)
        items.append(
            {
                "id": "automation-" + automation_id,
                "code": "AUTO-" + automation_id[:4].upper(),
                "title": fields.get("name") or automation_id,
                "detail": detail,
                "chip": "Wake" if kind == "heartbeat" else "Cron",
                "updatedAt": iso_from_epoch(fields.get("updated_at")),
                "tokens": None,
                "kind": "scheduled",
            }
        )
    return sorted(items, key=lambda item: item["title"])


def parse_simple_toml(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace("\\n", "\n").replace('\\"', '"')
        fields[key.strip()] = value
    return fields


def normalized_title(title: str | None, fallback: str | None) -> str:
    raw = next((value.strip() for value in (title, fallback) if value and value.strip()), "Untitled")
    single_line = " ".join(raw.split())
    return single_line if len(single_line) <= 48 else single_line[:45] + "..."


def short_workspace_name(path: str) -> str:
    return Path(path).name if path else ""


def format_tokens(value: int | None) -> str:
    if value is None:
        return "--"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def schedule_summary(rrule: str | None) -> str:
    if not rrule:
        return ""
    time_text = ""
    marker = "T"
    if marker in rrule:
        index = rrule.find(marker)
        value = rrule[index + 1 : index + 5]
        if len(value) == 4 and value.isdigit():
            time_text = value[:2] + ":" + value[2:]
    if "FREQ=DAILY" in rrule:
        return f"每天 {time_text}".strip()
    if "FREQ=WEEKLY" in rrule:
        return f"每周 {time_text}".strip()
    if "FREQ=HOURLY" in rrule:
        return "每小时"
    return time_text


def build_snapshot() -> dict[str, Any]:
    messages: list[str] = []
    app_server = read_app_server(messages)
    local = read_local_usage(messages)
    task_board = read_task_board(messages)

    snapshot: dict[str, Any] = {"refreshedAt": iso_now(), "messages": messages}
    snapshot.update(app_server)
    if local:
        snapshot["local"] = local
    if task_board:
        snapshot["taskBoard"] = task_board
    return snapshot


def main() -> int:
    json.dump(build_snapshot(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
