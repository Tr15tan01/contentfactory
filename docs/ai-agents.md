# AI agents and Marketing Intelligence

**Status:** the provider abstraction, usage accounting, response cache and single-post drafting are implemented (Phase 3, see [content-workflow.md](content-workflow.md)). Also: schema implemented (`agent_runs`, `agent_steps`, `marketing_memory` with pgvector, `marketing_insights`, `experiments`, `research_items`, `ai_usage`); the dashboard already reads agent activity and insights. The multi-agent runs and memory retrieval are Phase 6. Model names are configuration only.

## Provider abstraction

```python
class AIProvider(Protocol):
    async def complete(self, req: CompletionRequest) -> Completion: ...   # text / JSON
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def image(self, req: ImageRequest) -> GeneratedMedia: ...
    async def video(self, req: VideoRequest) -> VideoJob: ...            # async, polled
```

`AI_PROVIDER` selects the implementation (`mock` by default, so the whole product runs offline). Each call names a **role**, not a model; roles map to env vars:

| Role | Variable | Used for |
| --- | --- | --- |
| fast | `AI_FAST_MODEL` | Captions, hashtags, classification, tagging |
| reasoning | `AI_REASONING_MODEL` | Strategy, weekly plans, analysis, experiment design |
| image | `AI_IMAGE_MODEL` | Brand-aware images |
| video | `AI_VIDEO_MODEL` | Short-form video scenes |
| embedding | `AI_EMBEDDING_MODEL` | Memory and media search (`AI_EMBEDDING_DIMENSIONS`) |
| voice | `AI_VOICE_MODEL` | Voiceovers |

All calls go through the usage service (reserve, commit or refund, cache) described in [billing.md](billing.md). Structured outputs are validated against Pydantic schemas; one repair attempt is allowed before the step fails.

## Agents

An orchestrator run creates child steps for the specialists. Each agent is a function with typed input and output, not a free-roaming loop.

| Agent | Input | Output |
| --- | --- | --- |
| Strategy | Profile, goals, memory, recent insights | Pillars, weekly mix, campaign ideas |
| Research | Industry, location, calendar | `research_items` (deduplicated, `trusted` flag for vetted sources) |
| Content | Plan slot, brand voice, memory | Hooks, captions, CTAs, variants per platform |
| Creative | Draft, media library, preference | Chosen media or an image/video brief |
| Publishing | Approved content | Adapted variants, schedules (see [social-integrations.md](social-integrations.md)) |
| Analytics | Metrics | Comparisons with sample sizes → `marketing_insights` |
| Optimization | Insights, experiments | Memory updates and next-plan adjustments |

### Guardrails

- Every run copies `max_steps`, `max_runtime_seconds`, `max_cost_usd` and `max_retries` at creation. Hitting any limit ends the run as `limit_reached` and tells the user.
- Every step is recorded in `agent_steps` with a plain-language summary shown on the activity timeline.
- Content from research sources and user uploads is treated as data, never as instructions (prompt-injection defence): it's quoted inside delimited blocks and the system prompt says so.
- Autopilot publishes only content that passes brand, forbidden-topic, platform-format, media and safety checks; low confidence stops the run with a `needs_input` state.

## Marketing Intelligence (no retraining)

1. **Collect** real metrics per publication (`platform_metrics`, snapshots over time).
2. **Compare** groups (pillar, format, hook style, time of day, platform) over a fixed period. A conclusion requires at least 5 posts in each group and 8 (`MIN_INSIGHT_SAMPLE`) in total, and a 20 % difference; otherwise nothing is claimed.
3. See [analytics-intelligence.md](analytics-intelligence.md) for the exact thresholds (5 posts per group, 8 in total, 20 % difference). **Record** an insight with statement, sample size, period, confidence and evidence JSON. Users can accept, reject, edit or mark it outdated.
4. **Remember** accepted insights and user corrections as `marketing_memory` rows (categories such as `brand`, `audience`, `successful_topic`, `weak_format`, `successful_hook`, `platform_pattern`) with embeddings.
5. **Retrieve** the most relevant memories for each task (pgvector cosine similarity, filtered by workspace and category, pinned memories always included) and pass them as context.

Users can see, edit, pin or delete every memory at `/intelligence/memory`.
