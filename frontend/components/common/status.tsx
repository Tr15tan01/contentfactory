import { cn } from "@/lib/utils";

/** Content lifecycle statuses (spec §16) with one visual language across the app. */
export const STATUS_META: Record<string, { label: string; tone: "neutral" | "lab" | "marker" | "signal" | "live" }> = {
  draft: { label: "Draft", tone: "neutral" },
  generating: { label: "Generating", tone: "live" },
  ready: { label: "Ready", tone: "neutral" },
  awaiting_approval: { label: "Awaiting approval", tone: "marker" },
  approved: { label: "Approved", tone: "lab" },
  scheduled: { label: "Scheduled", tone: "lab" },
  publishing: { label: "Publishing", tone: "live" },
  published: { label: "Published", tone: "lab" },
  failed: { label: "Failed", tone: "signal" },
  rejected: { label: "Rejected", tone: "neutral" },
  running: { label: "Working", tone: "live" },
  queued: { label: "Queued", tone: "neutral" },
  succeeded: { label: "Done", tone: "lab" },
  completed: { label: "Done", tone: "lab" },
  needs_input: { label: "Needs you", tone: "marker" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  limit_reached: { label: "Stopped at limit", tone: "signal" },
};

const toneClass = {
  neutral: "bg-sunk text-muted",
  lab: "bg-lab-soft text-lab",
  marker: "bg-marker-soft text-ink dark:text-marker",
  signal: "bg-signal-soft text-signal",
  live: "bg-lab-soft text-lab",
} as const;

export function StatusChip({ status, className }: { status: string; className?: string }) {
  const meta = STATUS_META[status] ?? { label: status.replaceAll("_", " "), tone: "neutral" as const };
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", toneClass[meta.tone], className)}>
      {meta.tone === "live" && <span className="size-1.5 animate-pulse-dot rounded-full bg-current" aria-hidden />}
      {meta.label}
    </span>
  );
}

const PLATFORM_NAMES: Record<string, string> = {
  instagram: "Instagram",
  facebook: "Facebook",
  tiktok: "TikTok",
  youtube: "YouTube",
  linkedin: "LinkedIn",
  pinterest: "Pinterest",
  x: "X",
};

export function platformName(p: string): string {
  return PLATFORM_NAMES[p] ?? p;
}

export function contentTypeName(t: string): string {
  const names: Record<string, string> = {
    post: "Post",
    carousel: "Carousel",
    reel: "Reel",
    short: "Short",
    story: "Story",
    video: "Video",
  };
  return names[t] ?? t.replaceAll("_", " ");
}
