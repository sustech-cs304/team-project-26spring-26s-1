"""Scheduled tasks CRUD — storage matches HTTP ``/api/tasks`` (``cron/<id>.json`` + ``agent.db`` runs)."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from pathlib import Path

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
from agent.api.task import (
    LastRunTrigger,
    _TASK_EXECUTOR_MAX_CONCURRENT,
    _TASK_EXECUTOR_TIMEOUT_S,
    _coerce_log_entry,
    _paginate,
    _run_dict_to_execution_response,
    _runs_for_task,
)
from agent.task_executor import TaskExecutor, delete_run_json_files_for_task

CRON_DIR = Path("./cron")
_MAX_TEXT = 1024

# Agent tool schema: only ``script`` today; extend this Literal when new modes exist.
AgentExecutionMode = Literal["script"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_like_to_calendar_date(value: Any) -> str | None:
    """ISO timestamps or unix seconds → ``YYYY-MM-DD`` for agent-facing tool payloads."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            from agent.services.calendar_time import unix_sec_to_local_ymdhms

            p = unix_sec_to_local_ymdhms(int(value))
            return f"{p['year']:04d}-{p['month']:02d}-{p['day']:02d}"
        except (ValueError, OSError, OverflowError):
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt.date().isoformat()
    except ValueError:
        return None


def _enrich_iso_date_fields(d: dict, keys: tuple[str, ...]) -> dict:
    out = dict(d)
    for k in keys:
        if k in out and out[k] is not None:
            cal = _iso_like_to_calendar_date(out[k])
            if cal is not None:
                out[f"{k}_date"] = cal
    return out


_TASK_PUBLIC_DATE_KEYS = ("created_at", "started_at", "updated_at", "last_run_at")
_RUN_SUMMARY_DATE_KEYS = ("started_at", "finished_at")


def _ensure_cron_dir() -> None:
    CRON_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s or "/" in s or "\\" in s or ".." in s:
        return ""
    return s


def _read_task(task_id: str) -> dict | None:
    tid = _normalize_id(task_id)
    if not tid:
        return None
    p = CRON_DIR / f"{tid}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_task(task: dict) -> None:
    _ensure_cron_dir()
    p = CRON_DIR / f"{task['id']}.json"
    p.write_text(json.dumps(task, ensure_ascii=False, indent=2), "utf-8")


def _delete_task_file(task_id: str) -> bool:
    tid = _normalize_id(task_id)
    if not tid:
        return False
    p = CRON_DIR / f"{tid}.json"
    if not p.is_file():
        return False
    p.unlink()
    return True


