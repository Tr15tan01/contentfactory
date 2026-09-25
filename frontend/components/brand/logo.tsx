import Link from "next/link";
import { cn } from "@/lib/utils";

/** The mark is the product loop: an open ring with work moving through the gap. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("size-7", className)}>
      <path
        d="M24.5 9.2A11 11 0 1 0 27 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
        className="text-lab"
      />
      <path d="M11 16h8" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" className="text-ink" />
      <circle cx="27" cy="9.6" r="3.1" className="fill-marker" />
    </svg>
  );
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("group inline-flex items-center gap-2 text-ink", className)} aria-label="ContentFactory home">
      <LogoMark />
      <span className="display text-[1.35rem] leading-none tracking-tight">ContentFactory</span>
    </Link>
  );
}
