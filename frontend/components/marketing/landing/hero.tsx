import Link from "next/link";
import { Check, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "../section";
import { PhotoTile } from "../photo-tile";

const feed = [
  { time: "04:05", agent: "Analytics agent", text: "Compared 14 posts: how-to posts earn about twice the saves" },
  { time: "09:33", agent: "Content agent", text: "Read your brand voice and what it has learned so far" },
  { time: "09:34", agent: "Content agent", text: "Wrote a how-to post in your voice: warm, direct, no jargon" },
  { time: "09:34", agent: "Content agent", text: "Used your photo cold-brew-bar.jpg instead of generating one" },
  { time: "09:35", agent: "Publishing agent", text: "Set for Thursday 18:00 on Instagram. Waiting for your approval" },
];

function AgentDesk() {
  return (
    <div
      className="relative overflow-hidden rounded-[var(--radius-frame)] bg-surface shadow-[var(--shadow-frame)] ring-1 ring-line"
      aria-label="Example: a morning of agent work for Tbilisi Coffee Lab"
      role="figure"
    >
      <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
        <span className="grid size-8 place-items-center rounded-full bg-[#5a321d] text-xs font-semibold text-[#f4e6d4]">TC</span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">Tbilisi Coffee Lab</p>
          <p className="text-xs text-muted">Thursday morning</p>
        </div>
        <span className="ml-auto inline-flex items-center gap-2 rounded-full bg-lab-soft px-2.5 py-1 text-xs font-medium text-lab">
          <span className="size-1.5 animate-pulse-dot rounded-full bg-current" aria-hidden />
          Agent working
        </span>
      </div>

      <div className="grid md:grid-cols-[1.1fr_1fr]">
        <ol className="grid content-start gap-0 border-line px-5 py-4 md:border-r">
          {feed.map((item, i) => (
            <li key={item.time} className="seq relative grid grid-cols-[3.2rem_1fr] gap-2 py-2.5" style={{ "--seq": i } as React.CSSProperties}>
              <span className="numeric pt-px text-xs text-faint">{item.time}</span>
              <div className="grid gap-0.5 border-l border-line pl-3">
                <span className="text-xs font-semibold text-lab">{item.agent}</span>
                <span className="text-sm leading-snug text-ink">{item.text}</span>
              </div>
            </li>
          ))}
        </ol>

        <div className="grid content-start gap-3 bg-sunk/60 p-4 sm:p-5">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Instagram Reel, Thu 18:00</span>
            <span className="relative inline-grid">
              <span className="seq-leave col-start-1 row-start-1 rounded-full bg-surface px-2.5 py-0.5 font-medium text-muted ring-1 ring-line" style={{ "--seq": 4 } as React.CSSProperties}>
                Draft
              </span>
              <span className="seq col-start-1 row-start-1 rounded-full bg-marker-soft px-2.5 py-0.5 font-medium text-ink dark:text-marker" style={{ "--seq": 4 } as React.CSSProperties}>
                Awaiting approval
              </span>
            </span>
          </div>
          <div className="overflow-hidden rounded-[var(--radius-card)] bg-surface ring-1 ring-line">
            <div className="relative aspect-[4/3]">
              <div className="absolute inset-0 grid place-items-center bg-sunk text-xs text-faint">Choosing a visual</div>
              <div className="seq absolute inset-0" style={{ "--seq": 3 } as React.CSSProperties}>
                <PhotoTile kind="coldbrew" label="cold-brew-bar.jpg" className="size-full rounded-none" />
              </div>
            </div>
            <div className="grid gap-1.5 p-3.5">
              <p className="seq text-[0.95rem] font-semibold leading-snug" style={{ "--seq": 2 } as React.CSSProperties}>
                3 things that ruin cold brew at home
              </p>
              <p className="seq text-sm leading-snug text-muted" style={{ "--seq": 2.4 } as React.CSSProperties}>
                We steep ours for 18 hours. Here&apos;s what we learned the hard way, so you don&apos;t have to.
              </p>
            </div>
          </div>
          <div className="seq flex gap-2" style={{ "--seq": 4.3 } as React.CSSProperties}>
            <span className="inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-lab text-sm font-medium text-on-lab">
              <Check className="size-3.5" aria-hidden /> Approve
            </span>
            <span className="inline-flex h-8 items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-surface px-3 text-sm font-medium ring-1 ring-line-strong">
              <Pencil className="size-3.5" aria-hidden /> Edit
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative overflow-hidden pb-16 pt-14 sm:pt-20">
      {/* Quiet atmosphere: a slow teal wash behind the desk, nothing more. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-40 top-40 h-[36rem] w-[52rem] rounded-full opacity-60 blur-3xl dark:opacity-40"
        style={{ background: "radial-gradient(closest-side, var(--lab-soft), transparent)" }}
      />
      <Container className="relative">
        <h1 className="display-tight max-w-5xl text-[clamp(3.1rem,8.6vw,6.6rem)] leading-[0.92] text-ink">
          Your AI Marketing Team, On Autopilot.
        </h1>
        <div className="mt-10 grid items-start gap-10 lg:grid-cols-[minmax(0,22rem)_1fr] lg:gap-14">
          <div className="grid gap-7 lg:pt-6">
            <p className="text-lg text-muted">
              Plan, create, publish, and improve your business content with an AI marketing agent that learns what
              works for your business.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link href="/register">Start Free</Link>
              </Button>
              <Button asChild size="lg" variant="secondary">
                <Link href="#how-it-works">See How It Works</Link>
              </Button>
            </div>
            <p className="text-sm text-faint">Free plan, no card needed. Nothing is published without your approval.</p>
          </div>
          <AgentDesk />
        </div>
      </Container>
    </section>
  );
}
