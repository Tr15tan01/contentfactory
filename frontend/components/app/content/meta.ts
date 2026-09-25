import type { ContentType, PlatformId } from "@/types/api";

// Mirrors backend/app/content/rules.py (the server re-validates everything).
export const CONTENT_TYPES: { id: ContentType; label: string; hint: string }[] = [
  { id: "post", label: "Post", hint: "Photo and caption" },
  { id: "carousel", label: "Carousel", hint: "Several slides" },
  { id: "reel", label: "Reel", hint: "Short vertical video" },
  { id: "short", label: "Short", hint: "YouTube or TikTok video" },
  { id: "story", label: "Story", hint: "24-hour story" },
];

export const PLATFORM_RULES: Record<PlatformId, { label: string; captionMax: number; hashtagsMax: number; types: ContentType[]; available: boolean }> = {
  instagram: { label: "Instagram", captionMax: 2200, hashtagsMax: 30, types: ["post", "carousel", "reel", "story"], available: true },
  facebook: { label: "Facebook", captionMax: 5000, hashtagsMax: 10, types: ["post", "carousel", "reel", "story", "video"], available: true },
  tiktok: { label: "TikTok", captionMax: 2200, hashtagsMax: 10, types: ["reel", "short", "video", "carousel"], available: true },
  youtube: { label: "YouTube", captionMax: 5000, hashtagsMax: 15, types: ["short", "video"], available: true },
  linkedin: { label: "LinkedIn", captionMax: 3000, hashtagsMax: 5, types: ["post", "carousel", "video"], available: false },
  pinterest: { label: "Pinterest", captionMax: 500, hashtagsMax: 20, types: ["post", "video"], available: false },
  x: { label: "X", captionMax: 280, hashtagsMax: 3, types: ["post", "video"], available: false },
};

export const PLATFORM_ORDER: PlatformId[] = ["instagram", "facebook", "tiktok", "youtube", "linkedin", "pinterest", "x"];

export const PILLAR_LABELS: Record<string, string> = {
  educational: "Educational",
  promotional: "Promotional",
  behind_the_scenes: "Behind the scenes",
  community: "Community",
  product: "Product",
  seasonal: "Seasonal",
  entertainment: "Entertainment",
};

export const VIDEO_TYPES: ContentType[] = ["reel", "short", "story", "video"];
