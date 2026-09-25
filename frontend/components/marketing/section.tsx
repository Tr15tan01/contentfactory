import { cn } from "@/lib/utils";

export function Container({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-[76rem] px-5 sm:px-8", className)}>{children}</div>;
}

export function SectionHeading({
  title,
  children,
  className,
  as: Tag = "h2",
}: {
  title: string;
  children?: React.ReactNode;
  className?: string;
  as?: "h1" | "h2";
}) {
  return (
    <div className={cn("grid max-w-2xl gap-4", className)}>
      <Tag className={cn("display text-ink", Tag === "h1" ? "text-4xl sm:text-5xl" : "text-3xl sm:text-4xl")}>{title}</Tag>
      {children && <div className="text-lg text-muted">{children}</div>}
    </div>
  );
}
