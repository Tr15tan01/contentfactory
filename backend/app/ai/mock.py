"""Offline stand-in for a real model, for development and tests only (refused in production).

It writes plain, template-based drafts from the structured hints the generator passes, returns
the same JSON shape a real model is asked for, and labels itself "mock" so the UI can say so.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.ai.base import Completion, CompletionRequest, Role

CAPTION_LIMITS = {
    "instagram": 2200,
    "facebook": 2000,
    "tiktok": 2200,
    "youtube": 5000,
    "linkedin": 3000,
}


def _pick(options: list[str], seed: str) -> str:
    return options[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(options)]


def _tag(text: str) -> str:
    return "".join(w.capitalize() for w in text.replace("#", " ").split() if w.isalnum())[:40]


class MockProvider:
    name = "mock"

    def model_for(self, role: Role) -> str:
        return f"mock-{role}"

    async def complete(self, req: CompletionRequest) -> Completion:
        h = req.hints
        seed = json.dumps(h, sort_keys=True, default=str)
        business = h.get("business", "our shop")
        idea = (h.get("idea") or "").strip()
        product = h.get("product") or {}
        subject = idea or (
            f"why people love our {product.get('name', '').lower()}"
            if product
            else f"a day at {business}"
        )
        subject = subject.rstrip(".")
        pillar = (
            "promotional"
            if product and not idea
            else _pick(["educational", "behind_the_scenes", "community"], seed)
        )
        hooks = [
            f"Here's something most people don't know about {subject.lower()}.",
            f"{subject[:1].upper()}{subject[1:]}: the short version.",
            f"We get asked about this every week: {subject.lower()}.",
        ]
        hook = _pick(hooks, seed + "hook")
        if h.get("instruction"):
            hook = f"{hook} ({h['instruction'][:60]})"
        benefits = product.get("benefits") or []
        body_lines = [
            hook,
            "",
            f"At {business}, we keep it simple and honest."
            if not product
            else f"Our {product.get('name')}: {product.get('description') or 'made with care'}.",
        ]
        if benefits:
            body_lines.append("What regulars tell us they love: " + ", ".join(benefits[:3]) + ".")
        goal_cta = {
            "more_visits": "Come by and say hello.",
            "more_bookings": "Book your spot through the link in our bio.",
            "online_sales": "Order online through the link in our bio.",
            "leads": "Send us a message with your questions.",
            "loyalty": "Tag a friend who needs to see this.",
        }
        cta = goal_cta.get(h.get("goal") or "", "Save this for later.")
        tone = ", ".join(h.get("tone") or []) or "friendly"
        media = h.get("media") or []
        chosen = None
        if media and h.get("prefer_media") != "never":
            words = set(subject.lower().split()) | {
                w.lower() for w in product.get("name", "").split()
            }
            scored = sorted(
                media,
                key=lambda m: (
                    -len(
                        words
                        & set(" ".join([m.get("name", ""), *m.get("tags", [])]).lower().split())
                    )
                ),
            )
            chosen = scored[0]["id"]
        stop = {
            "how",
            "why",
            "what",
            "when",
            "the",
            "our",
            "we",
            "a",
            "an",
            "and",
            "to",
            "of",
            "at",
            "in",
            "for",
            "this",
            "make",
        }
        keyword = max((w for w in subject.split() if w.lower() not in stop), key=len, default="")
        base_tags = [
            _tag(business),
            _tag(product.get("name", "")) if product else _tag(keyword),
        ]
        variants = []
        for platform in h.get("platforms") or ["instagram"]:
            n_tags = {"instagram": 6, "tiktok": 4, "facebook": 2, "youtube": 3, "linkedin": 3}.get(
                platform, 3
            )
            tags = [
                t
                for t in [*base_tags, "SmallBusiness", "ShopLocal", "BehindTheScenes", "Tips"]
                if t
            ][:n_tags]
            caption = "\n".join(body_lines)
            if platform in ("tiktok", "youtube"):
                caption = f"{hook} {cta}"
            variants.append(
                {
                    "platform": platform,
                    "caption": caption[: CAPTION_LIMITS.get(platform, 2200)],
                    "hashtags": tags,
                    "cta": cta,
                }
            )
        ctype = h.get("content_type", "post")
        script = None
        if ctype in ("reel", "short", "story", "video"):
            script = [
                {"scene": "Close-up opening shot", "on_screen_text": hook[:60], "duration_s": 3},
                {
                    "scene": f"Show {subject.lower()} in action",
                    "on_screen_text": "",
                    "duration_s": 8,
                },
                {"scene": "Friendly closing shot", "on_screen_text": cta, "duration_s": 3},
            ]
        slides = None
        if ctype == "carousel":
            slides = [
                {"heading": subject[:1].upper() + subject[1:60], "text": hook},
                {"heading": "The details", "text": body_lines[2] if len(body_lines) > 2 else ""},
                {"heading": "Your turn", "text": cta},
            ]
        subj = subject.lower()
        out: dict[str, Any] = {
            "title": (subject[:1].upper() + subject[1:])[:80],
            "pillar": pillar,
            "hook": hook,
            "visual": {
                "media_id": chosen,
                "concept": f"A bright, natural photo of {subj} at {business}. Tone: {tone}.",
                "image_prompt": f"Natural light photo, {subj}, {business}, candid, no text",
            },
            "script": script,
            "slides": slides,
            "variants": variants,
        }
        text = json.dumps(out)
        return Completion(
            text=text,
            provider=self.name,
            model=self.model_for(req.role),
            input_tokens=len(req.system + req.prompt) // 4,
            output_tokens=len(text) // 4,
        )
