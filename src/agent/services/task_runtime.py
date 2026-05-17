"""Async task runtime backed fully by ORM models."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform as platform_mod
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent.credentials_store import read_credential_values
from agent.db.database import ensure_default_schema, get_default_session_factory
from agent.db.models import ScheduledTask, TaskLog

log = logging.getLogger("task_runtime")

_ENV_VAR_CREDENTIAL_TYPE = "env_var"
_DEFAULT_TIMEOUT_S = 300
_DEFAULT_MAX_CONCURRENT = 8


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_dt().isoformat()


def _user_timezone():
    return datetime.now().astimezone().tzinfo or timezone.utc


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=_user_timezone())
    return value.astimezone(timezone.utc)


def _to_user_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_user_timezone())


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default
    return value


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value)
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return _to_utc(datetime.fromisoformat(s))
    except ValueError:
        return None


def _dt_to_iso(value: datetime | None) -> str | None:
    return _to_user_timezone(value).isoformat() if value is not None else None


def _normalize_env_refs(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    refs: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        refs.append({"key": key})
    return refs


def _task_row_to_dict(row: ScheduledTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "cron_expression": row.cron_expression,
        "execution_mode": row.execution_mode,
        "status": row.status,
        "payload": row.payload,
        "env_var_refs": _normalize_env_refs(_json_loads(row.env_var_refs_json, [])),
        "created_at": _dt_to_iso(row.created_at) or "",
        "started_at": _dt_to_iso(row.started_at),
        "updated_at": _dt_to_iso(row.updated_at) or "",
        "last_run_id": row.last_run_id,
        "last_run_at": _dt_to_iso(row.last_run_at),
        "last_run_status": row.last_run_status,
        "last_run_trigger": row.last_run_trigger,
    }


def _log_row_to_dict(row: TaskLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "run_id": row.run_id,
        "step_index": row.seq,
        "log_type": row.log_type,
        "duration_ms": row.duration_ms,
        "status": row.entry_status,
        "timestamp": _dt_to_iso(row.timestamp) or "",
        "content": row.content,
        "metadata": _json_loads(row.metadata_json, {}),
        "input_params": _json_loads(row.input_params_json, None),
        "output": _json_loads(row.output_json, None),
        "tool_name": row.tool_name,
    }


def _run_dict_from_rows(rows: list[TaskLog]) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot build run dict from empty row list")
    ordered = sorted(rows, key=lambda row: row.seq)
    latest = max(rows, key=lambda row: row.seq)
    return {
        "id": latest.run_id,
        "task_id": latest.task_id,
        "status": latest.run_status,
        "trigger": latest.run_trigger,
        "override_prompt": latest.run_override_prompt,
        "started_at": _dt_to_iso(latest.run_started_at) or "",
        "finished_at": _dt_to_iso(latest.run_finished_at),
        "message": latest.run_error_message,
        "logs": [_log_row_to_dict(row) for row in ordered],
    }


def _entry_level(log_type: str) -> str:
    if log_type == "script_stdout":
        return "stdout"
    if log_type == "script_stderr":
        return "stderr"
    return "info"


def _status_to_last_run(status: str) -> str | None:
    if status == "succeeded":
        return "success"
    if status in {"failed", "cancelled"}:
        return status
    return None


class CronMatcher:
    __slots__ = ("_fields",)

    def __init__(self, expression: str):
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression (need 5 fields): {expression!r}")
        ranges = [
            (0, 59),
            (0, 23),
            (1, 31),
            (1, 12),
            (0, 6),
        ]
        self._fields: list[set[int]] = [
            self._parse_field(part, lo, hi) for part, (lo, hi) in zip(parts, ranges)
        ]

    @staticmethod
    def _parse_field(field: str, lo: int, hi: int) -> set[int]:
        result: set[int] = set()
        for token in field.split(","):
            if "/" in token:
                range_part, step_s = token.split("/", 1)
                step = int(step_s)
            else:
                range_part, step = token, 1

            if range_part == "*":
                start, end = lo, hi
            elif "-" in range_part:
                a, b = range_part.split("-", 1)
                start, end = int(a), int(b)
            else:
                start = end = int(range_part)

            result.update(range(start, end + 1, step))
        return result

    def matches(self, dt_value: datetime) -> bool:
        dow = (dt_value.weekday() + 1) % 7
        return (
            dt_value.minute in self._fields[0]
            and dt_value.hour in self._fields[1]
            and dt_value.day in self._fields[2]
            and dt_value.month in self._fields[3]
            and dow in self._fields[4]
        )


@dataclass
class _RunHandle:
    run_id: str
    task_id: str
    trigger: str
    override_prompt: str | None
    started_at: datetime
    started_perf: float = field(default_factory=time.perf_counter)
    next_seq: int = 2
    process: asyncio.subprocess.Process | None = None
    cancel_requested: bool = False
    forced_terminal_status: str | None = None
    forced_error_message: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    done: asyncio.Event = field(default_factory=asyncio.Event)


class TaskRuntimeService:
    def __init__(
        self,
        session_factory: async_sessionmaker | None = None,
        *,
        default_timeout_s: int = _DEFAULT_TIMEOUT_S,
        max_concurrent: int = _DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self._session_factory = session_factory or get_default_session_factory()
        self._default_timeout_s = default_timeout_s
        self._max_concurrent = max_concurrent
        self._run_handles: dict[str, _RunHandle] = {}
        self._handles_lock = asyncio.Lock()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._scheduler_stop = asyncio.Event()
        self._last_fired_minute: dict[str, datetime] = {}
        self._concurrency_sem = asyncio.Semaphore(max_concurrent)

    async def ensure_schema(self) -> None:
        await ensure_default_schema()

    async def start_scheduler(self, interval_s: float = 60.0) -> None:
        await self.ensure_schema()
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return
        self._scheduler_stop = asyncio.Event()
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(interval_s),
            name="task-scheduler",
        )

    async def stop_scheduler(self) -> None:
        self._scheduler_stop.set()
        if self._scheduler_task is not None:
            await self._scheduler_task
        self._scheduler_task = None

    async def aclose(self) -> None:
        await self.stop_scheduler()
        handles = await self._all_handles()
        for handle in handles:
            await self._request_terminal_state(handle, "cancelled", "Cancelled during shutdown.")

    async def create_task(
        self,
        *,
        name: str,
        description: str,
        cron_expression: str | None,
        execution_mode: str,
        payload: str,
        env_var_refs: list[dict[str, str]],
        started_at: str | None,
    ) -> dict[str, Any]:
        await self.ensure_schema()
        now = _now_dt()
        row = ScheduledTask(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            cron_expression=cron_expression,
            execution_mode=execution_mode,
            status="enabled",
            payload=payload,
            env_var_refs_json=_json_dumps(env_var_refs),
            created_at=now,
            started_at=_parse_dt(started_at),
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _task_row_to_dict(row)

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        await self.ensure_schema()
        async with self._session_factory() as session:
            stmt = select(ScheduledTask).order_by(ScheduledTask.created_at.desc())
            if status is not None:
                stmt = stmt.where(ScheduledTask.status == status)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        total = len(rows)
        start = (page - 1) * page_size
        return [_task_row_to_dict(row) for row in rows[start : start + page_size]], total

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(ScheduledTask, task_id)
            return _task_row_to_dict(row) if row is not None else None

    async def update_task(self, task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(ScheduledTask, task_id)
            if row is None:
                return None

            if "name" in updates:
                row.name = updates["name"]
            if "description" in updates:
                row.description = updates["description"]
            if "cron_expression" in updates:
                row.cron_expression = updates["cron_expression"]
            if "execution_mode" in updates:
                row.execution_mode = updates["execution_mode"]
            if "payload" in updates:
                row.payload = updates["payload"]
            if "env_var_refs" in updates:
                row.env_var_refs_json = _json_dumps(updates["env_var_refs"] or [])
            if "started_at" in updates:
                row.started_at = _parse_dt(updates["started_at"])
            row.updated_at = _now_dt()
            await session.commit()
            await session.refresh(row)
            return _task_row_to_dict(row)

    async def set_task_enabled(self, task_id: str, enabled: bool) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(ScheduledTask, task_id)
            if row is None:
                return None
            now = _now_dt()
            if enabled and row.started_at is None:
                row.started_at = now
            row.status = "enabled" if enabled else "disabled"
            row.updated_at = now
            await session.commit()
            await session.refresh(row)
            return _task_row_to_dict(row)

    async def delete_task(self, task_id: str) -> bool:
        await self.ensure_schema()
        handles = await self._handles_for_task(task_id)
        for handle in handles:
            await self._request_terminal_state(handle, "cancelled", "Cancelled by user.")

        async with self._session_factory() as session:
            row = await session.get(ScheduledTask, task_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def trigger_task(
        self,
        task_id: str,
        *,
        trigger: str,
        override_prompt: str | None = None,
        timeout_s: int | None = None,
    ) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(ScheduledTask, task_id)
            if row is None:
                return None
            task = _task_row_to_dict(row)
            now = _now_dt()
            if row.started_at is None:
                row.started_at = now
                task["started_at"] = _dt_to_iso(now)
            row.status = "running"
            row.updated_at = now
            row.last_run_at = now
            row.last_run_trigger = trigger
            run_id = str(uuid.uuid4())
            row.last_run_id = run_id
            await session.commit()
            await session.refresh(row)
            task = _task_row_to_dict(row)

        env, injected_keys = await self._build_env(task.get("env_var_refs") or [])
        handle = _RunHandle(
            run_id=run_id,
            task_id=task_id,
            trigger=trigger,
            override_prompt=override_prompt,
            started_at=now,
        )
        await self._insert_log(
            task_id=task_id,
            run_id=run_id,
            seq=1,
            log_type="script_start",
            entry_status="success",
            duration_ms=0,
            content=None,
            metadata={
                "platform": platform_mod.platform(),
                "python_version": sys.version.split()[0],
                "injected_env_keys": injected_keys,
            },
            run_status="running",
            run_trigger=trigger,
            run_override_prompt=override_prompt,
            run_started_at=now,
            run_finished_at=None,
            run_error_message=None,
        )

        if task.get("execution_mode") != "script" or not str(task.get("payload") or "").strip():
            message = "Nothing to execute: execution_mode is not 'script' or payload is empty."
            await self._append_terminal_log(
                task_id=task_id,
                run_id=run_id,
                status="failed",
                error_message=message,
                trigger=trigger,
                override_prompt=override_prompt,
                started_at=now,
                content=message,
            )
            await self._finalize_task_state(task_id, run_id, "failed", trigger, _now_dt())
            return await self.get_run(run_id)

        async with self._handles_lock:
            self._run_handles[run_id] = handle

        asyncio.create_task(
            self._run_script(
                handle,
                task,
                env,
                timeout_s or self._default_timeout_s,
            ),
            name=f"task-run-{run_id[:8]}",
        )
        return await self.get_run(run_id)

    async def list_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        await self.ensure_schema()
        async with self._session_factory() as session:
            stmt = (
                select(TaskLog)
                .where(TaskLog.task_id == task_id)
                .order_by(TaskLog.run_started_at.desc(), TaskLog.seq.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        grouped: dict[str, list[TaskLog]] = {}
        ordered_run_ids: list[str] = []
        for row in rows:
            if row.run_id not in grouped:
                grouped[row.run_id] = []
                ordered_run_ids.append(row.run_id)
            grouped[row.run_id].append(row)
        return [_run_dict_from_rows(grouped[run_id]) for run_id in ordered_run_ids]

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        await self.ensure_schema()
        async with self._session_factory() as session:
            stmt = select(TaskLog).where(TaskLog.run_id == run_id).order_by(TaskLog.seq.asc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
        if not rows:
            return None
        return _run_dict_from_rows(rows)

    async def get_run_logs(self, run_id: str) -> list[dict[str, Any]]:
        run = await self.get_run(run_id)
        if run is None:
            return []
        return run.get("logs") or []

    async def cancel_run(self, run_id: str) -> dict[str, Any] | None:
        run = await self.get_run(run_id)
        if run is None:
            return None
        if run["status"] in {"succeeded", "failed", "cancelled"}:
            return run

        handle = await self._get_handle(run_id)
        if handle is not None:
            await self._request_terminal_state(handle, "cancelled", "Cancelled by user.")
        else:
            await self._append_terminal_log(
                task_id=run["task_id"],
                run_id=run_id,
                status="cancelled",
                error_message="Cancelled by user.",
                trigger=run["trigger"],
                override_prompt=run.get("override_prompt"),
                started_at=_parse_dt(run["started_at"]) or _now_dt(),
                content="Cancelled by user.",
            )
            await self._finalize_task_state(
                run["task_id"],
                run_id,
                "cancelled",
                run["trigger"],
                _now_dt(),
            )
        return await self.get_run(run_id)

    async def complete_run(self, run_id: str, status: str, error_message: str | None) -> dict[str, Any] | None:
        run = await self.get_run(run_id)
        if run is None:
            return None
        if run["status"] in {"succeeded", "failed", "cancelled"}:
            return run

        target_status = "succeeded" if status == "success" else "failed"
        handle = await self._get_handle(run_id)
        if handle is not None:
            await self._request_terminal_state(handle, target_status, error_message)
        else:
            await self._append_terminal_log(
                task_id=run["task_id"],
                run_id=run_id,
                status=target_status,
                error_message=error_message,
                trigger=run["trigger"],
                override_prompt=run.get("override_prompt"),
                started_at=_parse_dt(run["started_at"]) or _now_dt(),
                content=error_message,
            )
            await self._finalize_task_state(
                run["task_id"],
                run_id,
                target_status,
                run["trigger"],
                _now_dt(),
            )
        return await self.get_run(run_id)

    async def _scheduler_loop(self, interval_s: float) -> None:
        while not self._scheduler_stop.is_set():
            try:
                await self._dispatch_due_tasks()
            except Exception:
                log.exception("Error in task scheduler loop")
            try:
                await asyncio.wait_for(self._scheduler_stop.wait(), timeout=interval_s)
            except asyncio.TimeoutError:
                pass

    async def _dispatch_due_tasks(self) -> None:
        now = _now_dt()
        minute_start = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
        local_wall = _to_user_timezone(minute_start)
        async with self._session_factory() as session:
            stmt = select(ScheduledTask).where(
                ScheduledTask.status == "enabled",
                ScheduledTask.execution_mode == "script",
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()

        for task in tasks:
            expr = (task.cron_expression or "").strip()
            if not expr:
                continue
            try:
                matcher = CronMatcher(expr)
            except ValueError:
                continue
            if self._last_fired_minute.get(task.id) == minute_start:
                continue
            if not matcher.matches(local_wall):
                continue
            await self.trigger_task(task.id, trigger="cron")
            self._last_fired_minute[task.id] = minute_start

    async def _build_env(self, task_env_refs: list[dict[str, str]]) -> tuple[dict[str, str], list[str]]:
        global_vars = await read_credential_values(_ENV_VAR_CREDENTIAL_TYPE)
        env = dict(os.environ)
        env.update(global_vars)
        injected_keys = set(global_vars.keys())
        for ref in task_env_refs:
            key = str(ref.get("key") or "").strip()
            if not key:
                continue
            injected_keys.add(key)
            if key in global_vars:
                env[key] = global_vars[key]
        return env, sorted(injected_keys)

    async def _run_script(
        self,
        handle: _RunHandle,
        task: dict[str, Any],
        env: dict[str, str],
        timeout_s: int,
    ) -> None:
        script_path: str | None = None
        try:
            async with self._concurrency_sem:
                if handle.forced_terminal_status is not None:
                    await self._append_terminal_log(
                        task_id=handle.task_id,
                        run_id=handle.run_id,
                        status=handle.forced_terminal_status,
                        error_message=handle.forced_error_message,
                        trigger=handle.trigger,
                        override_prompt=handle.override_prompt,
                        started_at=handle.started_at,
                        content=handle.forced_error_message,
                    )
                    await self._finalize_task_state(
                        handle.task_id,
                        handle.run_id,
                        handle.forced_terminal_status,
                        handle.trigger,
                        _now_dt(),
                    )
                    await self._drop_handle(handle.run_id)
                    handle.done.set()
                    return
                script_path = await self._write_temp_script(task["id"], task.get("payload") or "")
                process = await self._spawn_process(script_path, env)
                handle.process = process
                stdout_task = asyncio.create_task(self._pump_stream(process.stdout, handle, "script_stdout"))
                stderr_task = asyncio.create_task(self._pump_stream(process.stderr, handle, "script_stderr"))

                timed_out = False
                try:
                    returncode = await asyncio.wait_for(process.wait(), timeout=timeout_s)
                except asyncio.TimeoutError:
                    timed_out = True
                    returncode = None
                    if process.returncode is None:
                        process.kill()
                        await process.wait()

                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
                await self._finish_run(handle, script_path, returncode, timed_out=timed_out, timeout_s=timeout_s)
        except Exception as exc:
            log.exception("Run %s failed with exception", handle.run_id)
            await self._append_terminal_log(
                task_id=handle.task_id,
                run_id=handle.run_id,
                status="failed",
                error_message=str(exc),
                trigger=handle.trigger,
                override_prompt=handle.override_prompt,
                started_at=handle.started_at,
                content=f"Executor error: {exc}",
            )
            await self._finalize_task_state(handle.task_id, handle.run_id, "failed", handle.trigger, _now_dt())
            await self._drop_handle(handle.run_id)
            handle.done.set()
            if script_path is not None:
                await asyncio.to_thread(self._unlink_path, script_path)

    async def _finish_run(
        self,
        handle: _RunHandle,
        script_path: str,
        returncode: int | None,
        *,
        timed_out: bool,
        timeout_s: int,
    ) -> None:
        if handle.forced_terminal_status is not None:
            final_status = handle.forced_terminal_status
            error_message = handle.forced_error_message
            content = handle.forced_error_message
        elif handle.cancel_requested:
            final_status = "cancelled"
            error_message = "Cancelled by user."
            content = error_message
        elif timed_out:
            final_status = "failed"
            error_message = f"Execution timed out after {timeout_s}s"
            content = error_message
        elif returncode == 0:
            final_status = "succeeded"
            error_message = None
            content = None
        else:
            final_status = "failed"
            error_message = f"Process exited with code {returncode}"
            content = None

        await self._append_terminal_log(
            task_id=handle.task_id,
            run_id=handle.run_id,
            status=final_status,
            error_message=error_message,
            trigger=handle.trigger,
            override_prompt=handle.override_prompt,
            started_at=handle.started_at,
            content=content,
            exit_code=returncode,
            duration_ms=int((time.perf_counter() - handle.started_perf) * 1000),
        )
        await self._finalize_task_state(handle.task_id, handle.run_id, final_status, handle.trigger, _now_dt())
        await self._drop_handle(handle.run_id)
        handle.done.set()
        await asyncio.to_thread(self._unlink_path, script_path)

    async def _request_terminal_state(
        self,
        handle: _RunHandle,
        status: str,
        error_message: str | None,
    ) -> None:
        handle.forced_terminal_status = status
        handle.forced_error_message = error_message
        if status == "cancelled":
            handle.cancel_requested = True
        process = handle.process
        if process is not None and process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(handle.done.wait(), timeout=5)
        except asyncio.TimeoutError:
            if process is not None and process.returncode is None:
                process.kill()
                try:
                    await asyncio.wait_for(handle.done.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

    async def _pump_stream(
        self,
        stream: asyncio.StreamReader | None,
        handle: _RunHandle,
        log_type: str,
    ) -> None:
        if stream is None:
            return
        chunk_index = 0
        while True:
            line = await stream.readline()
            if not line:
                return
            content = line.decode("utf-8", errors="replace").rstrip("\r\n")
            seq = await self._reserve_seq(handle)
            await self._insert_log(
                task_id=handle.task_id,
                run_id=handle.run_id,
                seq=seq,
                log_type=log_type,
                entry_status="success",
                duration_ms=0,
                content=content,
                metadata={"chunk_index": chunk_index},
                run_status="running",
                run_trigger=handle.trigger,
                run_override_prompt=handle.override_prompt,
                run_started_at=handle.started_at,
                run_finished_at=None,
                run_error_message=None,
            )
            chunk_index += 1

    async def _reserve_seq(self, handle: _RunHandle) -> int:
        async with handle.lock:
            seq = handle.next_seq
            handle.next_seq += 1
            return seq

    async def _insert_log(
        self,
        *,
        task_id: str,
        run_id: str,
        seq: int,
        log_type: str,
        entry_status: str,
        duration_ms: int,
        content: str | None,
        metadata: dict[str, Any],
        run_status: str,
        run_trigger: str,
        run_override_prompt: str | None,
        run_started_at: datetime,
        run_finished_at: datetime | None,
        run_error_message: str | None,
        input_params: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        tool_name: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                TaskLog(
                    task_id=task_id,
                    run_id=run_id,
                    seq=seq,
                    level=_entry_level(log_type),
                    log_type=log_type,
                    entry_status=entry_status,
                    duration_ms=duration_ms,
                    content=content,
                    timestamp=_now_dt(),
                    metadata_json=_json_dumps(metadata),
                    input_params_json=_json_dumps(input_params) if input_params is not None else None,
                    output_json=_json_dumps(output) if output is not None else None,
                    tool_name=tool_name,
                    run_status=run_status,
                    run_trigger=run_trigger,
                    run_override_prompt=run_override_prompt,
                    run_started_at=run_started_at,
                    run_finished_at=run_finished_at,
                    run_error_message=run_error_message,
                )
            )
            await session.commit()

    async def _append_terminal_log(
        self,
        *,
        task_id: str,
        run_id: str,
        status: str,
        error_message: str | None,
        trigger: str,
        override_prompt: str | None,
        started_at: datetime,
        content: str | None,
        exit_code: int | None = None,
        duration_ms: int = 0,
    ) -> None:
        async with self._session_factory() as session:
            stmt = select(func.max(TaskLog.seq)).where(TaskLog.run_id == run_id)
            result = await session.execute(stmt)
            current_seq = result.scalar_one() or 0
        metadata: dict[str, Any] = {}
        if exit_code is not None:
            metadata["exit_code"] = exit_code
        await self._insert_log(
            task_id=task_id,
            run_id=run_id,
            seq=current_seq + 1,
            log_type="script_end",
            entry_status="success" if status == "succeeded" else "failed",
            duration_ms=duration_ms,
            content=content,
            metadata=metadata,
            run_status=status,
            run_trigger=trigger,
            run_override_prompt=override_prompt,
            run_started_at=started_at,
            run_finished_at=_now_dt(),
            run_error_message=error_message,
        )

    async def _finalize_task_state(
        self,
        task_id: str,
        run_id: str,
        status: str,
        trigger: str,
        finished_at: datetime,
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(ScheduledTask, task_id)
            if row is None:
                return
            row.last_run_id = run_id
            row.last_run_at = finished_at
            row.last_run_status = _status_to_last_run(status)
            row.last_run_trigger = trigger
            row.updated_at = finished_at
            active_handles = await self._handles_for_task(task_id, exclude_run_id=run_id)
            row.status = "running" if active_handles else "enabled"
            await session.commit()

    async def _get_handle(self, run_id: str) -> _RunHandle | None:
        async with self._handles_lock:
            return self._run_handles.get(run_id)

    async def _drop_handle(self, run_id: str) -> None:
        async with self._handles_lock:
            self._run_handles.pop(run_id, None)

    async def _handles_for_task(self, task_id: str, exclude_run_id: str | None = None) -> list[_RunHandle]:
        async with self._handles_lock:
            return [
                handle
                for handle in self._run_handles.values()
                if handle.task_id == task_id and handle.run_id != exclude_run_id
            ]

    async def _all_handles(self) -> list[_RunHandle]:
        async with self._handles_lock:
            return list(self._run_handles.values())

    async def _spawn_process(self, script_path: str, env: dict[str, str]) -> asyncio.subprocess.Process:
        kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": "./",
            "env": env,
        }
        if os.name != "nt":
            kwargs["start_new_session"] = True
        return await asyncio.create_subprocess_exec(sys.executable, script_path, **kwargs)

    async def _write_temp_script(self, task_id: str, code: str) -> str:
        return await asyncio.to_thread(self._write_temp_script_sync, task_id, code)

    @staticmethod
    def _write_temp_script_sync(task_id: str, code: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix=f"task_{task_id[:8]}_",
            dir="./",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(code)
            return tmp.name

    @staticmethod
    def _unlink_path(path: str) -> None:
        try:
            Path(path).unlink()
        except OSError:
            pass


_task_runtime: TaskRuntimeService | None = None


def get_task_runtime() -> TaskRuntimeService:
    global _task_runtime
    if _task_runtime is None:
        _task_runtime = TaskRuntimeService()
    return _task_runtime
