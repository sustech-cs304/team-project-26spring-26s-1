"""HTTP API for scheduled tasks backed fully by ``agent.db`` ORM models."""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from enum import Enum
from typing import Annotated, Any, Literal

import pydantic
from fastapi import APIRouter, Body, HTTPException, Query, status

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
from agent.services.task_runtime import get_task_runtime

router = APIRouter(tags=["tasks"])

_MAX_TASK_TEXT_LEN = 1024
_CRON_5_FIELDS = re.compile(r"^\S+\s+\S+\s+\S+\s+\S+\s+\S+$")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class ExecutionMode(str, Enum):
    prompt = "prompt"
    script = "script"


class TaskListFilterStatus(str, Enum):
    disabled = "disabled"
    enabled = "enabled"
    running = "running"


Status = TaskListFilterStatus


class TaskRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class RunHistoryStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class LastRunStatus(str, Enum):
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class LastRunTrigger(str, Enum):
    agent = "agent"
    cron = "cron"
    manual = "manual"
    telegram = "telegram"


class LogType(str, Enum):
    script_end = "script_end"
    script_start = "script_start"
    script_stderr = "script_stderr"
    script_stdout = "script_stdout"
    tool_call = "tool_call"


class LogEntryStatus(str, Enum):
    success = "success"
    failed = "failed"


class LogMetadata(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    chunk_index: int | None = None
    exit_code: int | None = None
    injected_env_keys: list[str] | None = None
    platform: str | None = None
    python_version: str | None = None
    retry_count: int | None = None


class LogEntryResponse(pydantic.BaseModel):
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
    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "Task"},
    )

    created_at: str
    started_at: str | None = None
    cron_expression: str | None = None
    description: str | None = None
    env_var_refs: list[EnvVarRef]
    execution_mode: ExecutionMode
    id: str
    last_run_at: str | None = None
    last_run_status: LastRunStatus | None = None
    last_run_trigger: LastRunTrigger | None = None
    name: str
    payload: str
    status: Status
    updated_at: str


class TaskDetailResponse(TaskResponse):
    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "Response"},
    )


class TaskListRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    status: TaskListFilterStatus | None = None
    page: int = pydantic.Field(1, ge=1)
    page_size: int = pydantic.Field(20, ge=1, le=200)


class TaskListResponse(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    items: list[TaskResponse]
    total: int


class RunExecutionResponse(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="allow",
        json_schema_extra={"title": "Response"},
    )

    id: str
    task_id: str
    status: RunHistoryStatus
    trigger: LastRunTrigger
    started_at: str
    finished_at: str | None
    error_message: str | None = None
    override_prompt: str | None = None


class TaskRunListResponse(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    items: list[RunExecutionResponse]
    total: int
    page: int
    page_size: int
    task_id: str


class TaskRunListFilterRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    page: int = pydantic.Field(1, ge=1)
    page_size: int = pydantic.Field(20, ge=1, le=200)
    status: RunHistoryStatus | None = None
    trigger: LastRunTrigger | None = None


class TaskRunCompleteRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    status: Literal["success", "failed"]
    error_message: str | None = None


class RunStreamProgressEvent(pydantic.BaseModel):
    run_id: str
    status: RunHistoryStatus = RunHistoryStatus.running
    log: LogEntryResponse
    progress: float | None = pydantic.Field(None, ge=0, le=100)


class RunDetailResponse(RunExecutionResponse):
    logs: list[LogEntryResponse] = pydantic.Field(default_factory=list)


class TaskTriggerRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")

    override_prompt: str | None = None


class TaskUpdateRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    execution_mode: ExecutionMode | None = None
    payload: str | None = None
    cron_expression: str | None = None
    env_var_refs: list[EnvVarRef] | None = None
    started_at: str | None = None

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


def _validate_cron_or_400(expression: str) -> str:
    expr = expression.strip()
    if not _CRON_5_FIELDS.match(expr):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cron_expression must be 5-field cron")
    return expr


def _validate_env_key_or_400(raw_key: str) -> str:
    try:
        return validate_env_var_key(raw_key)
    except ValueError as exc:
        code = exc.args[0] if exc.args else ""
        if code == "too_long":
            _raise_param_too_long()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "Env var name must be alphanumeric and underscore only, length at most 1024"},
        )


def _normalize_task_env_var_refs(refs) -> list[dict]:
    if not refs:
        return []
    return [{"key": _validate_env_key_or_400(r.key)} for r in refs]


