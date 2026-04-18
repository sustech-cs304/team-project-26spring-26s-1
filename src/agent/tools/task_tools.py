"""Async scheduled task tools backed by the shared task runtime."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from langchain.tools import tool
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from agent.api.env_vars import validate_env_var_key
from agent.api.task import LastRunTrigger, _coerce_log_entry, _run_dict_to_execution_response
from agent.services.task_runtime import get_task_runtime

_MAX_TEXT = 1024
AgentExecutionMode = Literal["script"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_like_to_calendar_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            from agent.services.calendar_time import unix_sec_to_local_ymdhms

            parsed = unix_sec_to_local_ymdhms(int(value))
            return f"{parsed['year']:04d}-{parsed['month']:02d}-{parsed['day']:02d}"
        except (ValueError, OSError, OverflowError):
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).date().isoformat()
    except ValueError:
        return None


def _enrich_iso_date_fields(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    out = dict(payload)
    for key in keys:
        if key in out and out[key] is not None:
            cal = _iso_like_to_calendar_date(out[key])
            if cal is not None:
                out[f"{key}_date"] = cal
    return out


_TASK_PUBLIC_DATE_KEYS = ("created_at", "started_at", "updated_at", "last_run_at")
_RUN_SUMMARY_DATE_KEYS = ("started_at", "finished_at")


def _normalize_env_keys(keys: list[str] | None) -> tuple[list[dict[str, str]] | None, str | None]:
    if keys is None:
        return None, None
    out: list[dict[str, str]] = []
    for key in keys:
        try:
            out.append({"key": validate_env_var_key(key)})
        except ValueError:
            return None, f"Invalid env var key: {key!r}"
    return out, None


def _cron_string_is_llm_sentinel(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    return stripped.lower() in {"none", "null", "nil"}


def _normalize_cron_expression(expr: str) -> tuple[str | None, str | None]:
    parts = expr.strip().split()
    if len(parts) != 5:
        return None, (
            f"cron must have exactly 5 fields (got {len(parts)}); "
            "order: minute hour day-of-month month day-of-week."
        )
    return " ".join(parts), None


def _validate_task_core(
    name: str,
    description: str,
    cron_expression: str,
    execution_mode: AgentExecutionMode,
    payload: str,
    env_var_keys: list[str] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if len(name) > _MAX_TEXT or len(description) > _MAX_TEXT:
        return None, f"name and description must be at most {_MAX_TEXT} characters"
    if _cron_string_is_llm_sentinel(cron_expression):
        return None, (
            "cron_expression must be a valid 5-field cron string, not the text 'None', 'null', or empty."
        )
    normalized_cron, cron_error = _normalize_cron_expression(cron_expression)
    if cron_error:
        return None, cron_error
    refs, env_error = _normalize_env_keys(env_var_keys)
    if env_error:
        return None, env_error
    return {
        "name": name.strip(),
        "description": description.strip(),
        "cron_expression": normalized_cron,
        "execution_mode": execution_mode,
        "payload": payload if payload is not None else "",
        "env_var_refs": refs if refs is not None else [],
    }, None


def _cron_fields_public(cron_expression: str | None) -> dict[str, Any] | None:
    if not cron_expression:
        return None
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return {"valid": False, "raw": cron_expression}
    return {
        "valid": True,
        "minute": parts[0],
        "hour": parts[1],
        "day_of_month": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def _task_public_dict(task: dict[str, Any]) -> dict[str, Any]:
    cron_expression = task.get("cron_expression")
    payload = {
        "id": task.get("id"),
        "name": task.get("name"),
        "description": task.get("description"),
        "cron_expression": cron_expression,
        "cron_fields": _cron_fields_public(cron_expression) if isinstance(cron_expression, str) else None,
        "execution_mode": task.get("execution_mode"),
        "status": task.get("status"),
        "payload": task.get("payload") if task.get("payload") is not None else "",
        "env_var_refs": task.get("env_var_refs") or [],
        "created_at": task.get("created_at"),
        "started_at": task.get("started_at"),
        "updated_at": task.get("updated_at"),
        "last_run_at": task.get("last_run_at"),
        "last_run_status": task.get("last_run_status"),
        "last_run_trigger": task.get("last_run_trigger"),
    }
    return _enrich_iso_date_fields(payload, _TASK_PUBLIC_DATE_KEYS)


class UpdateScheduledTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    task_id: str = Field(validation_alias=AliasChoices("task_id", "taskId"))
    name: str
    description: str
    cron_expression: str
    execution_mode: AgentExecutionMode = Field(
        ...,
        description="Must be ``script`` (only supported mode for now; more may be added later).",
    )
    payload: str = Field(default="", description="Script body.")
    env_var_keys: list[str] | None = None
    started_at: str | None = None
    enabled: bool

    @field_validator("cron_expression", mode="before")
    @classmethod
    def cron_expression_no_placeholders(cls, value: Any) -> Any:
        if not isinstance(value, str):
            raise ValueError("cron_expression must be a string")
        if _cron_string_is_llm_sentinel(value):
            raise ValueError(
                "cron_expression must be a valid 5-field cron string. "
                "Do not use the text 'None', 'null', or an empty string."
            )
        return value


@tool
async def create_scheduled_task(
    name: str,
    description: str,
    cron_expression: str,
    execution_mode: AgentExecutionMode,
    payload: str = "",
    env_var_keys: list[str] | None = None,
    started_at: str | None = None,
) -> dict:
    """Create a scheduled script task with cron timing and optional injected env vars."""
    core, error = _validate_task_core(
        name,
        description,
        cron_expression,
        execution_mode,
        payload,
        env_var_keys,
    )
    if error:
        return {"success": False, "message": error}

    task = await get_task_runtime().create_task(
        name=core["name"],
        description=core["description"],
        cron_expression=core["cron_expression"],
        execution_mode=core["execution_mode"],
        payload=core["payload"],
        env_var_refs=core["env_var_refs"],
        started_at=started_at,
    )
    return {"success": True, "task": _task_public_dict(task), "message": "Task created."}


@tool
async def read_scheduled_tasks(
    task_id: str | None = None,
    status: Literal["enabled", "disabled", "running", "all"] = "all",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Read one scheduled task by id or list scheduled tasks with optional status filtering."""
    runtime = get_task_runtime()
    if task_id is not None and str(task_id).strip():
        task = await runtime.get_task(str(task_id).strip())
        if task is None:
            return {"success": False, "message": "Task not found"}
        return {"success": True, "task": _task_public_dict(task)}

    if page < 1 or page_size < 1 or page_size > 200:
        return {"success": False, "message": "page must be >= 1; page_size between 1 and 200"}
    items, total = await runtime.list_tasks(
        status=None if status == "all" else status,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "items": [_task_public_dict(task) for task in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@tool(args_schema=UpdateScheduledTaskInput)
async def update_scheduled_task(
    task_id: str,
    name: str,
    description: str,
    cron_expression: str,
    execution_mode: AgentExecutionMode,
    payload: str = "",
    env_var_keys: list[str] | None = None,
    started_at: str | None = None,
    *,
    enabled: bool,
) -> dict:
    """Replace a scheduled task's definition and set whether it is enabled."""
    try:
        data = UpdateScheduledTaskInput.model_validate(
            {
                "task_id": task_id,
                "name": name,
                "description": description,
                "cron_expression": cron_expression,
                "execution_mode": execution_mode,
                "payload": payload,
                "env_var_keys": env_var_keys,
                "started_at": started_at,
                "enabled": enabled,
            }
        )
    except ValidationError as exc:
        return {"success": False, "message": f"Invalid arguments: {exc}"}

    core, error = _validate_task_core(
        data.name,
        data.description,
        data.cron_expression,
        data.execution_mode,
        data.payload,
        data.env_var_keys,
    )
    if error:
        return {"success": False, "message": error}

    runtime = get_task_runtime()
    task = await runtime.update_task(
        data.task_id,
        {
            "name": core["name"],
            "description": core["description"],
            "cron_expression": core["cron_expression"],
            "execution_mode": core["execution_mode"],
            "payload": core["payload"],
            "env_var_refs": core["env_var_refs"],
            "started_at": data.started_at,
        },
    )
    if task is None:
        return {"success": False, "message": "Task not found"}
    task = await runtime.set_task_enabled(data.task_id, data.enabled)
    if task is None:
        return {"success": False, "message": "Task not found"}
    return {"success": True, "task": _task_public_dict(task), "message": "Task updated."}


@tool
async def delete_scheduled_task(task_id: str) -> dict:
    """Delete a scheduled task and cancel any active runs that belong to it."""
    ok = await get_task_runtime().delete_task(task_id.strip())
    if not ok:
        return {"success": False, "message": "Task not found"}
    return {"success": True, "id": task_id.strip(), "message": "Task deleted."}


@tool
async def read_scheduled_task_run_logs(
    task_id: str,
    run_id: str | None = None,
    log_page: int = 1,
    log_page_size: int = 50,
) -> dict:
    """Read recent runs for a task and page through log entries for one selected run."""
    runtime = get_task_runtime()
    task = await runtime.get_task(task_id.strip())
    if task is None:
        return {"success": False, "message": "Task not found"}
    if log_page < 1 or log_page_size < 1 or log_page_size > 200:
        return {"success": False, "message": "log_page must be >= 1; log_page_size between 1 and 200"}

    runs = await runtime.list_runs_for_task(task_id.strip())
    if not runs:
        return {
            "success": True,
            "task_id": task_id.strip(),
            "message": "No runs for this task yet.",
            "recent_runs": [],
            "run": None,
            "logs": [],
            "log_total": 0,
            "log_page": log_page,
            "log_page_size": log_page_size,
        }

    recent_runs = [
        _enrich_iso_date_fields(
            _run_dict_to_execution_response(run).model_dump(mode="json"),
            _RUN_SUMMARY_DATE_KEYS,
        )
        for run in runs[:10]
    ]

    if run_id is not None and str(run_id).strip():
        normalized_run_id = str(run_id).strip()
        run = next((item for item in runs if item.get("id") == normalized_run_id), None)
        if run is None:
            return {"success": False, "message": "Run not found for this task"}
    else:
        run = runs[0]

    summary = _enrich_iso_date_fields(
        _run_dict_to_execution_response(run).model_dump(mode="json"),
        _RUN_SUMMARY_DATE_KEYS,
    )
    logs = run.get("logs") or []
    start = (log_page - 1) * log_page_size
    page_items = logs[start : start + log_page_size]
    log_payload: list[dict[str, Any]] = []
    for idx, raw in enumerate(page_items):
        if not isinstance(raw, dict):
            continue
        entry = _coerce_log_entry(run["id"], raw, start + idx).model_dump(mode="json")
        cal = _iso_like_to_calendar_date(entry.get("timestamp"))
        if cal is not None:
            entry["timestamp_date"] = cal
        log_payload.append(entry)

    return {
        "success": True,
        "task_id": task_id.strip(),
        "recent_runs": recent_runs,
        "run": summary,
        "logs": log_payload,
        "log_total": len(logs),
        "log_page": log_page,
        "log_page_size": log_page_size,
    }


@tool
async def run_scheduled_task(task_id: str, override_prompt: str | None = None) -> dict:
    """Trigger a scheduled task immediately, optionally with an override prompt."""
    runtime = get_task_runtime()
    task = await runtime.get_task(task_id.strip())
    if task is None:
        return {"success": False, "message": "Task not found"}

    op = (override_prompt or "").strip()
    trigger = LastRunTrigger.agent.value if op else LastRunTrigger.manual.value
    run = await runtime.trigger_task(
        task_id.strip(),
        trigger=trigger,
        override_prompt=op or None,
    )
    if run is None:
        return {"success": False, "message": "Task not found"}
    return {
        "success": True,
        "task_id": task_id.strip(),
        "run_id": run["id"],
        "run_status": run.get("status"),
        "message": run.get("message"),
    }
