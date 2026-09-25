"""Gemini adapters over a mocked HTTP transport (request shape, parsing, errors, cost)."""

from __future__ import annotations

import base64
import json
import math

import httpx
import pytest

from app.ai import embeddings
from app.ai.base import AIProviderError, CompletionRequest
from app.ai.gemini import GeminiImageProvider, GeminiProvider
from app.ai.gemini import embed as gemini_embed
from app.core.config import Settings, settings
from app.media.generation import _font_arg
from tests.media_helpers import png_bytes


def _client(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://g.test")


async def test_text_request_parsing_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_FAST_MODEL", "gemini-fast")
    monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "g-key")
    monkeypatch.setattr(settings, "AI_FAST_THINKING_LEVEL", "low")
    monkeypatch.setattr(settings, "AI_FAST_INPUT_USD_PER_MTOK", 1.0)
    monkeypatch.setattr(settings, "AI_FAST_OUTPUT_USD_PER_MTOK", 4.0)
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.update(url=str(request.url), key=request.headers["x-goog-api-key"], body=body)
        prompt = body["contents"][0]["parts"][0]["text"]
        if prompt == "busy":
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        if prompt == "badkey":
            return httpx.Response(400, json={"error": {"message": "API key not valid."}})
        if prompt == "unsafe":
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
        if prompt == "long":
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]}
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "private reasoning", "thought": True},
                                {"text": '{"ok": '},
                                {"text": "true}"},
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 1000,
                    "candidatesTokenCount": 150,
                    "thoughtsTokenCount": 50,
                },
                "modelVersion": "gemini-fast-001",
            },
        )

    p = GeminiProvider(_client(handler))
    c = await p.complete(
        CompletionRequest(role="fast", system="sys", prompt="hello", max_tokens=500)
    )
    assert c.text == '{"ok": true}' and c.provider == "gemini" and c.model == "gemini-fast-001"
    # Thinking tokens are billed as output: 1000*1 + (150+50)*4 = 1800 per million.
    assert c.input_tokens == 1000 and c.output_tokens == 200 and math.isclose(c.cost_usd, 0.0018)
    assert seen["url"].endswith("/v1beta/models/gemini-fast:generateContent")
    assert seen["key"] == "g-key"
    assert seen["body"]["systemInstruction"] == {"parts": [{"text": "sys"}]}
    cfg = seen["body"]["generationConfig"]
    assert cfg["thinkingConfig"] == {"thinkingLevel": "low"} and cfg["maxOutputTokens"] > 500
    assert "temperature" not in cfg  # Gemini 3 models ignore/deprecate it

    for prompt, retryable, fragment in [
        ("busy", True, "busy"),
        ("badkey", False, "API key"),
        ("unsafe", False, "SAFETY"),
        ("long", False, "MAX_TOKENS"),
    ]:
        with pytest.raises(AIProviderError) as err:
            await p.complete(CompletionRequest(role="fast", system="s", prompt=prompt))
        assert err.value.retryable is retryable and fragment in str(err.value), prompt


async def test_empty_thinking_level_is_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_REASONING_MODEL", "gemini-pro")
    monkeypatch.setattr(settings, "AI_REASONING_THINKING_LEVEL", "")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]})

    await GeminiProvider(_client(handler)).complete(
        CompletionRequest(role="reasoning", system="s", prompt="p")
    )
    assert "thinkingConfig" not in seen["body"]["generationConfig"]


