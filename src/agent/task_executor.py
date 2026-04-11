"""Task executor — runs Python scripts defined in task payloads.

Executes the ``payload`` field of **script**-mode tasks as Python code in a
subprocess, captures stdout / stderr, and writes results to ``runs/<run_id>.json``.

Standalone usage::

    python src/agent/task_executor.py <task_id>          # run once
    python src/agent/task_executor.py <task_id> --trigger cron

Programmatic usage::

    from agent.task_executor import TaskExecutor

    executor = TaskExecutor()
    run = executor.execute(task_dict)            # returns the finished run dict
    run = executor.execute(task_dict, trigger="cron")
"""
from __future__ import annotations

import json
import logging
import os
import platform as platform_mod
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("task_executor")

CRON_DIR = Path("./cron")
RUNS_DIR = Path("./runs")
ENV_VARS_FILE = Path("./cron/env_vars.json")
DB_PATH = Path("./agent.db")

DEFAULT_TIMEOUT = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_entry(
    run_id: str,
    step_index: int,
    log_type: str,
    *,
    duration_ms: int = 0,
    status: str = "success",
    content: str | None = None,
    metadata: dict | None = None,
    timestamp: str | None = None,
) -> dict:
    """Build one API ``LogEntry``-shaped dict (frontend contract)."""
    return {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "step_index": step_index,
        "log_type": log_type,
        "duration_ms": duration_ms,
        "status": status,
        "timestamp": timestamp or _now_iso(),
        "content": content,
        "metadata": metadata or {},
        "input_params": None,
        "output": None,
        "tool_name": None,
    }


def _legacy_log_to_log_entry(run_id: str, seq: int, entry: dict) -> dict:
    """Convert legacy ``{level, message, ts}`` rows to LogEntry shape."""
    level = entry.get("level") or "stdout"
    message = entry.get("message") or ""
    ts = entry.get("ts") or _now_iso()
    lt_map = {
        "stdout": "script_stdout",
        "stderr": "script_stderr",
        "info": "script_stdout",
        "error": "script_stderr",
    }
    log_type = lt_map.get(level, "script_stdout")
    st = "failed" if level == "error" else "success"
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:log:{seq}")),
        "run_id": run_id,
        "step_index": seq + 1,
        "log_type": log_type,
        "duration_ms": 0,
        "status": st,
        "timestamp": ts,
        "content": message,
        "metadata": {},
        "input_params": None,
        "output": None,
        "tool_name": None,
    }


def _level_message_for_db_row(entry: dict) -> tuple[str, str]:
    """Derive legacy ``level`` / ``message`` columns from a LogEntry dict."""
    lt = entry.get("log_type") or ""
    if lt == "script_stdout":
        return "stdout", entry.get("content") or ""
    if lt == "script_stderr":
        return "stderr", entry.get("content") or ""
    return "info", entry.get("content") or ""


def _normalize_log_dict(run_id: str, seq: int, entry: dict) -> dict:
    if entry.get("log_type"):
        return entry
    return _legacy_log_to_log_entry(run_id, seq, entry)


def read_task(task_id: str) -> dict | None:
    p = CRON_DIR / f"{task_id}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text("utf-8"))


def write_task(task: dict) -> None:
    CRON_DIR.mkdir(exist_ok=True)
    p = CRON_DIR / f"{task['id']}.json"
    p.write_text(json.dumps(task, ensure_ascii=False, indent=2), "utf-8")


def read_run(run_id: str) -> dict | None:
    p = RUNS_DIR / f"{run_id}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text("utf-8"))


