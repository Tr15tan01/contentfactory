# AI images and video

**Status:** implemented in Phase 7. Covered by `backend/tests/test_generation.py` (4 tests, including a real ffmpeg render) and the browser test `frontend/e2e/phase7.py` (9 checks). The OpenAI-compatible image adapter has been tested against simulated responses only.

## Images (`app/ai/images.py`, `app/media/generation.py`)

| `AI_IMAGE_PROVIDER` | What it does |
| --- | --- |
| `mock` (default) | Draws a card labelled **"DEVELOPMENT PLACEHOLDER, NOT AI"** with the prompt, locally. The library badges it "Placeholder". **Refused in production.** It lets the whole flow (allowance, storage, reuse, attaching to posts) run offline. |
| `openai` | Any OpenAI-compatible `POST {AI_IMAGE_API_BASE_URL}/images/generations` returning `b64_json` (`AI_IMAGE_MODEL`, `AI_IMAGE_API_KEY`). Refused prompts come back as a clear, non-retryable message. |

Flow: `POST /workspaces/{id}/media/generate-image {prompt, aspect, use_brand, content_id?}`

1. With "use my brand" on, the prompt gains the brand's visual style and colours, and asks for no text or logos.
2. A **fingerprint** of provider, model, final prompt and shape is checked against the library. An identical earlier image is returned immediately, with **no charge** (`reused: true`).
3. Otherwise one image is reserved from the plan's monthly allowance (Free 10, Starter 40, Business 150, Agency 400) and a worker job generates it.
4. The bytes are checked to be a real PNG, JPEG or WebP, stored, and run through the normal media processing (dimensions, thumbnail). The prompt is kept as the description and in `ai_metadata`.
5. Failure refunds the allowance and says so on the file. With `content_id`, the finished image is attached to that post.

Shapes: square (1024×1024), portrait, landscape and tall (story).

## Videos from your own media (`app/media/generation.py`)

`POST /workspaces/{id}/media/build-video {scenes: [{media_id, duration_s, text?}], aspect, title?, content_id?}`

This is **assembly, not generative video**: it builds a Reel or Short from the business's own photos and clips with ffmpeg, and labels the result "Built video" (source `assembled`).

- Up to 20 scenes, 1–30 seconds each, 90 seconds in total; vertical 1080×1920 or square 1080×1080, 30 fps H.264 with a silent AAC track (some platforms reject videos without audio).
- Photos are shown for their scene's length; clips play from the start, and a clip shorter than its scene holds its last frame, so the video always matches the plan.
- Optional on-screen text per scene, in a readable box in the lower third (font: `VIDEO_FONT_PATH`).
- Cost: **1 video credit per started 30 seconds** (Free 2, Starter 5, Business 20, Agency 50 a month). Identical scene lists are reused without charge; a failed render refunds.
- The post editor's "Build video from script" pre-fills one scene per line of the AI-written script, with its on-screen text and length; you choose the photo or clip for each.
- Requires `ffmpeg` on the worker. Without it, the builder says it isn't available on the server.

Text-to-video models, voiceovers (`AI_VOICE_MODEL`) and generated video scenes are not implemented. They would use the same reserve, commit and refund flow and the `video_credits` allowance.