def _parse_last_run_status(raw: str | None) -> LastRunStatus | None:
    if raw == "succeeded":
        return LastRunStatus.success
    if raw == "success":
        return LastRunStatus.success
    if raw in {"failed", "cancelled"}:
        return LastRunStatus(raw)
    return None


def _task_to_response(t: dict[str, Any]) -> TaskResponse:
    desc = t.get("description")
    if desc == "":
        desc = None
    last_trigger = t.get("last_run_trigger")
    return TaskResponse(
        created_at=t.get("created_at") or "",
        started_at=t.get("started_at"),
        cron_expression=t.get("cron_expression") or None,
        description=desc,
        env_var_refs=[EnvVarRef(key=str(item.get("key") or "")) for item in (t.get("env_var_refs") or [])],
        execution_mode=ExecutionMode(t.get("execution_mode", "prompt")),
        id=t["id"],
        last_run_at=t.get("last_run_at"),
        last_run_status=_parse_last_run_status(t.get("last_run_status")),
        last_run_trigger=LastRunTrigger(last_trigger) if last_trigger in LastRunTrigger._value2member_map_ else None,
        name=t["name"],
        payload=t.get("payload") if t.get("payload") is not None else "",
        status=Status(t.get("status", "enabled")),
        updated_at=t.get("updated_at") or "",
    )


def _paginate(items: list[Any], page: int, page_size: int) -> tuple[list[Any], int]:
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def _run_status_storage_to_api(raw: str | None) -> RunHistoryStatus:
    if raw == TaskRunStatus.succeeded.value:
        return RunHistoryStatus.success
    if raw in RunHistoryStatus._value2member_map_:
        return RunHistoryStatus(raw)
    return RunHistoryStatus.failed


def _run_trigger_from_run(r: dict[str, Any]) -> LastRunTrigger:
    raw = r.get("trigger") or LastRunTrigger.manual.value
    return LastRunTrigger(raw) if raw in LastRunTrigger._value2member_map_ else LastRunTrigger.manual


def _error_message_public(status: RunHistoryStatus, raw: str | None) -> str | None:
    if status in {RunHistoryStatus.failed, RunHistoryStatus.cancelled}:
        return raw
    return None


def _run_dict_to_execution_response(r: dict[str, Any]) -> RunExecutionResponse:
    api_status = _run_status_storage_to_api(r.get("status"))
    return RunExecutionResponse(
        id=r["id"],
        task_id=r["task_id"],
        status=api_status,
        trigger=_run_trigger_from_run(r),
        started_at=r.get("started_at") or "",
        finished_at=r.get("finished_at"),
        error_message=_error_message_public(api_status, r.get("message")),
        override_prompt=r.get("override_prompt"),
    )


def _coerce_log_entry(run_id: str, raw: dict[str, Any], seq_index: int) -> LogEntryResponse:
    meta = raw.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
    log_type = raw.get("log_type")
    if log_type not in LogType._value2member_map_:
        log_type = LogType.script_stdout.value
    status = raw.get("status", "success")
    if status not in LogEntryStatus._value2member_map_:
        status = LogEntryStatus.success.value
    return LogEntryResponse(
        id=str(raw.get("id") or uuid.uuid4()),
        run_id=str(raw.get("run_id") or run_id),
        step_index=int(raw.get("step_index", seq_index + 1)),
        log_type=LogType(log_type),
        duration_ms=int(raw.get("duration_ms", 0)),
        status=LogEntryStatus(status),
        timestamp=str(raw.get("timestamp") or ""),
        content=raw.get("content"),
        metadata=LogMetadata.model_validate(meta),
        input_params=raw.get("input_params"),
        output=raw.get("output"),
        tool_name=raw.get("tool_name"),
    )


def _run_dict_to_detail(r: dict[str, Any]) -> RunDetailResponse:
    base = _run_dict_to_execution_response(r)
    logs = [
        _coerce_log_entry(r["id"], raw, idx)
        for idx, raw in enumerate(r.get("logs") or [])
        if isinstance(raw, dict)
    ]
    return RunDetailResponse(**base.model_dump(), logs=logs)


def _sse_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


