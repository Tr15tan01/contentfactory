import Link from "next/link";
import { PageHeader } from "@/components/marketing/page-header";
import { Container } from "@/components/marketing/section";
import { CtaBand } from "@/components/marketing/cta-band";
import { featurePages } from "@/content/features";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Features",
  description:
    "Everything ContentFactory does: AI strategy, content creation, media library, calendar and approvals, publishing, analytics, Marketing Intelligence and optional publishing without approval.",
  path: "/features",
});

const groups = [
  {
    title: "Plan",
    items: [
      ["Business profile and brand memory", "Products, customers, tone, goals and forbidden topics, loaded into every task."],
      ["AI content strategy", "Content pillars, a weekly plan and campaign ideas built from your goals and results."],
      ["Research agent (coming soon)", "Seasonal moments, customer questions and trends, saved so nothing is researched twice."],
    ],
  },
  {
    title: "Create",
    items: [
      ["Posts, carousels and scripts", "Hooks, captions, CTAs and scene plans shaped for each platform."],
      ["Media library", "Your photos and videos with tags, descriptions and folders. Used first when relevant."],
      ["AI images and video", "Brand-aware visuals and short videos, with the cost shown before you generate."],
    ],
  },
  {
    title: "Publish",
    items: [
      ["Content calendar", "Month, week and list views. Drag, reschedule, duplicate or pause."],
      ["Approvals and reminders", "Approve, edit, regenerate or reject, with reminders 24, 6 or 1 hour ahead."],
      ["Publishing engine", "Official APIs, each post published exactly once, automatic retries, honest failure states."],
    ],
  },
  {
    title: "Learn",
    items: [
      ["Analytics", "Reach, views, engagement, saves, shares and watch time where platforms provide them."],
      ["Marketing Intelligence", "Insights with sample size and period. No conclusions from too little data."],
      ["Experiments", "Test one thing at a time and save what wins to your memory."],
    ],
  },
  {
    title: "Run",
    items: [
      ["Publishing without approval", "Optional on Business and Agency. Every post is still checked before it goes out."],
      ["Agent activity timeline", "Every agent step in plain language, with its status and what it's waiting for."],
      ["Workspaces", "Separate businesses and client workspaces, with roles for your team."],
    ],
  },
];

export default function FeaturesPage() {
  return (
    <>
      <PageHeader
        title="Everything your marketing needs, in one loop"
        intro="Plan, create, publish and learn in one place. Each part feeds the next, so the work gets sharper every week."
      />
      <Container className="grid gap-14 py-16 sm:py-20">
        {groups.map((group) => (
          <section key={group.title} className="grid gap-6 border-t border-line pt-8 lg:grid-cols-[12rem_1fr] lg:gap-12">
            <h2 className="display text-3xl">{group.title}</h2>
            <dl className="grid gap-x-10 gap-y-7 md:grid-cols-3">
              {group.items.map(([name, text]) => (
                <div key={name} className="grid content-start gap-1.5">
                  <dt className="font-semibold">{name}</dt>
                  <dd className="text-sm text-muted">{text}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
        <section className="grid gap-6 border-t border-line pt-8 lg:grid-cols-[12rem_1fr] lg:gap-12">
          <h2 className="display text-3xl">In depth</h2>
          <ul className="grid gap-x-10 gap-y-3 md:grid-cols-3">
            {featurePages.map((p) => (
              <li key={p.slug}>
                <Link href={`/${p.slug}`} className="font-medium text-lab underline-offset-4 hover:underline">
                  {p.navLabel}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </Container>
      <CtaBand />
    </>
  );
}
