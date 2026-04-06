import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from agent.file_utils.extract import extract_attachment

class FileRunner:
    def __init__(self, session_factory: async_sessionmaker, config, workers: int = 2):
        self.session_factory = session_factory
        self.config = config
        self.workers = workers
        self.queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._file_ids: set[str] = set()
        self._lock = asyncio.Lock()

    async def start(self):
        for _ in range(self.workers):
            self._tasks.append(asyncio.create_task(self._worker()))

    async def enqueue(self, file_id: str):
        async with self._lock:
            if file_id in self._file_ids:
                return
            self._file_ids.add(file_id)
        await self.queue.put(file_id)

    async def _worker(self):
        while True:
            file_id = await self.queue.get()
            if file_id is None:
                self.queue.task_done()
                break
            try:
                await extract_attachment(file_id=file_id, session_factory=self.session_factory, config=self.config)
            finally:
                async with self._lock:
                    self._file_ids.discard(file_id)
                self.queue.task_done()

    async def stop(self):
        for _ in range(self.workers):
            await self.queue.put(None)
        await asyncio.gather(*self._tasks, return_exceptions=True)