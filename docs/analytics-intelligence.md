# Analytics, insights, memory and experiments

**Status:** implemented in Phase 6. Covered by `backend/tests/test_intelligence.py` (5 tests) and the browser test `frontend/e2e/phase6.py` (9 checks). Metrics collection has been tested against simulated platform responses only.

## Metrics collection (`app/analytics/collector.py`)

An hourly worker job pulls metrics for published posts on a decaying schedule: every 6 hours for the first 2 days, daily until day 7, weekly until day 30, then stops.

| Platform | Metrics requested |
| --- | --- |
| Instagram | reach, saves, shares, likes, comments, total interactions; views for Reels and videos |
| Facebook | reactions (as likes), comments, shares; reach where Facebook provides it for that post |
| TikTok | views, likes, comments, shares (needs the `video.list` scope) |
| YouTube | views, likes, comments |

A metric the platform doesn't report is stored as `NULL` and listed as missing from `available_metrics`, **never as zero**. The latest values live in `platform_metrics` (one row per publication); every pull also appends a `metric_snapshots` row. An auth error while collecting flags the account for reconnect.

## Analytics (`GET /workspaces/{id}/analytics?days=7|30|90`)

Totals, per-platform rows (with which metrics each platform didn't report), engagements per day in the workspace time zone, and the top five posts. Engagements are likes + comments + shares + saves over whichever of those the platform reports. A total is `null` when no post in the period reported that metric; the page shows "Not available".

## Insights (`app/analytics/insights.py`)

Nightly (and on "Analyse now"), for each dimension (pillar, format, time of day, platform) the engine takes the first metric with enough data (saves, then engagements, reach, views) over the last 90 days and compares the two best-measured groups. It states a finding only when:

- each group has at least **5** posts with that metric, and together at least **8** (`MIN_INSIGHT_SAMPLE`), and
- the better group is at least **20 %** ahead.

Confidence is *high* with 15+ posts per side and a 30 %+ gap, *medium* with 8+ per side, otherwise *low*. Each insight shows its sample, period and every group's average. Insights are keyed by dimension and metric, so re-analysis updates them; ones the data no longer supports become *superseded*, and a "Not useful" dismissal is respected for 30 days.

## Memory (`app/intelligence/memory.py`)

Short facts the agent should know: added by the owner, saved from an insight ("Remember this", with the insight's sample and period kept as evidence), or recorded from a finished experiment. Nothing trains a model.

- **Retrieval:** every AI draft includes pinned memories plus the most relevant others for the brief (up to 8), inside a `<what_we_learned>` block the system prompt tells the model to follow and never contradict.
- **Embeddings** (`app/ai/embeddings.py`): `local` (default) is signed feature hashing of words and word pairs, normalised, so similarity reflects shared vocabulary without any API. `voyage` uses Voyage AI for semantic similarity. Search combines vector similarity with a text match.
- Owners can edit, re-categorise, pin ("Always use") or delete any memory. Up to 500 per business.

## Experiments (`app/intelligence/experiments.py`)

A/B tests on one variable (hook, CTA, format, time, topic or visual) judged by one metric. Posts are assigned to variant A or B (never both). "Check results" (and the nightly job) compares per-post averages once each side has the minimum number of published, measured posts:

- a lead of 15 % or more completes the experiment, names the winner, and saves the conclusion to memory;
- otherwise it's marked *no clear winner*;
- before the minimum, it says "still collecting".

Plans: not on Free; Starter 1 running experiment; Business 3; Agency 10.

## API

All under `/api/v1/workspaces/{workspace_id}`: `GET /analytics`, `GET /insights`, `POST /insights/refresh`, `POST /insights/{id}/remember`, `POST /insights/{id}/dismiss`, `GET|POST /memory`, `PATCH|DELETE /memory/{id}`, `GET|POST /experiments`, `PUT /experiments/{id}/variants/{A|B}`, `POST /experiments/{id}/evaluate`, `POST /experiments/{id}/cancel`.
