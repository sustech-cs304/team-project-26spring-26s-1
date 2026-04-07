import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from agent.file_utils.extract import extract_attachment

class FileRunner:
    def __init__(self, session_factory: async_sessionmaker, config, max_concurrency: int = 5):
        self.session_factory = session_factory
        self.config = config
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._status : dict[str, str] = {}
        self._closing = False

    async def start(self):
        self._closing = False

    async def run_task(self, file_id: str):
        async with self._lock:
            if self._closing:
                raise RuntimeError("FileRunner is closing, cannot enqueue new files.")
            task = self._tasks.get(file_id)
            if task and not task.done():
                return False
            self._status[file_id] = "pending"
            self._tasks[file_id] = asyncio.create_task(self._run(file_id))
            return True

    async def _run(self, file_id: str):
        try:
            self._status[file_id] = "running"
            async with self.semaphore:
                await extract_attachment(file_id, self.session_factory, self.config)
            self._status[file_id] = "completed"
        except asyncio.CancelledError:
            self._status[file_id] = "cancelled"
        except Exception:
            self._status[file_id] = "failed"
        finally:
            async with self._lock:
                task = self._tasks.get(file_id)
                if task and task.done():
                    self._tasks.pop(file_id, None)

    async def get_status(self, file_id: str) -> str | None:
        async with self._lock:
            return self._status.get(file_id)
    
    async def stop(self, timeout: float | None = None):
        async with self._lock:
            self._closing = True
            pending = [t for t in self._tasks.values() if not t.done()]
            for task in pending:
                task.cancel()