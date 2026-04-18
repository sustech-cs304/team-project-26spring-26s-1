"""HTTP API for schedule / routine tasks.

Storage:

- ``cron/<task_id>.json`` — task definition (file)
- ``agent.db`` ``credentials`` — global env vars (SQLite; see ``env_vars`` module)
- ``agent.db`` — ``task_runs`` / ``task_run_logs`` (SQLite: runs + logs)
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import pydantic
from fastapi import APIRouter, Body, HTTPException, Query, status
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

try:
    from fastapi.sse import EventSourceResponse, ServerSentEvent
except ModuleNotFoundError as e:
    raise ImportError(
        "FastAPI is too old: `fastapi.sse` is missing. Upgrade with: "
        'pip install -U "fastapi[standard]>=0.135.1" '
        "(use the same venv you run uvicorn with)."
    ) from e
from pydantic import field_validator

from agent.api.env_vars import validate_env_var_key
from agent.db.models import TaskRun, TaskRunLog
from agent.task_executor import TaskExecutor, delete_run_json_files_for_task

router = APIRouter(tags=["tasks"])

# Same order of magnitude as cron_watcher / CLI
_TASK_EXECUTOR_TIMEOUT_S = 300
_TASK_EXECUTOR_MAX_CONCURRENT = 8

_MAX_TASK_TEXT_LEN = 1024


def _raise_param_too_long() -> None:
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail={"message": "Parameter too long"},
    )


def _validate_name_and_description(name: str | None, description: str | None) -> None:
    if name is not None and len(name) > _MAX_TASK_TEXT_LEN:
        _raise_param_too_long()
    if description is not None and len(description) > _MAX_TASK_TEXT_LEN:
        _raise_param_too_long()


def _validate_env_key_or_400(raw_key: str) -> str:
    try:
        return validate_env_var_key(raw_key)
    except ValueError as e:
        code = e.args[0] if e.args else ""
        if code == "too_long":
            _raise_param_too_long()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "Env var name must be alphanumeric and underscore only, length at most 1024"},
        )


def _normalize_task_env_var_refs(refs) -> list[dict]:
    if not refs:
        return []
    out: list[dict] = []
    for r in refs:
        k = _validate_env_key_or_400(r.key)
        out.append({"key": k})
    return out


CRON_DIR = Path("./cron")
DB_PATH = Path("./agent.db")

_run_engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", future=True)
_run_session = async_sessionmaker(_run_engine, expire_on_commit=False)

def _normalize_id(raw: str) -> str:
    s = raw.strip()
    if not s or "/" in s or "\\" in s or ".." in s:
        return ""
    return s

_CRON_5_FIELDS = re.compile(r"^\S+\s+\S+\s+\S+\s+\S+\s+\S+$")


def _ensure_cron_dir() -> None:
    CRON_DIR.mkdir(exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_task(task_id: str) -> dict | None:
    task_id = _normalize_id(task_id)
    p = CRON_DIR / f"{task_id}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text("utf-8"))


def _write_task(task: dict) -> None:
    _ensure_cron_dir()
    p = CRON_DIR / f"{task['id']}.json"
    p.write_text(json.dumps(task, ensure_ascii=False, indent=2), "utf-8")


def _delete_task_file(task_id: str) -> bool:
    p = CRON_DIR / f"{task_id}.json"
    if not p.is_file():
        return False
    p.unlink()
    return True


def _all_tasks() -> list[dict]:
    _ensure_cron_dir()
    tasks = []
    for p in sorted(CRON_DIR.glob("*.json")):
        if p.name == "env_vars.json":
            continue
        try:
            tasks.append(json.loads(p.read_text("utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return tasks


def _db_row_to_ts(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _parse_dt(val, *, required: bool = False) -> datetime | None:
    """Parse API / dict timestamps into timezone-aware ``datetime`` for the ORM."""
    if val is None:
        return datetime.now(timezone.utc) if required else None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return datetime.now(timezone.utc) if required else None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return datetime.now(timezone.utc) if required else None
    return datetime.now(timezone.utc) if required else None


def _orm_log_to_log_dict(run_id: str, lg: TaskRunLog) -> dict:
    raw = getattr(lg, "entry_json", None)
    if not raw:
        raise ValueError(f"Run {run_id} log row {lg.id} is missing entry_json")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Run {run_id} log row {lg.id} has invalid entry_json") from exc


def _db_run_to_dict(row: TaskRun) -> dict:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "status": row.status,
        "trigger": row.trigger,
        "override_prompt": row.override_prompt,
        "started_at": _db_row_to_ts(row.started_at) or "",
        "finished_at": _db_row_to_ts(row.finished_at),
        "message": row.error_message,
        "logs": [_orm_log_to_log_dict(row.id, lg) for lg in (row.logs or [])],
    }


async def _read_run(run_id: str) -> dict | None:
    run_id = _normalize_id(run_id)
    if not run_id:
        return None
    async with _run_session() as session:
        stmt = (
            select(TaskRun)
            .options(selectinload(TaskRun.logs))
            .where(TaskRun.id == run_id)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return _db_run_to_dict(row)


def _raise_run_not_found(run_id: str) -> None:
    rid = _normalize_id(run_id)
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"message": "Run not found", "run_id": rid or run_id.strip()},
    )


async def _write_run(run: dict) -> None:
    started_at = _parse_dt(run.get("started_at"), required=True)
    finished_at = _parse_dt(run.get("finished_at"))
    async with _run_session() as session:
        existing = await session.get(TaskRun, run["id"])
        if existing:
            existing.status = run["status"]
            existing.trigger = run.get("trigger", "manual")
            existing.override_prompt = run.get("override_prompt")
            existing.started_at = started_at
            existing.finished_at = finished_at
            existing.error_message = run.get("message")
        else:
            session.add(TaskRun(
                id=run["id"],
                task_id=run["task_id"],
                status=run["status"],
                trigger=run.get("trigger", "manual"),
                override_prompt=run.get("override_prompt"),
                started_at=started_at,
                finished_at=finished_at,
                error_message=run.get("message"),
            ))
        await session.commit()


async def _runs_for_task(task_id: str) -> list[dict]:
    async with _run_session() as session:
        stmt = (
            select(TaskRun)
            .options(selectinload(TaskRun.logs))
            .where(TaskRun.task_id == task_id)
            .order_by(TaskRun.started_at.desc())
        )
        result = await session.execute(stmt)
        return [_db_run_to_dict(row) for row in result.scalars().all()]


async def _delete_runs_for_task(task_id: str) -> None:
    delete_run_json_files_for_task(task_id)
    async with _run_session() as session:
        await session.execute(
            delete(TaskRunLog).where(
                TaskRunLog.run_id.in_(
                    select(TaskRun.id).where(TaskRun.task_id == task_id)
                )
            )
        )
        await session.execute(delete(TaskRun).where(TaskRun.task_id == task_id))
        await session.commit()


class ExecutionMode(str, Enum):
    prompt = "prompt"
    script = "script"


class TaskListFilterStatus(str, Enum):
    disabled = "disabled"
    enabled = "enabled"
    running = "running"


Status = TaskListFilterStatus


class TaskRunStatus(str, Enum):
    """Storage / internal run status (success is ``succeeded``)."""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class RunHistoryStatus(str, Enum):
    """Run history filter and API status (matches frontend Status; success is ``success``)."""

    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class LastRunStatus(str, Enum):
    """Matches frontend `LastRunStatus` (terminal outcomes)."""

    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class LastRunTrigger(str, Enum):
    """Matches frontend `LastRunTrigger`."""

    agent = "agent"
    cron = "cron"
    manual = "manual"
    telegram = "telegram"


class LogType(str, Enum):
    """Matches frontend ``LogType``."""

    script_end = "script_end"
    script_start = "script_start"
    script_stderr = "script_stderr"
    script_stdout = "script_stdout"
    tool_call = "tool_call"


class LogEntryStatus(str, Enum):
    """Per-log step status (matches frontend ``Status``)."""

    success = "success"
    failed = "failed"


class LogMetadata(pydantic.BaseModel):
    """Matches frontend ``Metadata``."""

    model_config = pydantic.ConfigDict(extra="allow")

    chunk_index: int | None = None
    exit_code: int | None = None
    injected_env_keys: list[str] | None = None
    platform: str | None = None
    python_version: str | None = None
    retry_count: int | None = None


class LogEntryResponse(pydantic.BaseModel):
    """Matches frontend ``LogEntry`` / ``Response``."""

    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "LogEntry"},
    )

    content: str | None = None
    duration_ms: int = 0
    id: str
    input_params: dict[str, Any] | None = None
    log_type: LogType
    metadata: LogMetadata = pydantic.Field(default_factory=LogMetadata)
    output: dict[str, Any] | None = None
    run_id: str
    status: LogEntryStatus
    step_index: int
    timestamp: str
    tool_name: str | None = None


class EnvVarRef(pydantic.BaseModel):
    """Task-level env ref: ``key`` only, aligned with the global env store."""

    model_config = pydantic.ConfigDict(extra="ignore")
    key: str = pydantic.Field(..., description="Name in the global env store")


class TaskCreateRequest(pydantic.BaseModel):
    cron_expression: str = pydantic.Field(..., description="5-field cron expression")
    description: str
    env_var_refs: list[EnvVarRef] | None = None
    execution_mode: ExecutionMode
    name: str
    payload: str | None = None
    started_at: str | None = pydantic.Field(
        None,
        description="Business start time; omit to leave unset until first enable/trigger",
    )


class TaskResponse(pydantic.BaseModel):
    """Full task record; field order matches frontend ``Task`` (list / create).

    Optional fields use ``None``; routes use ``response_model_exclude_none`` so JSON omits them (no ``null``).

    **Note:** ``payload`` / ``env_var_refs`` / ``id`` use ``Field(...)`` without defaults so OpenAPI
    marks them **required** (matches strict frontend types). Empty payload is ``""``; empty env list is ``[]``.
    """

    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "Task"},
    )

    # Order aligned with frontend `Task`
    created_at: str = pydantic.Field(..., description="When the task record was created")
    started_at: str | None = pydantic.Field(
        None,
        description="Business start time (may differ from created_at)",
    )
    cron_expression: str | None = pydantic.Field(
        None,
        description="5-field cron; omitted when not scheduled (manual / Agent / Telegram only)",
    )
    description: str | None = pydantic.Field(None, description="Max 1024 chars; omitted when empty")
    env_var_refs: list[EnvVarRef] = pydantic.Field(
        ...,
        description="Task-level env; overrides globals with same name (use [] when none)",
    )
    execution_mode: ExecutionMode
    id: str = pydantic.Field(..., description="System-generated id")
    last_run_at: str | None = pydantic.Field(None, description="Last execution time (ISO 8601)")
    last_run_status: LastRunStatus | None = None
    last_run_trigger: LastRunTrigger | None = None
    name: str = pydantic.Field(..., max_length=1024, description="Max 1024 chars")
    payload: str = pydantic.Field(..., description="Prompt or script body (may be empty string)")
    status: Status
    updated_at: str


class TaskDetailResponse(TaskResponse):
    """``GET`` / ``PATCH`` ``/tasks/{task_id}`` 200 body; matches frontend ``Response``."""

    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={
            "title": "Response",
            "description": "Task detail 200 response (frontend `Response`).",
        },
    )


class TaskListRequest(pydantic.BaseModel):
    """JSON body for **POST /tasks** (list / filter)."""

    model_config = pydantic.ConfigDict(extra="allow")

    status: TaskListFilterStatus | None = pydantic.Field(
        None,
        description="Omit or null to return tasks in **any** status.",
    )
    page: int = pydantic.Field(1, ge=1)
    page_size: int = pydantic.Field(20, ge=1, le=200)


class TaskListResponse(pydantic.BaseModel):
    """Matches frontend: `{ items: Task[], total: number }`."""

    model_config = pydantic.ConfigDict(extra="allow")

    items: list[TaskResponse]
    total: int


class RunExecutionResponse(pydantic.BaseModel):
    """Matches frontend single-run ``Response`` (history row / run detail body)."""

    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "Response"},
    )

    id: str
    task_id: str
    status: RunHistoryStatus = pydantic.Field(
        ...,
        description="pending / running / success / failed / cancelled",
    )
    trigger: LastRunTrigger = pydantic.Field(
        ...,
        description="cron / manual / agent / telegram",
    )
    started_at: str = pydantic.Field(..., description="Start time (ISO 8601)")
    finished_at: str | None = pydantic.Field(
        ...,
        description="End time; null while still running",
    )
    error_message: str | None = pydantic.Field(
        None,
        description="Top-level error when failed",
    )
    override_prompt: str | None = pydantic.Field(
        None,
        description="Override prompt for Agent trigger; null for other triggers",
    )


class TaskRunListResponse(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    items: list[RunExecutionResponse]
    total: int
    page: int
    page_size: int
    task_id: str


class TaskRunListFilterRequest(pydantic.BaseModel):
    """Matches frontend run history Request (JSON body for POST /tasks/{task_id}/runs)."""

    model_config = pydantic.ConfigDict(extra="allow")

    page: int = pydantic.Field(1, ge=1)
    page_size: int = pydantic.Field(20, ge=1, le=200)
    status: RunHistoryStatus | None = pydantic.Field(
        None,
        description="Filter: cancelled / failed / pending / running / success",
    )
    trigger: LastRunTrigger | None = pydantic.Field(
        None,
        description="Filter trigger: agent / cron / manual / telegram",
    )


class TaskRunCompleteRequest(pydantic.BaseModel):
    """Mark run success/failure; sets ``finished_at`` and stored ``message`` (exposed as error_message)."""

    model_config = pydantic.ConfigDict(extra="forbid")

    status: Literal["success", "failed"] = pydantic.Field(
        ...,
        description="success → stored as succeeded; failed → stored as failed",
    )
    error_message: str | None = pydantic.Field(
        None,
        description="Failure or note text; stored as message; list/detail map to error_message",
    )


class RunStreamProgressEvent(pydantic.BaseModel):
    run_id: str
    status: RunHistoryStatus = RunHistoryStatus.running
    log: LogEntryResponse
    progress: float | None = pydantic.Field(None, ge=0, le=100)


class RunDetailResponse(RunExecutionResponse):
    """Run detail: same as ``Response`` plus ``logs``."""

    logs: list[LogEntryResponse] = pydantic.Field(default_factory=list)


class TaskTriggerRequest(pydantic.BaseModel):
    """Trigger a run; non-empty ``override_prompt`` counts as Agent trigger."""

    model_config = pydantic.ConfigDict(extra="allow")

    override_prompt: str | None = pydantic.Field(
        None,
        description="Override prompt for Agent; omit or empty for manual etc.",
    )


class TaskUpdateRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    execution_mode: ExecutionMode | None = None
    payload: str | None = None
    cron_expression: str | None = None
    env_var_refs: list[EnvVarRef] | None = None
    started_at: str | None = pydantic.Field(
        None,
        description="Business start time; set explicitly or clear (null)",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_or_null(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _CRON_5_FIELDS.match(v.strip()):
            raise ValueError("cron_expression must be 5-field cron or null")
        return v.strip()


class TaskEnableResponse(pydantic.BaseModel):
    id: str
    status: TaskListFilterStatus = TaskListFilterStatus.enabled
    message: str = "Task enabled."


class TaskDisableResponse(pydantic.BaseModel):
    id: str
    status: TaskListFilterStatus = TaskListFilterStatus.disabled
    message: str = "Task disabled."


class TaskTriggerResponse(pydantic.BaseModel):
    id: str
    run_id: str
    message: str = "Run created."
    status: TaskListFilterStatus = TaskListFilterStatus.running


class TaskDeleteResponse(pydantic.BaseModel):
    id: str
    message: str = "Task deleted."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_last_run_status(raw: str | None) -> LastRunStatus | None:
    if not raw:
        return None
    if raw == "succeeded":
        return LastRunStatus.success
    try:
        return LastRunStatus(raw)
    except ValueError:
        return None


def _task_to_response(t: dict) -> TaskResponse:
    refs = t.get("env_var_refs")
    if refs is None:
        refs_list: list = []
    else:
        refs_list = refs
    lr_s = t.get("last_run_status")
    lr_tr = t.get("last_run_trigger")
    desc = t.get("description")
    if desc == "":
        desc = None
    return TaskResponse(
        created_at=t.get("created_at") or "",
        started_at=t.get("started_at"),
        cron_expression=t.get("cron_expression") or None,
        description=desc,
        env_var_refs=[
            EnvVarRef(key=str(r.get("key", "")) if isinstance(r, dict) else "")
            for r in refs_list
        ],
        execution_mode=ExecutionMode(t.get("execution_mode", "prompt")),
        id=t.get("id"),
        last_run_at=t.get("last_run_at"),
        last_run_status=_parse_last_run_status(lr_s) if isinstance(lr_s, str) else None,
        last_run_trigger=LastRunTrigger(lr_tr) if lr_tr else None,
        name=t["name"],
        payload=t.get("payload") if t.get("payload") is not None else "",
        status=Status(t.get("status", "enabled")),
        updated_at=t.get("updated_at") or "",
    )


def _paginate(items: list, page: int, page_size: int) -> tuple[list, int]:
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def _run_status_storage_to_api(raw: str | None) -> RunHistoryStatus:
    s = raw or "pending"
    if s == TaskRunStatus.succeeded.value:
        return RunHistoryStatus.success
    try:
        return RunHistoryStatus(s)
    except ValueError:
        return RunHistoryStatus.failed


def _run_trigger_from_run(r: dict) -> LastRunTrigger:
    tr = r.get("trigger")
    if not tr:
        return LastRunTrigger.manual
    try:
        return LastRunTrigger(tr)
    except ValueError:
        return LastRunTrigger.manual


def _update_task_after_terminal_run(r: dict) -> None:
    """After run is terminal and ``finished_at`` is set, sync task last_run_* fields."""
    task = _read_task(r["task_id"])
    if not task:
        return
    finished = r.get("finished_at") or _now_iso()
    task["last_run_at"] = finished
    st = r.get("status")
    if st == TaskRunStatus.succeeded.value:
        task["last_run_status"] = LastRunStatus.success.value
    elif st == TaskRunStatus.failed.value:
        task["last_run_status"] = LastRunStatus.failed.value
    elif st == TaskRunStatus.cancelled.value:
        task["last_run_status"] = LastRunStatus.cancelled.value
    if task.get("last_run_trigger") is None:
        tr = r.get("trigger")
        task["last_run_trigger"] = tr if tr else LastRunTrigger.manual.value
    if task.get("status") == TaskListFilterStatus.running.value:
        task["status"] = TaskListFilterStatus.enabled.value
    task["updated_at"] = finished
    _write_task(task)


def _error_message_public(status: RunHistoryStatus, raw: str | None) -> str | None:
    """Stored message maps to public error_message only on failed/cancelled."""
    if not raw:
        return None
    if status in (RunHistoryStatus.failed, RunHistoryStatus.cancelled):
        return raw
    return None


def _run_dict_to_execution_response(r: dict) -> RunExecutionResponse:
    raw_status = r.get("status", "pending")
    st = _run_status_storage_to_api(raw_status)
    return RunExecutionResponse(
        id=r["id"],
        task_id=r["task_id"],
        status=st,
        trigger=_run_trigger_from_run(r),
        started_at=r.get("started_at") or "",
        finished_at=r.get("finished_at"),
        error_message=_error_message_public(st, r.get("message")),
        override_prompt=r.get("override_prompt"),
    )


def _coerce_log_entry(run_id: str, raw: dict, seq_index: int) -> LogEntryResponse:
    """Normalize log dict from DB/file into ``LogEntryResponse``."""
    if not raw.get("log_type"):
        raise ValueError("Log entry is missing log_type")
    meta = raw.get("metadata")
    if meta is None or not isinstance(meta, dict):
        meta = {}
    try:
        lt = LogType(raw["log_type"])
    except (ValueError, KeyError, TypeError):
        lt = LogType.script_stdout
    try:
        st = LogEntryStatus(str(raw.get("status", "success")))
    except ValueError:
        st = LogEntryStatus.success
    return LogEntryResponse(
        id=str(raw.get("id") or uuid.uuid4()),
        run_id=str(raw.get("run_id") or run_id),
        step_index=int(raw.get("step_index", seq_index + 1)),
        log_type=lt,
        duration_ms=int(raw.get("duration_ms", 0)),
        status=st,
        timestamp=str(raw.get("timestamp") or ""),
        content=raw.get("content"),
        metadata=LogMetadata.model_validate(meta),
        input_params=raw.get("input_params"),
        output=raw.get("output"),
        tool_name=raw.get("tool_name"),
    )


def _run_dict_to_detail(r: dict) -> RunDetailResponse:
    base = _run_dict_to_execution_response(r)
    raw_logs = r.get("logs") or []
    lines: list[LogEntryResponse] = []
    for i, l in enumerate(raw_logs):
        if not isinstance(l, dict):
            continue
        try:
            lines.append(_coerce_log_entry(r["id"], l, i))
        except Exception:
            continue
    return RunDetailResponse(**base.model_dump(), logs=lines)


def _filter_runs_for_history(
    runs: list[dict],
    status_filter: RunHistoryStatus | None,
    trigger_filter: LastRunTrigger | None,
) -> list[dict]:
    out: list[dict] = []
    for r in runs:
        if status_filter is not None:
            if _run_status_storage_to_api(r.get("status")) != status_filter:
                continue
        if trigger_filter is not None:
            if _run_trigger_from_run(r) != trigger_filter:
                continue
        out.append(r)
    return out


async def _list_task_runs_impl(
    task_id: str,
    page: int,
    page_size: int,
    status_filter: RunHistoryStatus | None,
    trigger_filter: LastRunTrigger | None,
) -> TaskRunListResponse:
    if not _read_task(task_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Task not found")
    all_runs = await _runs_for_task(task_id)
    filtered = _filter_runs_for_history(all_runs, status_filter, trigger_filter)
    page_items, total = _paginate(filtered, page, page_size)
    return TaskRunListResponse(
        items=[_run_dict_to_execution_response(r) for r in page_items],
        total=total,
        page=page,
        page_size=page_size,
        task_id=task_id,
    )


def _list_tasks_page(
    task_status: TaskListFilterStatus | None,
    page: int,
    page_size: int,
) -> TaskListResponse:
    all_raw = _all_tasks()
    if task_status is None:
        all_t = all_raw
    else:
        all_t = [t for t in all_raw if t.get("status") == task_status.value]
    page_items, total = _paginate(all_t, page, page_size)
    return TaskListResponse(
        items=[_task_to_response(t) for t in page_items],
        total=total,
    )


@router.post(
    "/tasks/create",
    response_model=TaskResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Create a scheduled task",
)
async def create_task(body: TaskCreateRequest) -> TaskResponse:
    _validate_name_and_description(body.name, body.description)
    env_refs = _normalize_task_env_var_refs(body.env_var_refs)
    task_id = str(uuid.uuid4())
    now = _now_iso()
    task = {
        "id": task_id,
        "name": body.name,
        "description": body.description,
        "cron_expression": body.cron_expression,
        "execution_mode": body.execution_mode.value,
        "status": "enabled",
        "payload": body.payload if body.payload is not None else "",
        "env_var_refs": env_refs,
        "created_at": now,
        "started_at": body.started_at,
        "updated_at": now,
    }
    _write_task(task)
    return _task_to_response(task)


@router.post(
    "/tasks",
    response_model=TaskListResponse,
    response_model_exclude_none=True,
    summary="List tasks (JSON body)",
    description=(
        "**Not task detail.** Returns a paged list `{ items: Task[], total }`. "
        "For **one** task use **`GET /tasks/{task_id}`** (id in path). "
        "`status` is optional (omit = all). Or use **GET /tasks** with query params."
    ),
)
async def list_tasks_post(body: TaskListRequest) -> TaskListResponse:
    return _list_tasks_page(body.status, body.page, body.page_size)


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    response_model_exclude_none=True,
    summary="List tasks (query params)",
    description=(
        "**Not task detail.** Returns `{ items, total }` with multiple tasks. "
        "**Single task** → **`GET /tasks/{task_id}`**. "
        "`status` optional; e.g. `GET /tasks?page=1&page_size=20`."
    ),
)
async def list_tasks_get(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    task_status: TaskListFilterStatus | None = Query(None, alias="status"),
) -> TaskListResponse:
    return _list_tasks_page(task_status, page, page_size)


@router.get(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    response_model_exclude_none=True,
    summary="Get one task",
    description=(
        "**Path `task_id`** selects the task. Response is **one** task object (`Response` / Task), "
        "**no** `items` array. Lists use **GET/POST /tasks**."
    ),
)
async def get_task_detail(task_id: str) -> TaskDetailResponse:
    t = _read_task(task_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskDetailResponse.model_validate(_task_to_response(t).model_dump())


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    response_model_exclude_none=True,
    summary="Update task (PATCH, partial)",
)
@router.put(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    response_model_exclude_none=True,
    summary="Update task (PUT, same as PATCH)",
    description="Same as **PATCH /tasks/{task_id}**; use when the client only supports **PUT**.",
)
@router.post(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    response_model_exclude_none=True,
    summary="Update task (POST, same as PATCH)",
    description=(
        "Same as **PATCH /tasks/{task_id}**. Use this route for **POST** updates; "
        "do not use **POST /tasks** (that lists tasks). Clients that can only send **POST** should use here instead of PATCH."
    ),
)
async def patch_task(task_id: str, body: TaskUpdateRequest) -> TaskDetailResponse:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    t = _read_task(task_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if "name" in updates and len(updates["name"]) > _MAX_TASK_TEXT_LEN:
        _raise_param_too_long()
    if "description" in updates:
        d = updates["description"]
        if d is not None and len(d) > _MAX_TASK_TEXT_LEN:
            _raise_param_too_long()
    for field in ("name", "description", "payload", "cron_expression"):
        if field in updates:
            t[field] = updates[field]
    if "execution_mode" in updates:
        t["execution_mode"] = updates["execution_mode"].value
    if "env_var_refs" in updates:
        refs = body.env_var_refs
        t["env_var_refs"] = _normalize_task_env_var_refs(refs) if refs else []
    if "started_at" in updates:
        t["started_at"] = updates["started_at"]
    t["updated_at"] = _now_iso()
    _write_task(t)
    return TaskDetailResponse.model_validate(_task_to_response(t).model_dump())


@router.post("/tasks/{task_id}/enable", response_model=TaskEnableResponse, summary="Enable a task")
async def enable_task(task_id: str) -> TaskEnableResponse:
    t = _read_task(task_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    now = _now_iso()
    if not t.get("started_at"):
        t["started_at"] = now
    t["status"] = "enabled"
    t["updated_at"] = now
    _write_task(t)
    return TaskEnableResponse(id=task_id)


@router.post("/tasks/{task_id}/disable", response_model=TaskDisableResponse, summary="Disable a task")
async def disable_task(task_id: str) -> TaskDisableResponse:
    t = _read_task(task_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    t["status"] = "disabled"
    t["updated_at"] = _now_iso()
    _write_task(t)
    return TaskDisableResponse(id=task_id)


@router.post("/tasks/{task_id}/trigger", response_model=TaskTriggerResponse, summary="Trigger a task run")
async def trigger_task(
    task_id: str,
    body: Annotated[TaskTriggerRequest | None, Body()] = None,
) -> TaskTriggerResponse:
    t = _read_task(task_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    b = body or TaskTriggerRequest()
    op = (b.override_prompt or "").strip()
    if op:
        trig = LastRunTrigger.agent.value
        override_prompt: str | None = op
    else:
        trig = LastRunTrigger.manual.value
        override_prompt = None

    task_copy = dict(t)
    if not task_copy.get("started_at"):
        task_copy["started_at"] = _now_iso()

    executor = TaskExecutor(
        timeout=_TASK_EXECUTOR_TIMEOUT_S,
        max_concurrent=_TASK_EXECUTOR_MAX_CONCURRENT,
    )
    run, _ = await asyncio.to_thread(
        executor.execute_background,
        task_copy,
        trig,
        override_prompt,
    )
    return TaskTriggerResponse(id=task_id, run_id=run["id"])


@router.get(
    "/tasks/{task_id}/runs",
    response_model=TaskRunListResponse,
    summary="Run history (query)",
    description=(
        "Filters match frontend **Request**: `page`, `page_size`, "
        "**`status`** (cancelled / failed / pending / running / **success**), "
        "**`trigger`** (agent / cron / manual / telegram). "
        "Or **POST** the same path with a JSON body. "
        "**Unknown task** → **400**; **task exists but no runs** → **200** with empty `items`."
    ),
)
async def list_task_runs_get(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: RunHistoryStatus | None = Query(
        None,
        description="Filter status (success in API; stored as succeeded)",
    ),
    trigger: LastRunTrigger | None = Query(None, description="Filter trigger source"),
) -> TaskRunListResponse:
    return await _list_task_runs_impl(task_id, page, page_size, status, trigger)


@router.post(
    "/tasks/{task_id}/runs",
    response_model=TaskRunListResponse,
    summary="Run history (JSON body)",
    description=(
        "Same as **GET /tasks/{task_id}/runs**; body fields match frontend **Request** (`status` / `trigger`). "
        "**Unknown task** → **400**; **task exists, no runs** → **200** empty list."
    ),
)
async def list_task_runs_post(
    task_id: str,
    body: TaskRunListFilterRequest,
) -> TaskRunListResponse:
    return await _list_task_runs_impl(
        task_id,
        body.page,
        body.page_size,
        body.status,
        body.trigger,
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunExecutionResponse,
    summary="Cancel a run",
    description=(
        "Returns a single run object matching frontend **Run Response** (status cancelled). "
        "Already terminal → **404**."
    ),
)
async def cancel_run(run_id: str) -> RunExecutionResponse:
    r = await _read_run(run_id)
    if not r:
        _raise_run_not_found(run_id)
    terminal = {"succeeded", "failed", "cancelled"}
    if r["status"] in terminal:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Run already in terminal state: {r['status']}",
        )
    r["status"] = "cancelled"
    r["finished_at"] = _now_iso()
    r["message"] = "Cancelled by user."
    await _write_run(r)
    _update_task_after_terminal_run(r)
    return _run_dict_to_execution_response(r)


@router.post(
    "/runs/{run_id}/complete",
    response_model=RunExecutionResponse,
    summary="Complete run (success/failure)",
    description=(
        "Sets run to terminal and writes **end time** ``finished_at`` and ``error_message`` (stored as message). "
        "Mutually exclusive with **cancel**: already terminal → **404**."
    ),
)
async def complete_run(run_id: str, body: TaskRunCompleteRequest) -> RunExecutionResponse:
    r = await _read_run(run_id)
    if not r:
        _raise_run_not_found(run_id)
    terminal = {"succeeded", "failed", "cancelled"}
    if r["status"] in terminal:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Run already in terminal state: {r['status']}",
        )
    now = _now_iso()
    r["finished_at"] = now
    r["status"] = (
        TaskRunStatus.succeeded.value
        if body.status == "success"
        else TaskRunStatus.failed.value
    )
    r["message"] = body.error_message
    await _write_run(r)
    _update_task_after_terminal_run(r)
    return _run_dict_to_execution_response(r)


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    response_model_exclude_none=True,
    summary="Run detail (single run)",
    description=(
        "Returns full **RunExecutionResponse** plus **logs**; "
        "data from **agent.db** ``task_runs`` / ``task_run_logs``. "
        "If 404, check **run_id** (not task_id)."
    ),
)
async def get_run_detail(run_id: str) -> RunDetailResponse:
    raw = await _read_run(run_id)
    if not raw:
        _raise_run_not_found(run_id)
    return _run_dict_to_detail(raw)


@router.get(
    "/runs/{run_id}/logs",
    response_model=list[LogEntryResponse],
    response_model_exclude_none=True,
    summary="Run logs (JSON array)",
    description=(
        "Body is a **LogEntry array** (``[{...}, ...]``), no outer ``items`` / ``total``. "
        "From **agent.db** ``task_run_logs``, same source as **GET /runs/{run_id}** ``logs``. "
        "``page`` / ``page_size`` slice the log array (default page 1, size 20)."
    ),
)
async def get_run_logs(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> list[LogEntryResponse]:
    r = await _read_run(run_id)
    if not r:
        _raise_run_not_found(run_id)
    all_logs: list[dict] = r.get("logs") or []
    page_items, _ = _paginate(all_logs, page, page_size)
    start = (page - 1) * page_size
    items: list[LogEntryResponse] = []
    for idx, raw in enumerate(page_items):
        if not isinstance(raw, dict):
            continue
        try:
            items.append(_coerce_log_entry(run_id, raw, start + idx))
        except Exception:
            continue
    return items


def _sse_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


@router.get(
    "/runs/{run_id}/stream",
    response_class=EventSourceResponse,
    summary="SSE run progress (log lines)",
    description=(
        "Polls **agent.db** for the run and streams **progress** as ``logs`` grow; "
        "each event **data** is a **JSON string** (`progress` / `error` / `done`)."
    ),
)
async def stream_run_progress(run_id: str) -> EventSourceResponse:
    """Poll DB for new log entries until terminal status."""

    async def event_generator():
        seen = 0
        while True:
            r = await _read_run(run_id)
            if not r:
                yield ServerSentEvent(
                    event="error",
                    data=_sse_json({"detail": "Run not found", "run_id": run_id}),
                )
                return
            logs: list[dict] = r.get("logs") or []
            for log in logs[seen:]:
                seen += 1
                if not isinstance(log, dict):
                    continue
                try:
                    entry = _coerce_log_entry(run_id, log, seen - 1)
                except Exception:
                    continue
                evt = RunStreamProgressEvent(
                    run_id=run_id,
                    status=_run_status_storage_to_api(r.get("status")),
                    log=entry,
                )
                yield ServerSentEvent(
                    event="progress",
                    data=_sse_json(evt.model_dump(mode="json", exclude_none=True)),
                )
            if r["status"] in {"succeeded", "failed", "cancelled"}:
                yield ServerSentEvent(
                    event="done",
                    data=_sse_json(
                        {
                            "run_id": run_id,
                            "status": _run_status_storage_to_api(r.get("status")).value,
                        }
                    ),
                )
                return
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.delete(
    "/tasks/{task_id}",
    response_model=TaskDeleteResponse,
    summary="Delete a task",
)
async def delete_task(task_id: str) -> TaskDeleteResponse:
    if not _delete_task_file(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    await _delete_runs_for_task(task_id)
    return TaskDeleteResponse(id=task_id)
