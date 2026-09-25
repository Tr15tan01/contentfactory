import { ApiError } from "./api/client";
import { mediaApi } from "./api/endpoints";
import type { MediaAsset } from "@/types/api";

export const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm";
const MAX_IMAGE = 25 * 1024 * 1024; // mirrors MEDIA_MAX_IMAGE_MB; the server is authoritative
const MAX_VIDEO = 500 * 1024 * 1024;

/** Quick client-side check so obviously wrong files fail instantly; the server re-checks bytes. */
export function precheck(file: File): string | null {
  if (!ACCEPT.split(",").includes(file.type)) return "Only JPEG, PNG, WebP, GIF, MP4, MOV and WebM files can be uploaded.";
  const max = file.type.startsWith("video/") ? MAX_VIDEO : MAX_IMAGE;
  if (file.size > max) return `${file.type.startsWith("video/") ? "Videos" : "Images"} can be up to ${max / 1024 / 1024} MB.`;
  return null;
}

/** Browser → storage directly (presigned POST on S3, signed PUT locally), with progress. */
function send(url: string, method: "POST" | "PUT", file: File, fields: Record<string, string>, headers: Record<string, string>, onProgress: (p: number) => void, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new ApiError(xhr.status, "upload_failed", xhr.status === 413 ? "The file is larger than allowed." : "The upload didn't finish. Try again.")));
    xhr.onerror = () => reject(new ApiError(0, "network_error", "The upload was interrupted. Check your connection and try again."));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort());
    if (method === "POST") {
      const form = new FormData();
      Object.entries(fields).forEach(([k, v]) => form.append(k, v));
      form.append("file", file); // S3 requires the file to be the last field
      xhr.send(form);
    } else {
      Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));
      xhr.send(file);
    }
  });
}

export async function uploadFile(
  workspaceId: string,
  file: File,
  opts: { folderId?: string | null; onProgress?: (p: number) => void; signal?: AbortSignal } = {},
): Promise<MediaAsset> {
  const problem = precheck(file);
  if (problem) throw new ApiError(400, "invalid_file", problem);
  const { asset, upload } = await mediaApi.startUpload(workspaceId, {
    filename: file.name,
    content_type: file.type,
    size_bytes: file.size,
    folder_id: opts.folderId ?? null,
  });
  await send(upload.url, upload.method, file, upload.fields, upload.headers, opts.onProgress ?? (() => {}), opts.signal);
  return mediaApi.complete(workspaceId, asset.id);
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(n < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

export function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.round(s % 60)).padStart(2, "0")}`;
}
