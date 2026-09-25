"use client";

import { Alert } from "@/components/ui/alert";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function FormError({ error, title = "Not saved" }: { error: unknown; title?: string }) {
  if (!error) return null;
  const text = error instanceof ApiError ? (Object.values(error.fields)[0] ?? error.message) : "Try again.";
  return <Alert tone="error" title={title}>{text}</Alert>;
}

/** Toggle chip used for goals, tones and platforms. */
export function Toggle({ pressed, onClick, children, disabled, className }: { pressed: boolean; onClick: () => void; children: React.ReactNode; disabled?: boolean; className?: string }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "rounded-[var(--radius-control)] px-3.5 py-2.5 text-left text-sm ring-1 ring-inset ring-line-strong transition-colors hover:bg-sunk disabled:opacity-50",
        pressed && "bg-lab-soft ring-2 ring-lab hover:bg-lab-soft",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function FormActions({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">{children}</div>;
}

export function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}
