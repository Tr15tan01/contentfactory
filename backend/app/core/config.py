"""Application settings, loaded from environment variables.

Feature flags use 1/0 so they read the same in .env files, hosting dashboards and CI.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# libpq connection options that asyncpg doesn't accept (it would fail with a TypeError).
_LIBPQ_ONLY = frozenset(
    {"channel_binding", "gssencmode", "target_session_attrs", "connect_timeout"}
)


class Settings(BaseSettings):
    # The test suite sets ENVIRONMENT=test and must never read a developer's .env: it could hold
    # real AI, payment or email credentials, and tests would call those services.
    model_config = SettingsConfigDict(
        env_file=None if os.environ.get("ENVIRONMENT") == "test" else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Runtime -----------------------------------------------------------
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "ContentFactory"
    APP_URL: str = "http://localhost:3000"  # public origin of the Next.js app
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    TRUSTED_PROXY_COUNT: int = 1  # X-Forwarded-For hops to trust (Next.js rewrite = 1)
    LOG_LEVEL: str = "INFO"

    # --- Infrastructure ----------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://cf:cf@localhost:5432/contentfactory"
    DATABASE_POOL_SIZE: int = 10
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Secrets -----------------------------------------------------------
    JWT_SECRET: str = Field(min_length=32)
    SESSION_SECRET: str = Field(min_length=32)
    # Fernet key(s) for encrypting social tokens at rest. Comma-separated; first is active.
    ENCRYPTION_KEYS: str = ""

    # --- Auth --------------------------------------------------------------
    AUTH_GOOGLE_ENABLED: bool = False
    AUTH_REQUIRE_EMAIL_VERIFICATION: bool = True
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    REFRESH_REUSE_GRACE_SECONDS: int = 15
    EMAIL_VERIFICATION_TTL_HOURS: int = 48
    PASSWORD_RESET_TTL_MINUTES: int = 30
    PASSWORD_MIN_LENGTH: int = 10
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    COOKIE_SECURE: bool = True
    COOKIE_DOMAIN: str | None = None
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- Email -------------------------------------------------------------
    EMAIL_PROVIDER: Literal["console", "resend"] = "console"
    EMAIL_PROVIDER_API_KEY: str = ""
    EMAIL_FROM: str = "ContentFactory <hello@contentfactory.app>"
    SUPPORT_EMAIL: str = "support@contentfactory.app"

    # --- Storage (S3-compatible) -------------------------------------------
    # "local" keeps files on disk and serves them through signed API URLs (development,
    # single-server installs). "s3" uses any S3-compatible service with presigned URLs.
    STORAGE_PROVIDER: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_DIR: str = "var/storage"
    STORAGE_URL_TTL_SECONDS: int = 3600
    MEDIA_MAX_IMAGE_MB: int = 25
    MEDIA_MAX_VIDEO_MB: int = 500
    STORAGE_ENDPOINT: str = ""
    STORAGE_REGION: str = "auto"
    STORAGE_BUCKET: str = "contentfactory"
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    # How browsers upload to S3: "post" (presigned POST; the bucket enforces the size limit;
    # AWS S3, MinIO) or "put" (presigned PUT; for Cloudflare R2, which has no POST uploads).
    # With "put" the size limit is enforced when the upload is completed (oversized files are
    # deleted), and processing re-checks the file type from its bytes either way.
    STORAGE_UPLOAD_METHOD: Literal["post", "put"] = "post"

    # --- AI provider abstraction -------------------------------------------
    # "mock" writes deterministic drafts offline (labelled as such in the UI); "anthropic"
    # calls the Messages API; "gemini" calls Google's Gemini API (GEMINI_API_BASE_URL).
    # Models are configuration, never hard-coded.
    AI_PROVIDER: Literal["mock", "anthropic", "gemini"] = "mock"
    AI_PROVIDER_API_KEY: str = ""
    AI_FAST_MODEL: str = ""
    AI_REASONING_MODEL: str = ""
    AI_IMAGE_MODEL: str = ""
    # "mock" draws a labelled placeholder locally (development only, refused in production);
    # "openai" calls an OpenAI-compatible /images/generations endpoint (AI_IMAGE_API_BASE_URL);
    # "gemini" uses Gemini native image generation (key falls back to AI_PROVIDER_API_KEY).
    AI_IMAGE_PROVIDER: Literal["mock", "openai", "gemini"] = "mock"
    AI_IMAGE_API_KEY: str = ""
    AI_IMAGE_API_BASE_URL: str = "https://api.openai.com/v1"
    # Font for on-screen text in assembled videos and placeholders. Empty or missing = the first
    # common bold font found on this machine (Linux DejaVu, Windows Arial, macOS Arial).
    VIDEO_FONT_PATH: str = ""
    AI_VIDEO_MODEL: str = ""
    AI_EMBEDDING_MODEL: str = ""
    AI_VOICE_MODEL: str = ""
    AI_EMBEDDING_DIMENSIONS: int = 1536
    # "local" = lexical hashing vectors computed in-process (no API, fine for short business
    # facts); "voyage" = Voyage AI embeddings (set AI_EMBEDDING_MODEL and AI_EMBEDDING_API_KEY);
    # "gemini" = Gemini embeddings (key falls back to AI_PROVIDER_API_KEY). After switching,
    # run `python -m scripts.reembed_memory`.
    AI_EMBEDDING_PROVIDER: Literal["local", "voyage", "gemini"] = "local"
    AI_EMBEDDING_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://api.anthropic.com"
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com"
    # Gemini thinking effort per role: minimal/low/medium/high, or empty for the model default.
    AI_FAST_THINKING_LEVEL: str = "low"
    AI_REASONING_THINKING_LEVEL: str = "medium"
    AI_TIMEOUT_SECONDS: int = 90
    AI_CACHE_TTL_HOURS: int = 336  # identical requests reuse results for 14 days
    # Optional provider prices (USD per million tokens) for cost tracking; 0 = not tracked.
    AI_FAST_INPUT_USD_PER_MTOK: float = 0
    AI_FAST_OUTPUT_USD_PER_MTOK: float = 0
    AI_REASONING_INPUT_USD_PER_MTOK: float = 0
    AI_REASONING_OUTPUT_USD_PER_MTOK: float = 0

    # --- Billing (Paddle) --------------------------------------------------
    # 0 = launch without paid plans: Paddle isn't required in production and everyone is on Free
    # (the Billing page says paid plans aren't available). Plans granted with scripts.set_plan work.
    BILLING_ENABLED: bool = True
    PADDLE_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"
    PADDLE_API_KEY: str = ""
    PADDLE_CLIENT_TOKEN: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_STARTER_PRICE_ID: str = ""
    PADDLE_BUSINESS_PRICE_ID: str = ""
    PADDLE_AGENCY_PRICE_ID: str = ""
    # Override the Paddle API host (proxies, local test doubles). Empty = Paddle's own host.
    PADDLE_API_BASE_URL: str = ""

    # --- Social platforms --------------------------------------------------
    META_CLIENT_ID: str = ""
    META_CLIENT_SECRET: str = ""
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    META_GRAPH_VERSION: str = "v21.0"
    # Overrides for proxies and local test stand-ins; empty = Meta's own hosts.
    META_GRAPH_BASE_URL: str = ""
    META_DIALOG_BASE_URL: str = ""
    # YouTube uses GOOGLE_CLIENT_ID/SECRET with its own upload scope and redirect URI.
    YOUTUBE_ENABLED: bool = True

    # --- Push --------------------------------------------------------------
    PUSH_PUBLIC_KEY: str = ""
    PUSH_PRIVATE_KEY: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _asyncpg_url(cls, v: str) -> str:
        """Accept connection strings as hosted providers (Neon, Supabase, Render...) print them:
        use the asyncpg driver, map libpq's `sslmode` to asyncpg's `ssl`, and drop libpq-only
        options asyncpg would reject."""
        parts = urlsplit(v.strip())
        scheme = parts.scheme
        if scheme in ("postgres", "postgresql"):
            scheme = "postgresql+asyncpg"
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "sslmode":
                key = "ssl"
            elif key in _LIBPQ_ONLY:
                continue
            query.append((key, value))
        return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        if self.AUTH_GOOGLE_ENABLED and not (self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET):
            raise ValueError(
                "AUTH_GOOGLE_ENABLED=1 requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
            )
        if self.AI_PROVIDER != "mock" and not (
            self.AI_PROVIDER_API_KEY and self.AI_FAST_MODEL and self.AI_REASONING_MODEL
        ):
            raise ValueError(
                f"AI_PROVIDER={self.AI_PROVIDER} requires AI_PROVIDER_API_KEY, AI_FAST_MODEL "
                "and AI_REASONING_MODEL"
            )
        if self.AI_IMAGE_PROVIDER != "mock" and not (self.image_api_key and self.AI_IMAGE_MODEL):
            raise ValueError("AI_IMAGE_PROVIDER requires AI_IMAGE_API_KEY and AI_IMAGE_MODEL")
        if self.AI_EMBEDDING_PROVIDER != "local" and not (
            self.embedding_api_key and self.AI_EMBEDDING_MODEL
        ):
            raise ValueError(
                "AI_EMBEDDING_PROVIDER requires AI_EMBEDDING_API_KEY and AI_EMBEDDING_MODEL"
            )
        if self.is_production:
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be 1 in production")
            if not self.ENCRYPTION_KEYS:
                raise ValueError("ENCRYPTION_KEYS is required in production")
            if self.EMAIL_PROVIDER == "console":
                raise ValueError("EMAIL_PROVIDER=console is not allowed in production")
            if self.AI_PROVIDER == "mock":
                raise ValueError("AI_PROVIDER=mock is not allowed in production")
            if self.AI_IMAGE_PROVIDER == "mock":
                raise ValueError("AI_IMAGE_PROVIDER=mock is not allowed in production")
            if self.BILLING_ENABLED and not (
                self.PADDLE_API_KEY
                and self.PADDLE_CLIENT_TOKEN
                and self.PADDLE_WEBHOOK_SECRET
                and self.PADDLE_STARTER_PRICE_ID
                and self.PADDLE_BUSINESS_PRICE_ID
                and self.PADDLE_AGENCY_PRICE_ID
            ):
                raise ValueError(
                    "All PADDLE_* settings are required in production (or set BILLING_ENABLED=0)"
                )
            if self.STORAGE_PROVIDER == "local":
                raise ValueError("STORAGE_PROVIDER=local is not allowed in production; use s3")
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def image_api_key(self) -> str:
        if self.AI_IMAGE_PROVIDER == "gemini":
            return self.AI_IMAGE_API_KEY or self.AI_PROVIDER_API_KEY
        return self.AI_IMAGE_API_KEY

    @property
    def embedding_api_key(self) -> str:
        if self.AI_EMBEDDING_PROVIDER == "gemini":
            return self.AI_EMBEDDING_API_KEY or self.AI_PROVIDER_API_KEY
        return self.AI_EMBEDDING_API_KEY

    @property
    def video_font_path(self) -> str | None:
        """The configured font if it exists, otherwise the first common bold font found."""
        candidates = [
            self.VIDEO_FONT_PATH,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
        return next((c for c in candidates if c and Path(c).is_file()), None)

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.APP_URL}{self.API_PREFIX}/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
