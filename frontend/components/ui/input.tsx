import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-[var(--radius-control)] bg-surface px-3.5 text-base text-ink ring-1 ring-inset ring-line-strong transition-shadow placeholder:text-faint",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab",
        "aria-[invalid=true]:ring-signal disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-32 w-full rounded-[var(--radius-control)] bg-surface px-3.5 py-3 text-base text-ink ring-1 ring-inset ring-line-strong placeholder:text-faint",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab aria-[invalid=true]:ring-signal",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-11 w-full appearance-none rounded-[var(--radius-control)] bg-surface bg-[length:1rem] bg-[right_0.9rem_center] bg-no-repeat px-3.5 pr-9 text-base text-ink ring-1 ring-inset ring-line-strong",
        "bg-[url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2356676a' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab",
        className,
      )}
      {...props}
    />
  );
}
