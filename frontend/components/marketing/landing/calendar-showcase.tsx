"use client";

import { useReveal } from "@/hooks/use-reveal";
import { cn } from "@/lib/utils";
import { StatusChip } from "@/components/common/status";
import { Container, SectionHeading } from "../section";
import { PhotoTile, type PhotoKind } from "../photo-tile";

interface CalPost {
  time: string;
  platform: string;
  type: string;
  title: string;
  status: string;
  photo?: PhotoKind;
}

const week: { day: string; date: string; posts: CalPost[] }[] = [
  { day: "Mon", date: "12", posts: [{ time: "09:00", platform: "Instagram", type: "Carousel", title: "How we dial in espresso every morning", status: "published", photo: "espresso" }] },
  { day: "Tue", date: "13", posts: [{ time: "18:00", platform: "TikTok", type: "Reel", title: "Cold brew: 18 hours in 20 seconds", status: "published", photo: "coldbrew" }] },
  { day: "Wed", date: "14", posts: [{ time: "12:30", platform: "Instagram", type: "Post", title: "New on the counter: cardamom buns", status: "scheduled", photo: "pastry" }] },
  { day: "Thu", date: "15", posts: [{ time: "18:00", platform: "Instagram", type: "Reel", title: "3 mistakes people make with milk foam", status: "awaiting_approval", photo: "latte" }] },
  { day: "Fri", date: "16", posts: [{ time: "08:30", platform: "Facebook", type: "Post", title: "Our Tbilisoba weekend hours", status: "approved" }] },
  { day: "Sat", date: "17", posts: [{ time: "10:00", platform: "Instagram", type: "Story", title: "Saturday cupping at 11:00, free", status: "draft", photo: "bar" }] },
  { day: "Sun", date: "18", posts: [] },
];

function PostCard({ post, index, state }: { post: CalPost; index: number; state: "static" | "armed" | "shown" }) {
  return (
    <article
      className={cn(
        "grid gap-2 rounded-[var(--radius-card)] bg-surface p-2.5 ring-1 ring-line transition-[opacity,transform] duration-500 ease-[cubic-bezier(0.2,0.7,0.2,1)]",
        state === "armed" && "translate-y-2.5 opacity-0",
      )}
      style={{ transitionDelay: state === "shown" ? `${index * 120}ms` : undefined }}
    >
      {post.photo && <PhotoTile kind={post.photo} className="aspect-[5/4] w-full" />}
      <p className="numeric text-xs text-muted">
        {post.time} <span className="text-faint">/</span> {post.platform}
      </p>
      <p className="text-sm font-medium leading-snug">{post.title}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted">{post.type}</span>
        <StatusChip status={post.status} className="ml-auto" />
      </div>
    </article>
  );
}

export function CalendarShowcase() {
  const { ref, state } = useReveal<HTMLDivElement>();
  let index = 0;
  return (
    <section className="py-20 sm:py-28">
      <Container>
        <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
          <SectionHeading title="Next week is planned before Monday.">
            <p>
              Your agent fills the calendar around your goals and posting rhythm. Drag a post to another day, change
              the platform, or send it back for another draft.
            </p>
          </SectionHeading>
          <p className="text-sm text-muted lg:whitespace-nowrap">Example week for Tbilisi Coffee Lab</p>
        </div>

        <div ref={ref} className="mt-12 overflow-hidden rounded-[var(--radius-frame)] bg-sunk/70 p-3 ring-1 ring-line sm:p-4">
          <div className="grid gap-3 md:grid-cols-7">
            {week.map((d) => (
              <div key={d.day} className="grid content-start gap-2">
                <div className="flex items-baseline gap-2 px-1 md:block">
                  <p className="text-sm font-semibold">{d.day}</p>
                  <p className="numeric text-xs text-muted md:mt-0.5">Oct {d.date}</p>
                </div>
                {d.posts.length ? (
                  d.posts.map((p) => <PostCard key={p.title} post={p} index={index++} state={state} />)
                ) : (
                  <p className="rounded-[var(--radius-card)] border border-dashed border-line-strong px-2.5 py-4 text-xs text-muted">
                    Rest day. Your posting rhythm skips Sundays.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
