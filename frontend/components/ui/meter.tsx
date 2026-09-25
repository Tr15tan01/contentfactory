import { cn } from "@/lib/utils";

/** Usage bar for quotas: `used / limit`, never implies "unlimited". */
export function Meter({ used, limit, label, className }: { used: number; limit: number; label: string; className?: string }) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const tone = pct >= 95 ? "bg-signal" : pct >= 80 ? "bg-caution" : "bg-lab";
  return (
    <div className={cn("grid gap-1.5", className)}>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-ink">{label}</span>
        <span className="numeric text-muted">
          {used} / {limit}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-sunk"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={used}
      >
        <div className={cn("h-full rounded-full transition-[width] duration-500", tone)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