@router.post(
    "/tasks/create",
    response_model=TaskResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def create_task(body: TaskCreateRequest) -> TaskResponse:
    _validate_name_and_description(body.name, body.description)
    runtime = get_task_runtime()
    task = await runtime.create_task(
        name=body.name,
        description=body.description,
        cron_expression=_validate_cron_or_400(body.cron_expression),
        execution_mode=body.execution_mode.value,
        payload=body.payload if body.payload is not None else "",
        env_var_refs=_normalize_task_env_var_refs(body.env_var_refs),
        started_at=body.started_at,
    )
    return _task_to_response(task)


@router.post("/tasks", response_model=TaskListResponse, response_model_exclude_none=True)
async def list_tasks_post(body: TaskListRequest) -> TaskListResponse:
    runtime = get_task_runtime()
    items, total = await runtime.list_tasks(
        status=body.status.value if body.status is not None else None,
        page=body.page,
        page_size=body.page_size,
    )
    return TaskListResponse(items=[_task_to_response(item) for item in items], total=total)


@router.get("/tasks", response_model=TaskListResponse, response_model_exclude_none=True)
async def list_tasks_get(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    task_status: TaskListFilterStatus | None = Query(None, alias="status"),
) -> TaskListResponse:
    runtime = get_task_runtime()
    items, total = await runtime.list_tasks(
        status=task_status.value if task_status is not None else None,
        page=page,
        page_size=page_size,
    )
    return TaskListResponse(items=[_task_to_response(item) for item in items], total=total)


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse, response_model_exclude_none=True)
async def get_task_detail(task_id: str) -> TaskDetailResponse:
    task = await get_task_runtime().get_task(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskDetailResponse.model_validate(_task_to_response(task).model_dump())


@router.patch("/tasks/{task_id}", response_model=TaskDetailResponse, response_model_exclude_none=True)
@router.put("/tasks/{task_id}", response_model=TaskDetailResponse, response_model_exclude_none=True)
@router.post("/tasks/{task_id}", response_model=TaskDetailResponse, response_model_exclude_none=True)
async def patch_task(task_id: str, body: TaskUpdateRequest) -> TaskDetailResponse:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    if "name" in updates:
        _validate_name_and_description(updates["name"], None)
    if "description" in updates:
        _validate_name_and_description(None, updates["description"])
    if "cron_expression" in updates and updates["cron_expression"] is not None:
        updates["cron_expression"] = _validate_cron_or_400(updates["cron_expression"])
    if "env_var_refs" in updates:
        updates["env_var_refs"] = _normalize_task_env_var_refs(body.env_var_refs)
    if "execution_mode" in updates and updates["execution_mode"] is not None:
        updates["execution_mode"] = updates["execution_mode"].value
    task = await get_task_runtime().update_task(task_id, updates)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskDetailResponse.model_validate(_task_to_response(task).model_dump())


@router.post("/tasks/{task_id}/enable", response_model=TaskEnableResponse)
async def enable_task(task_id: str) -> TaskEnableResponse:
    task = await get_task_runtime().set_task_enabled(task_id, True)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskEnableResponse(id=task_id)


@router.post("/tasks/{task_id}/disable", response_model=TaskDisableResponse)
async def disable_task(task_id: str) -> TaskDisableResponse:
    task = await get_task_runtime().set_task_enabled(task_id, False)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskDisableResponse(id=task_id)


@router.post("/tasks/{task_id}/trigger", response_model=TaskTriggerResponse)
async def trigger_task(
    task_id: str,
    body: Annotated[TaskTriggerRequest | None, Body()] = None,
) -> TaskTriggerResponse:
    request = body or TaskTriggerRequest()
    op = (request.override_prompt or "").strip()
    trigger = LastRunTrigger.agent.value if op else LastRunTrigger.manual.value
    run = await get_task_runtime().trigger_task(
        task_id,
        trigger=trigger,
        override_prompt=op or None,
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskTriggerResponse(id=task_id, run_id=run["id"])


async def _list_task_runs_impl(
    task_id: str,
    page: int,
    page_size: int,
    status_filter: RunHistoryStatus | None,
    trigger_filter: LastRunTrigger | None,
) -> TaskRunListResponse:
    runtime = get_task_runtime()
    task = await runtime.get_task(task_id)
    if task is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Task not found")
    runs = await runtime.list_runs_for_task(task_id)
    filtered = []
    for run in runs:
        response = _run_dict_to_execution_response(run)
        if status_filter is not None and response.status != status_filter:
            continue
        if trigger_filter is not None and response.trigger != trigger_filter:
            continue
        filtered.append(run)
    page_items, total = _paginate(filtered, page, page_size)
    return TaskRunListResponse(
        items=[_run_dict_to_execution_response(run) for run in page_items],
        total=total,
        page=page,
        page_size=page_size,
        task_id=task_id,
    )


@router.get("/tasks/{task_id}/runs", response_model=TaskRunListResponse)
async def list_task_runs_get(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: RunHistoryStatus | None = Query(None),
    trigger: LastRunTrigger | None = Query(None),
) -> TaskRunListResponse:
    return await _list_task_runs_impl(task_id, page, page_size, status, trigger)


@router.post("/tasks/{task_id}/runs", response_model=TaskRunListResponse)
async def list_task_runs_post(task_id: str, body: TaskRunListFilterRequest) -> TaskRunListResponse:
    return await _list_task_runs_impl(task_id, body.page, body.page_size, body.status, body.trigger)


def _raise_run_not_found(run_id: str) -> None:
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"message": "Run not found", "run_id": run_id.strip()},
    )


