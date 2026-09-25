import Link from "next/link";
import { Check } from "lucide-react";
import { featureBySlug } from "@/content/features";
import { breadcrumbLd } from "@/lib/seo";
import { Button } from "@/components/ui/button";
import { Container } from "./section";
import { PageHeader } from "./page-header";
import { FaqList, faqLd } from "./faq-list";
import { CtaBand } from "./cta-band";
import { JsonLd } from "./json-ld";

export function FeaturePage({ slug }: { slug: string }) {
  const page = featureBySlug(slug);
  const related = page.related.map(featureBySlug);
  return (
    <>
      <JsonLd
        data={[
          breadcrumbLd([
            { name: "Home", path: "/" },
            { name: "Features", path: "/features" },
            { name: page.navLabel, path: `/${page.slug}` },
          ]),
          faqLd(page.faq),
        ]}
      />
      <PageHeader
        title={page.h1}
        intro={page.intro}
        crumbs={[
          { href: "/", label: "Home" },
          { href: "/features", label: "Features" },
          { href: `/${page.slug}`, label: page.navLabel },
        ]}
      >
        <div className="flex flex-wrap gap-3 pt-2">
          <Button asChild size="lg">
            <Link href="/register">Start free</Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link href="/pricing">See pricing</Link>
          </Button>
        </div>
      </PageHeader>

      <Container className="grid gap-16 py-16 sm:py-20">
        {page.sections.map((section) => (
          <section key={section.title} className="grid gap-5 lg:grid-cols-[minmax(0,22rem)_1fr] lg:gap-16">
            <h2 className="display text-2xl sm:text-3xl">{section.title}</h2>
            <div className="grid max-w-2xl content-start gap-5">
              <p className="text-lg text-muted">{section.body}</p>
              {section.points && (
                <ul className="grid gap-2.5">
                  {section.points.map((point) => (
                    <li key={point} className="flex gap-3">
                      <Check className="mt-1 size-4 shrink-0 text-lab" aria-hidden />
                      {point}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        ))}
      </Container>

      <section className="border-t border-line bg-surface py-16 sm:py-20">
        <Container className="grid gap-8 lg:grid-cols-[minmax(0,22rem)_1fr] lg:gap-16">
          <h2 className="display text-2xl sm:text-3xl">Questions</h2>
          <FaqList items={page.faq} />
        </Container>
      </section>

      <section className="py-16">
        <Container className="grid gap-6">
          <h2 className="text-lg font-semibold">Related</h2>
          <ul className="grid gap-px overflow-hidden rounded-[var(--radius-card)] bg-line ring-1 ring-line md:grid-cols-3">
            {related.map((r) => (
              <li key={r.slug} className="bg-surface">
                <Link href={`/${r.slug}`} className="grid h-full gap-1 p-5 transition-colors hover:bg-sunk">
                  <span className="font-medium">{r.navLabel}</span>
                  <span className="text-sm text-muted">{r.metaTitle}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Container>
      </section>
      <CtaBand />
    </>
  );
}
