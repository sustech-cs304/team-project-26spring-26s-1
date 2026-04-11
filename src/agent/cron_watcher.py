"""Cron directory watcher — monitors ``cron/`` for task changes and triggers execution.

Periodically checks ``cron/`` directory for file changes. When a task JSON is
loaded, the next cron fire time (``next_run_at``, UTC minute boundary) is
computed. Each poll compares ``now`` to ``next_run_at``; when due, the task is
dispatched once and ``next_run_at`` advances to the following matching minute.
Cold load initialises ``next_run_at`` from the **next** eligible minute (never
the current minute if ``now`` is already past ``:00``), so dev reload / restart
does not immediately re-fire the same wall-clock minute.

Usage::

    python src/agent/cron_watcher.py                     # default: poll every 60s
    python src/agent/cron_watcher.py --interval 10       # poll every 10s
    python src/agent/cron_watcher.py --once               # single check then exit

Architecture::

    cron/
      ├── <task_id>.json   ← task definitions (with cron_expression & payload)
      └── env_vars.json    ← global env vars
    runs/
      └── <run_id>.json    ← execution results (written by TaskExecutor)
"""
from __future__ import annotations

import importlib.util
import json
import logging
import signal
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("cron_watcher")

CRON_DIR = Path("./cron")


def _load_task_executor_module():
    """Load ``task_executor.py`` without importing ``agent`` package (avoids ``agent/__init__.py``)."""
    name = "agent._task_executor_standalone"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent / "task_executor.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load task executor from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class CronMatcher:
    """Evaluate a standard 5-field cron expression against a datetime.

    Supports: ``*``, specific values (``5``), lists (``1,15``),
    ranges (``1-5``), and steps (``*/5``, ``1-10/2``).
    Day-of-week: 0 = Monday … 6 = Sunday (Python convention).
    """

    __slots__ = ("_fields",)

    def __init__(self, expression: str):
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression (need 5 fields): {expression!r}")
        ranges = [
            (0, 59),   # minute
            (0, 23),   # hour
            (1, 31),   # day of month
            (1, 12),   # month
            (0, 6),    # day of week (0=Mon)
        ]
        self._fields: list[set[int]] = [
            self._parse_field(p, lo, hi) for p, (lo, hi) in zip(parts, ranges)
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

    def matches(self, dt: datetime) -> bool:
        minute = dt.minute
        hour = dt.hour
        dom = dt.day
        month = dt.month
        dow = dt.weekday()  # 0=Mon
        return (
            minute in self._fields[0]
            and hour in self._fields[1]
            and dom in self._fields[2]
            and month in self._fields[3]
            and dow in self._fields[4]
        )


_MAX_NEXT_SCAN_MINUTES = 366 * 24 * 60


def _utc_minute_start(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    return d.replace(second=0, microsecond=0)


def initial_next_run_at(matcher: CronMatcher, now: datetime) -> datetime | None:
    """First matching UTC minute for a **cold** ``next_run_at`` (process / registry just loaded).

    If ``now`` is already past the current minute's ``:00``, search from the **next whole minute**
    onward so hot reload / restart does not treat the same minute that already ran in the
    previous process as due again.

    If ``now`` is exactly on some minute's ``:00.000000``, that minute may still be used as the first slot.
    """
    t = _utc_minute_start(now)
    if now > t:
        t += timedelta(minutes=1)
    for _ in range(_MAX_NEXT_SCAN_MINUTES):
        if matcher.matches(t):
            return t
        t += timedelta(minutes=1)
    log.error("initial_next_run_at: no cron match in one year (expression bug?)")
    return None


def next_run_at_after(matcher: CronMatcher, after_minute: datetime) -> datetime | None:
    """First matching minute **strictly after** ``after_minute`` (which should be UTC minute start)."""
    t = _utc_minute_start(after_minute) + timedelta(minutes=1)
    for _ in range(_MAX_NEXT_SCAN_MINUTES):
        if matcher.matches(t):
            return t
        t += timedelta(minutes=1)
    log.error("next_run_at_after: no cron match in one year (expression bug?)")
    return None


class _TaskEntry:
    """In-memory cached task with its compiled cron matcher and scheduled next fire."""

    __slots__ = ("task", "mtime", "matcher", "next_run_at")

    def __init__(self, task: dict, mtime: float):
        self.task = task
        self.mtime = mtime
        self.matcher: CronMatcher | None = None
        self.next_run_at: datetime | None = None
        cron_expr = task.get("cron_expression", "").strip()
        if cron_expr:
            try:
                self.matcher = CronMatcher(cron_expr)
            except ValueError as e:
                log.warning("Task %s has invalid cron expression: %s", task.get("id"), e)


class CronWatcher:
    """Watch ``cron/`` directory, evaluate schedules, dispatch to executor."""

    def __init__(self, max_workers: int = 4, timeout: int = 300):
        self._registry: dict[str, _TaskEntry] = {}
        self._running_threads: dict[str, threading.Thread] = {}
        self._max_workers = max_workers
        self._timeout = timeout
        self._stop = False
        self._wake = threading.Event()

    def reload_tasks(self) -> None:
        """Scan ``cron/`` and update registry for new / modified / deleted tasks."""
        if not CRON_DIR.is_dir():
            if self._registry:
                log.info("cron/ directory gone — clearing %d cached tasks", len(self._registry))
                self._registry.clear()
            return

        on_disk: set[str] = set()
        for p in CRON_DIR.glob("*.json"):
            if p.name == "env_vars.json":
                continue
            task_id = p.stem
            on_disk.add(task_id)
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue

            existing = self._registry.get(task_id)
            # Skip disk read only when mtime unchanged; avoids rejecting reload on odd time ordering like ``>=`` would
            if existing and existing.mtime == mtime:
                continue

            try:
                data = json.loads(p.read_text("utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Failed to read %s: %s", p, exc)
                continue

            self._registry[task_id] = _TaskEntry(data, mtime)
            action = "reloaded" if existing else "loaded"
            log.info("Task %s (%s) %s", task_id, data.get("name", "?"), action)

        removed = set(self._registry) - on_disk
        for tid in removed:
            self._registry.pop(tid, None)
            log.info("Task %s removed (file deleted)", tid)

    def check_and_dispatch(self) -> int:
        """If ``now >= next_run_at``, fire once and advance ``next_run_at`` to the next matching minute.

        Returns the number of tasks dispatched.
        """
        now = datetime.now(timezone.utc)
        dispatched = 0

        for task_id, entry in list(self._registry.items()):
            task = entry.task

            if task.get("status") not in ("enabled",):
                continue
            if entry.matcher is None:
                continue
            if task.get("execution_mode") != "script":
                continue

            if entry.next_run_at is None:
                entry.next_run_at = initial_next_run_at(entry.matcher, now)
                if entry.next_run_at is None:
                    continue

            if now < entry.next_run_at:
                continue

            prev = self._running_threads.get(task_id)
            if prev is not None and prev.is_alive():
                continue

            scheduled = entry.next_run_at
            log.info(
                "Cron due — dispatching task %s (%s) scheduled=%s now=%s",
                task_id,
                task.get("name"),
                scheduled.isoformat(),
                now.isoformat(),
            )
            TaskExecutor = _load_task_executor_module().TaskExecutor

            executor = TaskExecutor(
                timeout=self._timeout,
                max_concurrent=self._max_workers,
            )
            # Must pass the registry task dict: execute_background sets status to running.
            _run, thread = executor.execute_background(task, trigger="cron")
            if thread is not None:
                self._running_threads[task_id] = thread

            entry.next_run_at = next_run_at_after(entry.matcher, scheduled)
            if entry.next_run_at is None:
                log.warning("Task %s: failed to compute next cron slot", task_id)
            else:
                log.info(
                    "Task %s (%s) next cron fire at %s (UTC)",
                    task_id,
                    task.get("name"),
                    entry.next_run_at.isoformat(),
                )
            dispatched += 1

        self._prune_dead_threads()
        return dispatched

    def _prune_dead_threads(self) -> None:
        dead = [tid for tid, th in self._running_threads.items() if not th.is_alive()]
        for tid in dead:
            del self._running_threads[tid]

    def stop(self) -> None:
        """Request the watch loop to stop (thread-safe)."""
        self._stop = True
        self._wake.set()

    def run(self, interval: float = 60.0, once: bool = False) -> None:
        """Start the watch loop.

        Args:
            interval: seconds between polls (default 60).
            once: if True, do a single check then return.
        """
        log.info("CronWatcher starting — polling every %.0fs, cron dir: %s", interval, CRON_DIR)
        self._stop = False
        self._wake.clear()

        if threading.current_thread() is threading.main_thread():
            def _on_signal(sig, _frame):
                log.info("Received signal %s, stopping …", sig)
                self.stop()
            signal.signal(signal.SIGINT, _on_signal)
            signal.signal(signal.SIGTERM, _on_signal)

        while not self._stop:
            try:
                self.reload_tasks()
                n = self.check_and_dispatch()
                if n:
                    log.info("Dispatched %d task(s) this cycle", n)
            except Exception:
                log.exception("Error in watch cycle")

            if once:
                break

            try:
                self._wake.wait(timeout=interval)
            except (KeyboardInterrupt, SystemExit):
                self.stop()
                break

        for tid, th in list(self._running_threads.items()):
            if th.is_alive():
                log.info("Waiting for task %s worker thread …", tid)
                th.join(timeout=5.0)
        log.info("CronWatcher stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Watch cron/ directory and execute matching tasks",
    )
    parser.add_argument(
        "--interval", type=float, default=60,
        help="Poll interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single check cycle then exit",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Max concurrent executor threads (default: 4)",
    )
    parser.add_argument(
        "--timeout", type=int, default=300,
        help="Per-task execution timeout in seconds (default: 300)",
    )
    args = parser.parse_args()

    watcher = CronWatcher(max_workers=args.workers, timeout=args.timeout)
    watcher.run(interval=args.interval, once=args.once)


if __name__ == "__main__":
    main()