async def test_image_generation_and_legacy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_IMAGE_MODEL", "gemini-image")
    monkeypatch.setattr(settings, "AI_IMAGE_API_KEY", "")
    monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "shared-key")
    png = png_bytes()
    calls: list[tuple[str, dict, str]] = []
    legacy_only = {"on": False}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((request.url.path, body, request.headers["x-goog-api-key"]))
        prompt = body["contents"][0]["parts"][0]["text"]
        if legacy_only["on"] and "responseFormat" in body["generationConfig"]:
            return httpx.Response(
                400,
                json={"error": {"message": 'Unknown name "responseFormat": Cannot find field.'}},
            )
        if prompt == "forbidden":
            return httpx.Response(
                200, json={"candidates": [{"finishReason": "IMAGE_SAFETY", "content": {}}]}
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "A latte on oak."},
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64.b64encode(png).decode(),
                                    }
                                },
                            ]
                        }
                    }
                ]
            },
        )

    p = GeminiImageProvider(_client(handler))
    img = await p.generate("a latte", "story")
    assert img.data == png and img.mime_type == "image/png" and img.provider == "gemini"
    assert img.revised_prompt == "A latte on oak."
    path, body, key = calls[-1]
    assert path == "/v1/models/gemini-image:generateContent" and key == "shared-key"
    assert body["generationConfig"]["responseFormat"] == {
        "image": {"aspectRatio": "9:16", "imageSize": "1K"}
    }

    legacy_only["on"] = True
    calls.clear()
    img = await p.generate("a latte", "square")
    assert img.data == png and len(calls) == 2
    path, body, _ = calls[-1]
    assert path == "/v1beta/models/gemini-image:generateContent"
    assert body["generationConfig"]["imageConfig"] == {"aspectRatio": "1:1", "imageSize": "1K"}

    legacy_only["on"] = False
    with pytest.raises(AIProviderError) as err:
        await p.generate("forbidden", "square")
    assert not err.value.retryable and "IMAGE_SAFETY" in str(err.value)


async def test_embeddings_are_batched_and_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_EMBEDDING_MODEL", "gemini-embedding-001")
    monkeypatch.setattr(settings, "AI_EMBEDDING_DIMENSIONS", 4)
    monkeypatch.setattr(settings, "AI_PROVIDER_API_KEY", "shared-key")
    batches: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1beta/models/gemini-embedding-001:batchEmbedContents"
        req = body["requests"][0]
        assert req["model"] == "models/gemini-embedding-001"
        assert req["outputDimensionality"] == settings.AI_EMBEDDING_DIMENSIONS
        batches.append(len(body["requests"]))
        return httpx.Response(
            200, json={"embeddings": [{"values": [3.0, 4.0, 0.0, 0.0]} for _ in body["requests"]]}
        )

    vecs = await embeddings.embed([f"fact {i}" for i in range(130)], _client(handler))
    assert batches == [100, 30] and len(vecs) == 130
    assert vecs[0] == [0.6, 0.8, 0.0, 0.0]  # unit length

    monkeypatch.setattr(settings, "AI_EMBEDDING_DIMENSIONS", 8)
    with pytest.raises(AIProviderError):
        await gemini_embed(["x"], _client(handler))


def test_settings_accept_gemini_with_one_key() -> None:
    s = Settings(
        AI_PROVIDER="gemini",
        AI_PROVIDER_API_KEY="k",
        AI_FAST_MODEL="f",
        AI_REASONING_MODEL="r",
        AI_IMAGE_PROVIDER="gemini",
        AI_IMAGE_MODEL="i",
        AI_EMBEDDING_PROVIDER="gemini",
        AI_EMBEDDING_MODEL="e",
    )
    assert s.image_api_key == "k" and s.embedding_api_key == "k"
    with pytest.raises(ValueError, match="AI_EMBEDDING_PROVIDER"):
        Settings(AI_EMBEDDING_PROVIDER="gemini", AI_EMBEDDING_MODEL="e")


def test_video_font_falls_back_and_escapes_windows_paths() -> None:
    assert Settings(VIDEO_FONT_PATH="/nope/missing.ttf").video_font_path != "/nope/missing.ttf"
    assert _font_arg("C:\\Windows\\Fonts\\arialbd.ttf") == "C\\:/Windows/Fonts/arialbd.ttf"
    assert _font_arg(None) is None