def write_run(run: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{run['id']}.json"
    p.write_text(json.dumps(run, ensure_ascii=False, indent=2), "utf-8")


def delete_run_json_files_for_task(task_id: str) -> None:
    """Remove ``runs/<run_id>.json`` for each run row with ``task_id`` (call before deleting DB rows)."""
    try:
        _init_db()
    except Exception as exc:
        log.warning("DB init failed, skipping run file cleanup: %s", exc)
        return
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        try:
            cur = conn.execute(
                "SELECT id FROM task_runs WHERE task_id = ?",
                (task_id,),
            )
            run_ids = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        log.warning("Failed to list runs for task %s: %s", task_id, exc)
        return
    for rid in run_ids:
        p = RUNS_DIR / f"{rid}.json"
        try:
            if p.is_file():
                p.unlink()
        except OSError as exc:
            log.warning("Failed to remove %s: %s", p, exc)


def read_env_vars() -> dict[str, str]:
    if not ENV_VARS_FILE.is_file():
        return {}
    try:
        return json.loads(ENV_VARS_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _build_env(task: dict) -> dict[str, str]:
    """Merge OS env → global env vars → task-level env_var_refs."""
    env = dict(os.environ)
    global_vars = read_env_vars()
    env.update(global_vars)
    for ref in task.get("env_var_refs") or []:
        if not isinstance(ref, dict):
            continue
        key = (ref.get("key") or "").strip()
        if not key:
            continue
        if key in global_vars:
            env[key] = global_vars[key]
            continue
        secret_ref = (ref.get("secret_ref") or "").strip()
        if secret_ref and secret_ref in global_vars:
            env[key] = global_vars[secret_ref]
    return env


# ---------------------------------------------------------------------------
# DB persistence (sync sqlite3 — no ORM / no FastAPI dependency)
# ---------------------------------------------------------------------------

_db_initialized = False


def ensure_task_run_sqlite_schema() -> None:
    """Public entry to ensure ``agent.db`` task tables + ``entry_json`` column exist."""
    _init_db()


def _init_db() -> None:
    global _db_initialized
    if _db_initialized:
        return
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_runs (
                id          VARCHAR(36)  PRIMARY KEY,
                task_id     VARCHAR(36)  NOT NULL,
                status      VARCHAR(20)  NOT NULL DEFAULT 'pending',
                "trigger"   VARCHAR(20)  NOT NULL DEFAULT 'manual',
                override_prompt TEXT,
                started_at  DATETIME     NOT NULL,
                finished_at DATETIME,
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_task_runs_task_id
                ON task_runs(task_id);
            CREATE INDEX IF NOT EXISTS ix_task_runs_task_started
                ON task_runs(task_id, started_at);

            CREATE TABLE IF NOT EXISTS task_run_logs (
                id      INTEGER      PRIMARY KEY AUTOINCREMENT,
                run_id  VARCHAR(36)  NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
                seq     INTEGER      NOT NULL,
                level   VARCHAR(10)  NOT NULL DEFAULT 'stdout',
                message TEXT         NOT NULL,
                ts      DATETIME
            );
            CREATE INDEX IF NOT EXISTS ix_task_run_logs_run_seq
                ON task_run_logs(run_id, seq);
        """)
        try:
            conn.execute("ALTER TABLE task_run_logs ADD COLUMN entry_json TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise
        try:
            conn.execute(
                "ALTER TABLE routine ADD COLUMN color TEXT NOT NULL DEFAULT '#3b82f6'"
            )
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise
        conn.commit()
        _db_initialized = True
    finally:
        conn.close()


def persist_run_to_db(run: dict) -> None:
    """Upsert run record + replace all log lines in SQLite (sync)."""
    try:
        _init_db()
    except Exception as exc:
        log.warning("DB init failed: %s", exc)
        return
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """INSERT INTO task_runs
                   (id, task_id, status, "trigger", override_prompt,
                    started_at, finished_at, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   status=excluded.status,
                   "trigger"=excluded."trigger",
                   override_prompt=excluded.override_prompt,
                   started_at=excluded.started_at,
                   finished_at=excluded.finished_at,
                   error_message=excluded.error_message
            """,
            (
                run["id"],
                run["task_id"],
                run["status"],
                run.get("trigger", "manual"),
                run.get("override_prompt"),
                run.get("started_at"),
                run.get("finished_at"),
                run.get("message"),
            ),
        )
        conn.execute("DELETE FROM task_run_logs WHERE run_id = ?", (run["id"],))
        logs = run.get("logs") or []
        for seq, entry in enumerate(logs):
            if not isinstance(entry, dict):
                continue
            full = _normalize_log_dict(run["id"], seq, entry)
            entry_json = json.dumps(full, ensure_ascii=False)
            level, message = _level_message_for_db_row(full)
            conn.execute(
                """INSERT INTO task_run_logs (run_id, seq, level, message, ts, entry_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run["id"],
                    seq,
                    level,
                    message,
                    full.get("timestamp"),
                    entry_json,
                ),
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.warning("Failed to persist run %s to DB: %s", run.get("id"), exc)


# ---------------------------------------------------------------------------
# Task file helpers
# ---------------------------------------------------------------------------

def _update_task_after_run(run: dict) -> None:
    """Sync last_run_* on the parent task."""
    task = read_task(run["task_id"])
    if not task:
        return
    finished = run.get("finished_at") or _now_iso()
    task["last_run_at"] = finished
    raw_status = run.get("status", "")
    status_map = {"succeeded": "success", "failed": "failed", "cancelled": "cancelled"}
    task["last_run_status"] = status_map.get(raw_status, raw_status)
    task["last_run_trigger"] = run.get("trigger", "manual")
    if task.get("status") == "running":
        task["status"] = "enabled"
    task["updated_at"] = finished
    write_task(task)


class TaskExecutor:
    """Execute a task's Python payload in a subprocess.

    Subprocess work runs under a concurrency slot so many tasks cannot exhaust
    the machine; :meth:`execute_background` runs that work in a **daemon thread**
    so callers (e.g. cron watcher main loop) return immediately without waiting
    for the child process.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_concurrent: int | None = 8):
        self.timeout = timeout
        self._max_concurrent = max_concurrent
        self._sem: threading.BoundedSemaphore | None = None
        if max_concurrent is not None and max_concurrent > 0:
            self._sem = threading.BoundedSemaphore(max_concurrent)

    @contextmanager
    def _concurrency_slot(self):
        if self._sem is None:
            yield
            return
        self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()

    def execute(
        self,
        task: dict,
        trigger: str = "manual",
        override_prompt: str | None = None,
    ) -> dict:
        """Create a run record, execute the payload in this thread, return finished run.

        Blocks until the subprocess exits or times out (for CLI / synchronous use).
        """
        run_id = str(uuid.uuid4())
        now = _now_iso()

        run: dict = {
            "id": run_id,
            "task_id": task["id"],
            "status": "running",
            "trigger": trigger,
            "override_prompt": override_prompt,
            "started_at": now,
            "finished_at": None,
            "message": None,
            "logs": [],
        }

        task["status"] = "running"
        task["updated_at"] = now
        task["last_run_at"] = now
        task["last_run_trigger"] = trigger
        write_task(task)
        write_run(run)
        persist_run_to_db(run)

        log.info("Run %s started for task %s [%s]", run_id, task["id"], task.get("name"))

        mode = task.get("execution_mode", "prompt")
        payload = task.get("payload", "")

        if mode != "script" or not payload.strip():
            run["status"] = "failed"
            run["finished_at"] = _now_iso()
            run["message"] = (
                "Nothing to execute: execution_mode is not 'script' or payload is empty."
            )
            inj: list[str] = []
            gv = read_env_vars()
            inj.extend(gv.keys())
            for ref in task.get("env_var_refs") or []:
                k = ref.get("key")
                if k:
                    inj.append(k)
            run["logs"].append(
                _log_entry(
                    run["id"],
                    1,
                    "script_start",
                    metadata={
                        "platform": platform_mod.platform(),
                        "python_version": sys.version.split()[0],
                        "injected_env_keys": sorted(set(inj)),
                    },
                )
            )
            run["logs"].append(
                _log_entry(
                    run["id"],
                    2,
                    "script_end",
                    duration_ms=0,
                    status="failed",
                    content=run["message"],
                    metadata={},
                )
            )
            write_run(run)
            persist_run_to_db(run)
            _update_task_after_run(run)
            log.warning("Run %s skipped: %s", run_id, run["message"])
            return run

        try:
            with self._concurrency_slot():
                self._run_python(run, payload, task)
        except Exception as exc:
            run["status"] = "failed"
            run["finished_at"] = _now_iso()
            run["message"] = str(exc)
            run["logs"].append(
                _log_entry(
                    run["id"],
                    len(run["logs"]) + 1,
                    "script_end",
                    duration_ms=0,
                    status="failed",
                    content=f"Executor error: {exc}",
                    metadata={},
                )
            )
            log.exception("Run %s failed with exception", run_id)

        write_run(run)
        persist_run_to_db(run)
        _update_task_after_run(run)
        log.info("Run %s finished: %s", run_id, run["status"])
        return run

    def execute_background(
        self,
        task: dict,
        trigger: str = "manual",
        override_prompt: str | None = None,
    ) -> tuple[dict, threading.Thread | None]:
        """Persist run as *running*, start a **daemon** thread for subprocess; return immediately.

        Does not block the caller on ``subprocess``/user code. The thread holds a
        concurrency slot only while the child process runs. Returns ``(run, thread)``
        where ``thread`` is ``None`` if execution finished synchronously (invalid payload).
        """
        run_id = str(uuid.uuid4())
        now = _now_iso()

        run: dict = {
            "id": run_id,
            "task_id": task["id"],
            "status": "running",
            "trigger": trigger,
            "override_prompt": override_prompt,
            "started_at": now,
            "finished_at": None,
            "message": None,
            "logs": [],
        }

        task_copy = dict(task)
        task["status"] = "running"
        task["updated_at"] = now
        task["last_run_at"] = now
        task["last_run_trigger"] = trigger
        write_task(task)
        write_run(run)
        persist_run_to_db(run)

        log.info(
            "Run %s scheduled (background) for task %s [%s]",
            run_id,
            task["id"],
            task.get("name"),
        )

        mode = task.get("execution_mode", "prompt")
        payload = task.get("payload", "")

        if mode != "script" or not payload.strip():
            run["status"] = "failed"
            run["finished_at"] = _now_iso()
            run["message"] = (
                "Nothing to execute: execution_mode is not 'script' or payload is empty."
            )
            inj_b: list[str] = []
            gv_b = read_env_vars()
            inj_b.extend(gv_b.keys())
            for ref in task.get("env_var_refs") or []:
                k = ref.get("key")
                if k:
                    inj_b.append(k)
            run["logs"].append(
                _log_entry(
                    run["id"],
                    1,
                    "script_start",
                    metadata={
                        "platform": platform_mod.platform(),
                        "python_version": sys.version.split()[0],
                        "injected_env_keys": sorted(set(inj_b)),
                    },
                )
            )
            run["logs"].append(
                _log_entry(
                    run["id"],
                    2,
                    "script_end",
                    duration_ms=0,
                    status="failed",
                    content=run["message"],
                    metadata={},
                )
            )
            write_run(run)
            persist_run_to_db(run)
            _update_task_after_run(run)
            log.warning("Run %s skipped: %s", run_id, run["message"])
            return run, None

        def worker() -> None:
            try:
                with self._concurrency_slot():
                    self._run_python(run, payload, task_copy)
            except Exception as exc:
                run["status"] = "failed"
                run["finished_at"] = _now_iso()
                run["message"] = str(exc)
                run["logs"].append(
                    _log_entry(
                        run["id"],
                        len(run["logs"]) + 1,
                        "script_end",
                        duration_ms=0,
                        status="failed",
                        content=f"Executor error: {exc}",
                        metadata={},
                    )
                )
                log.exception("Run %s failed with exception", run_id)
            write_run(run)
            persist_run_to_db(run)
            _update_task_after_run(run)
            log.info("Run %s finished: %s", run_id, run["status"])

        t = threading.Thread(
            target=worker,
            name=f"task-exec-{run_id[:8]}",
            daemon=True,
        )
        t.start()
        return run, t

    def _run_python(self, run: dict, code: str, task: dict) -> None:
        """Write code to a temp file, execute via subprocess, capture output."""
        env = _build_env(task)

        inj_keys: list[str] = []
        gv = read_env_vars()
        inj_keys.extend(gv.keys())
        for ref in task.get("env_var_refs") or []:
            k = ref.get("key")
            if k:
                inj_keys.append(k)
        inj_keys = sorted(set(inj_keys))

        step = 1

        def append_entry(entry: dict) -> None:
            nonlocal step
            run["logs"].append(entry)
            step = entry["step_index"] + 1

        append_entry(
            _log_entry(
                run["id"],
                step,
                "script_start",
                metadata={
                    "platform": platform_mod.platform(),
                    "python_version": sys.version.split()[0],
                    "injected_env_keys": inj_keys,
                },
            )
        )

        t0 = time.perf_counter()

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix=f"task_{task['id'][:8]}_",
            dir="./",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(code)
            script_path = tmp.name

        popen_kw: dict = {
            "capture_output": True,
            "text": True,
            "timeout": self.timeout,
            "cwd": "./",
            "env": env,
        }
        if os.name != "nt":
            popen_kw["start_new_session"] = True

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                **popen_kw,
            )

            chunk_out = 0
            if result.stdout:
                for line in result.stdout.splitlines():
                    append_entry(
                        _log_entry(
                            run["id"],
                            step,
                            "script_stdout",
                            content=line,
                            duration_ms=0,
                            status="success",
                            metadata={"chunk_index": chunk_out},
                        )
                    )
                    chunk_out += 1

            chunk_err = 0
            if result.stderr:
                for line in result.stderr.splitlines():
                    append_entry(
                        _log_entry(
                            run["id"],
                            step,
                            "script_stderr",
                            content=line,
                            duration_ms=0,
                            status="success",
                            metadata={"chunk_index": chunk_err},
                        )
                    )
                    chunk_err += 1

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            ok = result.returncode == 0
            if not ok:
                run["message"] = f"Process exited with code {result.returncode}"

            append_entry(
                _log_entry(
                    run["id"],
                    step,
                    "script_end",
                    duration_ms=elapsed_ms,
                    status="success" if ok else "failed",
                    metadata={"exit_code": result.returncode},
                )
            )

            run["status"] = "succeeded" if ok else "failed"
            run["finished_at"] = _now_iso()

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            run["status"] = "failed"
            run["finished_at"] = _now_iso()
            run["message"] = f"Execution timed out after {self.timeout}s"
            append_entry(
                _log_entry(
                    run["id"],
                    step,
                    "script_end",
                    duration_ms=elapsed_ms,
                    status="failed",
                    content=run["message"],
                    metadata={},
                )
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Execute a task's Python payload")
    parser.add_argument("task_id", help="Task ID (filename without .json in cron/)")
    parser.add_argument("--trigger", default="manual", help="Trigger type (default: manual)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout in seconds")
    args = parser.parse_args()

    task = read_task(args.task_id)
    if not task:
        log.error("Task not found: %s", args.task_id)
        sys.exit(1)

    executor = TaskExecutor(timeout=args.timeout)
    run = executor.execute(task, trigger=args.trigger)

    print(json.dumps(run, ensure_ascii=False, indent=2))
    sys.exit(0 if run["status"] == "succeeded" else 1)


if __name__ == "__main__":
    main()
