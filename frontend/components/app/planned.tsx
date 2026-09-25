import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PageTitle } from "./page-title";

/**
 * Honest placeholder for screens scheduled in a later build phase. It says what the page
 * will do and never shows fake data (product rule: no fake analytics or published states).
 */
export function PlannedPage({
  title,
  description,
  willDo,
  phase,
  primary,
}: {
  title: string;
  description: string;
  willDo: string[];
  phase: string;
  primary?: { href: string; label: string };
}) {
  return (
    <div className="mx-auto max-w-6xl">
      <PageTitle title={title} description={description} />
      <section className="grid gap-6 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface/60 p-6 sm:p-8 lg:grid-cols-[1fr_minmax(0,18rem)]">
        <div className="grid content-start gap-4">
          <h2 className="text-lg font-semibold">Being built</h2>
          <ul className="grid gap-2 text-muted">
            {willDo.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-lab" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="grid content-start gap-3 text-sm text-muted lg:border-l lg:border-line lg:pl-6">
          <p>
            Arrives in <span className="font-medium text-ink">{phase}</span> of the build plan. Nothing on this page shows placeholder data.
          </p>
          <Button asChild variant="secondary" size="sm" className="justify-self-start">
            <Link href={primary?.href ?? "/dashboard"}>{primary?.label ?? "Back to dashboard"}</Link>
          </Button>
        </div>
      </section>
    </div>
  );
}
