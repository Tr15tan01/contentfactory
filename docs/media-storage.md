# Media library and storage

**Status:** implemented in Phase 2. Covered by `backend/tests/test_media.py`, `test_storage_s3.py` and the browser test `frontend/e2e/phase2.py`.

## Storage backends

`backend/app/storage/` defines one `Storage` protocol with two implementations:

| `STORAGE_PROVIDER` | Use | Uploads | Downloads |
| --- | --- | --- | --- |
| `local` (default) | Development, tests, single-server trials. **Refused in production.** | Signed `PUT /api/v1/storage/local/upload?token=…` | Signed `GET /api/v1/storage/local/object?token=…` |
| `s3` | Production: AWS S3, Cloudflare R2, MinIO, Backblaze B2, … | Presigned **POST** straight to the bucket | Presigned GET |

Bytes never go through PostgreSQL, and on S3 they never go through the API either.

Local tokens are HMAC-signed with `SESSION_SECRET` (domain-separated from other signatures). An upload token names one key, one content type, a byte limit and a 15-minute expiry; the API streams the body to disk and aborts as soon as it passes the limit, even without a `Content-Length`. Download URLs expire in bucketed windows (`STORAGE_URL_TTL_SECONDS`) so the same file keeps the same URL long enough for browsers to cache it. Downloads are served with `nosniff` and a sandboxing `Content-Security-Policy`.

On S3 the presigned POST policy carries `content-length-range` and an exact `Content-Type`, so the bucket itself rejects oversized or relabelled uploads.

## Upload flow

```
browser ── POST /workspaces/{id}/media/uploads ─► API: validate type + declared size, create asset (pending_upload), return upload target
browser ── PUT/POST file ──────────────────────► storage (direct)
browser ── POST /media/{asset}/complete ───────► API: HEAD object, check size, status → processing, enqueue process_media
worker  ── process_media ──────────────────────► verify magic bytes, SHA-256, dimensions/duration, thumbnail, duplicate check → ready
```

- **Allowed:** JPEG, PNG, WebP, GIF up to `MEDIA_MAX_IMAGE_MB` (25); MP4, MOV, WebM up to `MEDIA_MAX_VIDEO_MB` (500). SVG and HTML are never accepted.
- **Content is checked, not the name.** If the bytes don't match the declared type, the asset becomes `quarantined`, the object is deleted, and the library shows "Not added" with the reason.
- **Images:** Pillow verifies the file (80-megapixel decompression-bomb limit), reads dimensions after EXIF rotation, and writes a 640px WebP thumbnail. Re-encoding drops EXIF, so GPS data in phone photos never reaches thumbnails. Originals are kept byte-for-byte.
- **Videos:** if `ffprobe`/`ffmpeg` are installed on the worker, width, height, duration and a poster frame are extracted. Without them, videos still upload and play; they just have no thumbnail or duration.
- **Duplicates:** an upload with the same SHA-256 as an existing file is kept but flagged (`duplicate_of`) so the user can remove it.
- **Cleanup:** deleting an asset soft-deletes the row and enqueues `delete_media_objects`. A nightly job removes uploads that were started but never completed within 24 hours.

## Library API

All under `/api/v1/workspaces/{workspace_id}`; viewers can read, editors and above can change.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/media?q=&kind=&folder=&tag=&favorites=&cursor=&limit=` | Search and filter (name, description, filename, tags); cursor pagination; `folder=unfiled` supported |
| POST | `/media/uploads` | Start an upload |
| POST | `/media/{id}/complete` | Finish an upload (idempotent) |
| GET / PATCH / DELETE | `/media/{id}` | Read, edit (name, description, tags, folder, favourite), delete |
| GET | `/media/tags` | Tags with counts |
| GET / POST | `/media-folders` | List (with counts) or create (names unique, case-insensitive) |
| PATCH / DELETE | `/media-folders/{id}` | Rename, or delete (files move to Unfiled, never deleted) |

## S3 bucket setup

1. Create a private bucket (no public access).
2. Create credentials limited to that bucket: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket`.
3. Add a CORS rule so browsers can POST directly and load previews:

```json
[{
  "AllowedOrigins": ["https://app.example.com"],
  "AllowedMethods": ["POST", "GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "ExposeHeaders": ["ETag"],
  "MaxAgeSeconds": 3600
}]
```

4. Set `STORAGE_PROVIDER=s3`, `STORAGE_BUCKET`, `STORAGE_REGION`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, and `STORAGE_ENDPOINT` for non-AWS providers (e.g. `https://<account>.r2.cloudflarestorage.com`).
5. Optionally add a lifecycle rule for incomplete multipart uploads; the app's own nightly cleanup handles abandoned single uploads.

## Business profile

Also Phase 2 (`app/services/business.py`, `app/api/v1/business.py`): profile, brand (voice, tone, colours, words to use/avoid, logo from the library), products with library photos, publishing preferences (media preference, platforms, posts per week, approval, reminders) and resumable onboarding progress. Saving the profile renames the workspace to the business name. Turning off approval requires a plan with automatic publishing (Business or Agency); the check lives in `app/billing/entitlements.py`, where Phase 4 adds quota counters.
