"""arq worker entrypoint:  arq app.workers.settings.WorkerSettings

Later phases register AI generation, publishing, analytics sync and media jobs here, each
with its own timeout and retry policy.
"""

from __future__ import annotations

import logging

from arq import cron, func
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.jobs.content import generate_content
from app.workers.jobs.email import send_email
from app.workers.jobs.intelligence import (
    approval_reminders,
    collect_metrics,
    nightly_intelligence,
    notification_emails,
)
from app.workers.jobs.maintenance import purge_expired_auth_rows
from app.workers.jobs.media import (
    delete_media_objects,
    generate_image,
    process_media,
    purge_abandoned_uploads,
    render_video,
)
from app.workers.jobs.recovery import recover_lost_jobs
from app.workers.jobs.social import (
    enqueue_due_publications,
    publish_publication,
    refresh_social_tokens,
)

logging.basicConfig(level=settings.LOG_LEVEL)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [
        send_email,
        purge_expired_auth_rows,
        func(generate_content, timeout=180, max_tries=1),  # the job itself refunds on failure
        func(process_media, timeout=900, max_tries=3),  # large videos: download + ffmpeg
        delete_media_objects,
        purge_abandoned_uploads,
        func(generate_image, timeout=300, max_tries=1),  # refunds itself on failure
        func(render_video, timeout=1200, max_tries=1),
        enqueue_due_publications,
        func(publish_publication, timeout=900, max_tries=1),  # retries are scheduled explicitly
        refresh_social_tokens,
        func(collect_metrics, timeout=900),
        func(nightly_intelligence, timeout=1800),
        approval_reminders,
        notification_emails,
        recover_lost_jobs,
    ]
    cron_jobs = [
        cron(purge_expired_auth_rows, hour=3, minute=17),
        cron(purge_abandoned_uploads, hour=3, minute=41),
        cron(enqueue_due_publications, second=5, unique=True),  # every minute
        cron(refresh_social_tokens, minute=23, unique=True),  # hourly
        cron(
            collect_metrics, minute=11, unique=True
        ),  # hourly; per-post cadence decides what's due
        cron(nightly_intelligence, hour=4, minute=5, unique=True),
        cron(approval_reminders, minute={0, 15, 30, 45}, second=20, unique=True),
        cron(notification_emails, second=40, unique=True),  # every minute
        # every 10 minutes: re-enqueue work whose queue entry Redis lost (see jobs/recovery.py)
        cron(recover_lost_jobs, minute=set(range(7, 60, 10)), second=50, unique=True),
    ]
    max_jobs = settings.WORKER_MAX_JOBS
    job_timeout = 300
    max_tries = 5