def _all_tasks() -> list[dict]:
    _ensure_cron_dir()
    out: list[dict] = []
    for p in sorted(CRON_DIR.glob("*.json")):
        if p.name == "env_vars.json":
            continue
        try:
            out.append(json.loads(p.read_text("utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _paginate(items: list, page: int, page_size: int) -> tuple[list, int]:
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def _delete_runs_for_task_sync(task_id: str) -> None:
    delete_run_json_files_for_task(task_id)
    path = str("./agent.db")
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.execute(
            "DELETE FROM task_run_logs WHERE run_id IN (SELECT id FROM task_runs WHERE task_id = ?)",
            (task_id,),
        )
        conn.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()


def _normalize_env_keys(keys: list[str] | None) -> tuple[list[dict] | None, str | None]:
    if keys is None:
        return None, None
    out: list[dict] = []
    for k in keys:
        try:
            out.append({"key": validate_env_var_key(k)})
        except ValueError:
            return None, f"Invalid env var key: {k!r}"
    return out, None


def _cron_string_is_llm_sentinel(s: str) -> bool:
    """True for empty string or the literal words None/null (models often send these instead of omitting the field)."""
    t = s.strip()
    if not t:
        return True
    return t.lower() in ("none", "null", "nil")


def _validate_task_core(
    name: str,
    description: str,
    cron_expression: str,
    execution_mode: AgentExecutionMode,
    payload: str,
    env_var_keys: list[str] | None,
) -> tuple[dict | None, str | None]:
    """Shared create/update body validation. Returns ``(core_fields, error_message)``."""
    if len(name) > _MAX_TEXT or len(description) > _MAX_TEXT:
        return None, f"name and description must be at most {_MAX_TEXT} characters"
    if _cron_string_is_llm_sentinel(cron_expression):
        return None, (
            "cron_expression must be a valid 5-field cron string, not the text 'None', 'null', or empty."
        )
    cron_expr, cerr = _normalize_cron_expression(cron_expression)
    if cerr:
        return None, cerr
    refs, emsg = _normalize_env_keys(env_var_keys)
    if emsg:
        return None, emsg
    env_refs = refs if refs is not None else []
    return {
        "name": name.strip(),
        "description": description.strip(),
        "cron_expression": cron_expr,
        "execution_mode": execution_mode,
        "payload": payload if payload is not None else "",
        "env_var_refs": env_refs,
    }, None


def _normalize_cron_expression(expr: str) -> tuple[str | None, str | None]:
    parts = expr.strip().split()
    if len(parts) != 5:
        return None, (
            f"cron must have exactly 5 fields (got {len(parts)}); "
            "order: minute hour day-of-month month day-of-week."
        )
    return " ".join(parts), None


def _cron_fields_public(cron_expression: str | None) -> dict | None:
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


def _task_public_dict(t: dict) -> dict:
    ce = t.get("cron_expression")
    base = {
        "id": t.get("id"),
        "name": t.get("name"),
        "description": t.get("description"),
        "cron_expression": ce,
        "cron_fields": _cron_fields_public(ce) if isinstance(ce, str) else None,
        "execution_mode": t.get("execution_mode"),
        "status": t.get("status"),
        "payload": t.get("payload") if t.get("payload") is not None else "",
        "env_var_refs": t.get("env_var_refs") or [],
        "created_at": t.get("created_at"),
        "started_at": t.get("started_at"),
        "updated_at": t.get("updated_at"),
        "last_run_at": t.get("last_run_at"),
        "last_run_status": t.get("last_run_status"),
        "last_run_trigger": t.get("last_run_trigger"),
    }
    return _enrich_iso_date_fields(base, _TASK_PUBLIC_DATE_KEYS)


class UpdateScheduledTaskInput(BaseModel):
    """Full replacement: same fields as creating a task, plus ``task_id`` and ``enabled``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    task_id: str = Field(validation_alias=AliasChoices("task_id", "taskId"))
    name: str
    description: str
    cron_expression: str
    execution_mode: AgentExecutionMode = Field(
        ...,
        description="Must be ``script`` (only supported mode for now; more may be added later).",
    )
    payload: str = Field(
        default="",
        description="Script body when execution_mode is script.",
    )
    env_var_keys: list[str] | None = Field(
        default=None,
        description="Env var key names to attach; same as create.",
    )
    started_at: str | None = Field(
        default=None,
        description="ISO start time if applicable; same as create.",
    )
    enabled: bool = Field(
        description="If true, task status is enabled; if false, disabled (create always starts enabled).",
    )

    @field_validator("cron_expression", mode="before")
    @classmethod
    def cron_expression_no_placeholders(cls, v: Any) -> Any:
        if not isinstance(v, str):
            raise ValueError("cron_expression must be a string")
        if _cron_string_is_llm_sentinel(v):
            raise ValueError(
                "cron_expression must be a valid 5-field cron string. "
                "Do not use the text 'None', 'null', or an empty string."
            )
        return v


@tool
def create_scheduled_task(
    name: str,
    description: str,
    cron_expression: str,
    execution_mode: AgentExecutionMode,
    payload: str = "",
    env_var_keys: list[str] | None = None,
    started_at: str | None = None,
) -> dict:
    """Create a task (``cron/*.json``). Pass ``execution_mode``; only ``script`` is valid today (extend later).

    ``cron_expression``: five whitespace-separated cron fields.
    """
    core, err = _validate_task_core(
        name, description, cron_expression, execution_mode, payload, env_var_keys
    )
    if err:
        return {"success": False, "message": err}

    task_id = str(uuid.uuid4())
    now = _now_iso()
    task = {
        "id": task_id,
        **core,
        "status": "enabled",
        "created_at": now,
        "started_at": started_at,
        "updated_at": now,
    }
    _write_task(task)
    return {"success": True, "task": _task_public_dict(task), "message": "Task created."}


@tool
def read_scheduled_tasks(
    task_id: str | None = None,
    status: Literal["enabled", "disabled", "running", "all"] = "all",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Read tasks: pass ``task_id`` for one task; omit it for a paginated list (``status``, ``page``, ``page_size``)."""
    if task_id is not None and str(task_id).strip():
        tid = _normalize_id(str(task_id))
        if not tid:
            return {"success": False, "message": "Invalid task_id"}
        t = _read_task(tid)
        if not t:
            return {"success": False, "message": "Task not found"}
        return {"success": True, "task": _task_public_dict(t)}

    if page < 1 or page_size < 1 or page_size > 200:
        return {"success": False, "message": "page must be >= 1; page_size between 1 and 200"}
    all_raw = _all_tasks()
    filtered = all_raw if status == "all" else [t for t in all_raw if t.get("status") == status]
    items, total = _paginate(filtered, page, page_size)
    return {
        "success": True,
        "items": [_task_public_dict(t) for t in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@tool(args_schema=UpdateScheduledTaskInput)
def update_scheduled_task(
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
    """Replace a task: ``task_id`` plus the same arguments as ``create_scheduled_task``, then ``enabled``.

    ``execution_mode`` must be ``script`` for now. Read the current task first, then submit the full payload.
    """
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
    except ValidationError as e:
        return {"success": False, "message": f"Invalid arguments: {e}"}

    tid = _normalize_id(data.task_id)
    if not tid:
        return {"success": False, "message": "Invalid task_id"}

    old = _read_task(tid)
    if not old:
        return {"success": False, "message": "Task not found"}

    core, err = _validate_task_core(
        data.name,
        data.description,
        data.cron_expression,
        data.execution_mode,
        data.payload,
        data.env_var_keys,
    )
    if err:
        return {"success": False, "message": err}

    now = _now_iso()
    status = "enabled" if data.enabled else "disabled"

    task = {
        "id": tid,
        **core,
        "status": status,
        "created_at": old.get("created_at"),
        "started_at": data.started_at,
        "updated_at": now,
        "last_run_at": old.get("last_run_at"),
        "last_run_status": old.get("last_run_status"),
        "last_run_trigger": old.get("last_run_trigger"),
    }
    _write_task(task)
    return {"success": True, "task": _task_public_dict(task), "message": "Task updated."}


@tool
def delete_scheduled_task(task_id: str) -> dict:
    """Delete a task and its run rows in ``agent.db``."""
    tid = _normalize_id(task_id)
    if not tid:
        return {"success": False, "message": "Invalid task_id"}
    if not _delete_task_file(tid):
        return {"success": False, "message": "Task not found"}
    try:
        _delete_runs_for_task_sync(tid)
    except Exception as e:
        return {"success": False, "message": f"Removed task file but failed to clean DB runs: {e}"}
    return {"success": True, "id": tid, "message": "Task deleted."}


def _run_async(coro):
    return asyncio.run(coro)


@tool
def read_scheduled_task_run_logs(
    task_id: str,
    run_id: str | None = None,
    log_page: int = 1,
    log_page_size: int = 50,
) -> dict:
    """Read run history / logs for a task (same data as ``GET /tasks/{task_id}/runs`` and ``GET /runs/{run_id}/logs``).

    Returns ``recent_runs`` (up to 10 summaries, newest first). Omit ``run_id`` to load the **latest** run's log page;
    pass a ``run_id`` from ``recent_runs`` to inspect an older run. Log lines use ``log_page`` / ``log_page_size``.
    """
    tid = _normalize_id(task_id)
    if not tid:
        return {"success": False, "message": "Invalid task_id"}
    if not _read_task(tid):
        return {"success": False, "message": "Task not found"}
    if log_page < 1 or log_page_size < 1 or log_page_size > 200:
        return {"success": False, "message": "log_page must be >= 1; log_page_size between 1 and 200"}

    all_runs = _run_async(_runs_for_task(tid))
    if not all_runs:
        return {
            "success": True,
            "task_id": tid,
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
            _run_dict_to_execution_response(r).model_dump(mode="json"),
            _RUN_SUMMARY_DATE_KEYS,
        )
        for r in all_runs[:10]
    ]

    if run_id is not None and str(run_id).strip():
        rid = _normalize_id(str(run_id))
        if not rid:
            return {"success": False, "message": "Invalid run_id"}
        raw = next((r for r in all_runs if r.get("id") == rid), None)
        if not raw:
            return {"success": False, "message": "Run not found for this task"}
    else:
        raw = all_runs[0]

    summary = _enrich_iso_date_fields(
        _run_dict_to_execution_response(raw).model_dump(mode="json"),
        _RUN_SUMMARY_DATE_KEYS,
    )
    all_logs: list = raw.get("logs") or []
    page_items, _ = _paginate(all_logs, log_page, log_page_size)
    start = (log_page - 1) * log_page_size
    rid = raw["id"]
    log_payload: list[dict] = []
    for idx, row in enumerate(page_items):
        if not isinstance(row, dict):
            continue
        try:
            entry = _coerce_log_entry(rid, row, start + idx).model_dump(mode="json")
        except Exception:
            continue
        cal = _iso_like_to_calendar_date(entry.get("timestamp"))
        if cal is not None:
            entry["timestamp_date"] = cal
        log_payload.append(entry)

    return {
        "success": True,
        "task_id": tid,
        "recent_runs": recent_runs,
        "run": summary,
        "logs": log_payload,
        "log_total": len(all_logs),
        "log_page": log_page,
        "log_page_size": log_page_size,
    }


@tool
def run_scheduled_task(task_id: str, override_prompt: str | None = None) -> dict:
    """Start a task run in the background (same behavior as ``POST /tasks/{task_id}/trigger``).

    Non-empty ``override_prompt`` uses the **agent** trigger; otherwise **manual**. Execution is asynchronous.
    """
    tid = _normalize_id(task_id)
    if not tid:
        return {"success": False, "message": "Invalid task_id"}
    t = _read_task(tid)
    if not t:
        return {"success": False, "message": "Task not found"}

    op = (override_prompt or "").strip()
    if op:
        trig = LastRunTrigger.agent.value
        ovp: str | None = op
    else:
        trig = LastRunTrigger.manual.value
        ovp = None

    task_copy = dict(t)
    if not task_copy.get("started_at"):
        task_copy["started_at"] = _now_iso()

    executor = TaskExecutor(
        timeout=_TASK_EXECUTOR_TIMEOUT_S,
        max_concurrent=_TASK_EXECUTOR_MAX_CONCURRENT,
    )

    async def _trigger() -> tuple[dict, Any]:
        return await asyncio.to_thread(
            executor.execute_background,
            task_copy,
            trig,
            ovp,
        )

    run, _thread = _run_async(_trigger())
    return {
        "success": True,
        "task_id": tid,
        "run_id": run["id"],
        "run_status": run.get("status"),
        "message": run.get("message"),
    }
