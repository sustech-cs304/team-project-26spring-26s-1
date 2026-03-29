import asyncio
from typing import Dict

class _ConversationJobState:
    def __init__(self):
        self.history = []
        self.cond = asyncio.Condition()
        self.done = False
        self.task : asyncio.Task = None # type: ignore
        
class ConversationRunner:
    def __init__(self):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        pass
    
    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self._conversation_jobs
    
    def run(self, conversation_id : str):
        if conversation_id not in self._conversation_jobs:
            self._conversation_jobs[conversation_id] = _ConversationJobState()
        else:
            raise ValueError(f"Conversation {conversation_id} is already running")

        async def _test_generate():
            for i in range(100):
                await asyncio.sleep(1)
                yield f"message {i}"
        
        async def _run(job: _ConversationJobState):
            try:
                async for message in _test_generate():
                    async with job.cond:
                        job.history.append(message)
                        job.cond.notify_all()
            except asyncio.CancelledError:
                pass
            finally:
                async with job.cond:
                    job.done = True
                    job.cond.notify_all()
                self._conversation_jobs.pop(conversation_id, None)
        
        self._conversation_jobs[conversation_id].task = asyncio.create_task(_run(self._conversation_jobs[conversation_id]))
        
    def listen(self, conversation_id : str):
        async def _listen(job: _ConversationJobState):
            idx = 0
            while True:
                async with job.cond:
                    while idx < len(job.history):
                        yield job.history[idx]
                        idx += 1
                    if job.done:
                        break
                    try:
                        await asyncio.wait_for(job.cond.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass
        return _listen(self._conversation_jobs[conversation_id])
                    
    def cancel(self, conversation_id : str):
        if conversation_id in self._conversation_jobs:
            job = self._conversation_jobs[conversation_id]
            if job.task:
                job.task.cancel()