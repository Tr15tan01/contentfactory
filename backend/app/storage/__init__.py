from __future__ import annotations

from app.core.config import settings
from app.storage.base import ObjectInfo, Storage, UploadTarget

_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.STORAGE_PROVIDER == "s3":
            from app.storage.s3 import S3Storage

            _storage = S3Storage()
        else:
            from app.storage.local import LocalStorage

            _storage = LocalStorage(settings.STORAGE_LOCAL_DIR)
    return _storage


def set_storage(storage: Storage | None) -> None:
    """Swap the backend (tests)."""
    global _storage
    _storage = storage


__all__ = ["ObjectInfo", "Storage", "UploadTarget", "get_storage", "set_storage"]
