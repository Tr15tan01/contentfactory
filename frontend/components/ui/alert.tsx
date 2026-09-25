import * as React from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";

const tones = {
  error: { cls: "bg-signal-soft text-ink [&>svg]:text-signal", Icon: AlertCircle },
  success: { cls: "bg-lab-soft text-ink [&>svg]:text-lab", Icon: CheckCircle2 },
  info: { cls: "bg-sunk text-ink [&>svg]:text-muted", Icon: Info },
} as const;

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: keyof typeof tones;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { cls, Icon } = tones[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-[var(--radius-control)] px-4 py-3 text-sm", cls, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="grid gap-0.5">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="text-muted [&_a]:text-lab [&_a]:underline">{children}</div>}
      </div>
    </div>
  );
}
