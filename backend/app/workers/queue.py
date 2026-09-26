"""Job queue abstraction. HTTP handlers enqueue; workers execute. Nothing slow runs inline."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

log = logging.getLogger("contentfactory.queue")


class JobQueue(Protocol):
    async def enqueue(self, job: str, /, **kwargs: Any) -> None: ...


# Jobs that app.workers.jobs.recovery may enqueue again after Redis loses its data. A fixed job
# id per unit of work makes arq refuse a second copy while the first is queued, running, or
# its result is still kept, so recovery can't start work that is still in progress.
DEDUPED_JOBS = {
    "generate_content": "usage_id",
    "generate_image": "usage_id",
    "render_video": "usage_id",
    "process_media": "asset_id",
}


def job_id(job: str, kwargs: dict[str, Any]) -> str | None:
    field = DEDUPED_JOBS.get(job)
    return f"{job}:{kwargs[field]}" if field and field in kwargs else None


class ArqJobQueue:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def enqueue(self, job: str, /, **kwargs: Any) -> None:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await self._pool.enqueue_job(job, _job_id=job_id(job, kwargs), **kwargs)


class RecordingJobQueue:
    """Test double: records jobs instead of sending them."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, job: str, /, **kwargs: Any) -> None:
        self.jobs.append((job, kwargs))

    def last(self, job: str) -> dict[str, Any]:
        for name, kwargs in reversed(self.jobs):
            if name == job:
                return kwargs
        raise LookupError(job)


_queue: JobQueue = ArqJobQueue()


def get_queue() -> JobQueue:
    return _queue


def set_queue(queue: JobQueue) -> None:
    global _queue
    _queue = queue
