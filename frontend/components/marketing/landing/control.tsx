import { Bell, Check, Pencil, RefreshCw, ShieldCheck, X } from "lucide-react";
import { Container, SectionHeading } from "../section";
import { PhotoTile } from "../photo-tile";

const checks = [
  "The post is approved (unless you've turned approval off)",
  "The account is connected and its access is valid",
  "The format suits the platform (Reels need a video, and so on)",
  "Captions and hashtags fit the platform's limits",
  "The media file is valid and reachable",
  "Drafts using words or topics you've blocked are flagged for you",
];

export function Control() {
  return (
    <section className="border-t border-line bg-surface py-20 sm:py-28">
      <Container className="grid items-start gap-14 lg:grid-cols-[1fr_minmax(0,27rem)] lg:gap-20">
        <div className="grid gap-10">
          <SectionHeading title="Nothing goes out without your say.">
            <p>
              By default every post waits for your approval. You get a reminder before it&apos;s due: 24 hours ahead,
              6 hours, 1 hour, or not at all. If you haven&apos;t approved it, it doesn&apos;t publish.
            </p>
          </SectionHeading>
          <div className="grid gap-4">
            <h3 className="flex items-center gap-2 text-lg font-semibold">
              <ShieldCheck className="size-5 text-lab" aria-hidden /> Checked before it goes out
            </h3>
            <p className="max-w-xl text-muted">
              On Business and Agency plans you can turn approval off and let approved-by-default posts publish on their
              own. Either way, every post is checked before it goes out, and anything that fails is held back with the
              reason, never quietly dropped.
            </p>
            <ul className="grid gap-x-8 gap-y-2.5 sm:grid-cols-2">
              {checks.map((c) => (
                <li key={c} className="flex items-start gap-2.5 text-sm">
                  <Check className="mt-0.5 size-4 shrink-0 text-lab" aria-hidden />
                  {c}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <figure className="rounded-[var(--radius-frame)] bg-paper p-4 ring-1 ring-line" aria-label="Example approval notification">
          <div className="grid gap-4 rounded-[var(--radius-card)] bg-surface p-4 shadow-[var(--shadow-frame)] ring-1 ring-line">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-marker-soft text-ink dark:text-marker">
                <Bell className="size-4" aria-hidden />
              </span>
              <div>
                <p className="font-semibold leading-snug">Your 6:00 PM Instagram post is ready</p>
                <p className="text-sm text-muted">Due today. Approve it to keep the slot.</p>
              </div>
            </div>
            <div className="grid grid-cols-[5.5rem_1fr] gap-3">
              <PhotoTile kind="latte" className="aspect-square" />
              <p className="text-sm leading-snug">
                5 mistakes people make when ordering a flat white, and what to ask for instead.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm font-medium">
              <span className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-lab text-on-lab">
                <Check className="size-3.5" aria-hidden /> Approve
              </span>
              <span className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--radius-control)] ring-1 ring-line-strong">
                <Pencil className="size-3.5" aria-hidden /> Edit
              </span>
              <span className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--radius-control)] ring-1 ring-line-strong">
                <RefreshCw className="size-3.5" aria-hidden /> Regenerate
              </span>
              <span className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--radius-control)] text-muted ring-1 ring-line-strong">
                <X className="size-3.5" aria-hidden /> Reject
              </span>
            </div>
          </div>
          <figcaption className="px-1 pt-3 text-xs text-muted">Shown on your dashboard, and by email if you turn it on.</figcaption>
        </figure>
      </Container>
    </section>
  );
}