@router.post("/runs/{run_id}/cancel", response_model=RunExecutionResponse)
async def cancel_run(run_id: str) -> RunExecutionResponse:
    current = await get_task_runtime().get_run(run_id)
    if current is None:
        _raise_run_not_found(run_id)
    if current["status"] in {"succeeded", "failed", "cancelled"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Run already in terminal state: {current['status']}")
    run = await get_task_runtime().cancel_run(run_id)
    if run is None:
        _raise_run_not_found(run_id)
    return _run_dict_to_execution_response(run)


@router.post("/runs/{run_id}/complete", response_model=RunExecutionResponse)
async def complete_run(run_id: str, body: TaskRunCompleteRequest) -> RunExecutionResponse:
    current = await get_task_runtime().get_run(run_id)
    if current is None:
        _raise_run_not_found(run_id)
    if current["status"] in {"succeeded", "failed", "cancelled"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Run already in terminal state: {current['status']}")
    run = await get_task_runtime().complete_run(run_id, body.status, body.error_message)
    if run is None:
        _raise_run_not_found(run_id)
    return _run_dict_to_execution_response(run)


@router.get("/runs/{run_id}", response_model=RunDetailResponse, response_model_exclude_none=True)
async def get_run_detail(run_id: str) -> RunDetailResponse:
    run = await get_task_runtime().get_run(run_id)
    if run is None:
        _raise_run_not_found(run_id)
    return _run_dict_to_detail(run)


@router.get("/runs/{run_id}/logs", response_model=list[LogEntryResponse], response_model_exclude_none=True)
async def get_run_logs(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> list[LogEntryResponse]:
    run = await get_task_runtime().get_run(run_id)
    if run is None:
        _raise_run_not_found(run_id)
    items, _ = _paginate(run.get("logs") or [], page, page_size)
    start = (page - 1) * page_size
    return [_coerce_log_entry(run_id, raw, start + idx) for idx, raw in enumerate(items) if isinstance(raw, dict)]


@router.get("/runs/{run_id}/stream", response_class=EventSourceResponse)
async def stream_run_progress(run_id: str) -> EventSourceResponse:
    async def event_generator():
        seen = 0
        while True:
            run = await get_task_runtime().get_run(run_id)
            if run is None:
                yield ServerSentEvent(event="error", data=_sse_json({"detail": "Run not found", "run_id": run_id}))
                return
            logs = run.get("logs") or []
            for raw in logs[seen:]:
                seen += 1
                if not isinstance(raw, dict):
                    continue
                entry = _coerce_log_entry(run_id, raw, seen - 1)
                evt = RunStreamProgressEvent(
                    run_id=run_id,
                    status=_run_status_storage_to_api(run.get("status")),
                    log=entry,
                )
                yield ServerSentEvent(
                    event="progress",
                    data=_sse_json(evt.model_dump(mode="json", exclude_none=True)),
                )
            if run["status"] in {"succeeded", "failed", "cancelled"}:
                yield ServerSentEvent(
                    event="done",
                    data=_sse_json(
                        {
                            "run_id": run_id,
                            "status": _run_status_storage_to_api(run["status"]).value,
                        }
                    ),
                )
                return
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.delete("/tasks/{task_id}", response_model=TaskDeleteResponse)
async def delete_task(task_id: str) -> TaskDeleteResponse:
    ok = await get_task_runtime().delete_task(task_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskDeleteResponse(id=task_id)
