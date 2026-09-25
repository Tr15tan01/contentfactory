# Workers

Background jobs run on [arq](https://arq-docs.helpmanual.io/) (async, Redis-backed). The job code lives in
`backend/app/workers/` so it shares models, services and configuration with the API, with no duplicated
business logic.

```bash
cd backend
arq app.workers.settings.WorkerSettings          # run a worker
arq app.workers.settings.WorkerSettings --check  # health check (exit code)
```

| Job | Trigger | Purpose |
| --- | --- | --- |
| `send_email` | Enqueued by the API | Renders a template and sends via the configured email provider |
| `purge_expired_auth_rows` | Cron, daily 03:17 UTC | Deletes expired sessions, verification and reset tokens |

API code enqueues through the `JobQueue` protocol (`backend/app/workers/queue.py`). Tests swap in
`RecordingJobQueue`, so no Redis worker is needed to test the API.

Later phases add queues for AI generation, media processing, publishing (idempotency keys, exponential
backoff), analytics collection and agent runs. Run one worker per queue in production so slow video jobs
can't delay publishing.
