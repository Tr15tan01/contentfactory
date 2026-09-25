import { Check, Minus } from "lucide-react";
import { PageHeader } from "@/components/marketing/page-header";
import { Container } from "@/components/marketing/section";
import { PricingTable } from "@/components/marketing/pricing-table";
import { FaqList, faqLd } from "@/components/marketing/faq-list";
import { CtaBand } from "@/components/marketing/cta-band";
import { JsonLd } from "@/components/marketing/json-ld";
import { faqGroups } from "@/content/faq";
import { PLANS, type PlanLimits } from "@/lib/plans";
import { pageMetadata, softwareLd } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Pricing",
  description:
    "ContentFactory plans from $0 to $99 a month, with clear monthly limits for AI content, images and video. Start free, no card required.",
  path: "/pricing",
});

type Row = { label: string; value: (p: PlanLimits) => string | boolean };

const rows: { group: string; rows: Row[] }[] = [
  {
    group: "Monthly limits",
    rows: [
      { label: "Businesses", value: (p) => String(p.businesses) },
      { label: "Social accounts", value: (p) => String(p.socialAccounts) },
      { label: "AI content generations", value: (p) => String(p.aiContent) },
      { label: "Image generations", value: (p) => String(p.images) },
      { label: "AI video credits", value: (p) => String(p.videoCredits) },
      { label: "Scheduled posts", value: (p) => p.scheduledPosts.toLocaleString("en-US") },
    ],
  },
  {
    group: "Features",
    rows: [
      { label: "Content calendar and approvals", value: () => true },
      { label: "Social publishing after approval", value: () => true },
      { label: "Marketing Intelligence", value: (p) => (p.id === "free" ? "Limited" : true) },
      { label: "Experiments", value: (p) => ({ none: false, basic: "Basic", full: true, advanced: "Advanced" })[p.experiments] },
      { label: "Publishing without approval", value: (p) => p.autoPublish },
      { label: "Research agent (coming soon)", value: (p) => p.researchAgent },
      { label: "Client workspaces", value: (p) => p.id === "agency" },
      { label: "Priority processing", value: (p) => p.priorityProcessing },
    ],
  },
];

function Cell({ value }: { value: string | boolean }) {
  if (value === true) return <Check className="size-4 text-lab" aria-label="Included" />;
  if (value === false) return <Minus className="size-4 text-faint" aria-label="Not included" />;
  return <span className="numeric">{value}</span>;
}

const billingFaq = faqGroups.find((g) => g.title === "Plans and billing")?.items ?? [];

export default function PricingPage() {
  return (
    <>
      <JsonLd data={[softwareLd, faqLd(billingFaq)]} />
      <PageHeader
        title="Pricing that stays predictable"
        intro="Every plan has clear monthly limits for AI work. Nothing is unlimited, so nothing surprises you on your bill."
      />
      <Container className="py-14 sm:py-16">
        <PricingTable />
        <p className="mt-5 text-sm text-muted">
          Prices in USD, billed monthly through Paddle. Sales tax or VAT is added where it applies.
        </p>
      </Container>

      <section className="border-t border-line bg-surface py-16 sm:py-20">
        <Container className="grid gap-8">
          <h2 className="display text-3xl sm:text-4xl">Compare plans</h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
              <caption className="sr-only">Plan comparison</caption>
              <thead>
                <tr className="border-b border-line-strong">
                  <th scope="col" className="w-2/5 py-3 pr-4 font-medium text-muted">Plan</th>
                  {PLANS.map((p) => (
                    <th key={p.id} scope="col" className="py-3 pr-4 text-base font-semibold">
                      {p.name}
                      <span className="block text-sm font-normal text-muted">${p.priceUsd} / month</span>
                    </th>
                  ))}
                </tr>
              </thead>
              {rows.map((group) => (
                <tbody key={group.group}>
                  <tr>
                    <th scope="colgroup" colSpan={5} className="pb-2 pt-8 text-base font-semibold">{group.group}</th>
                  </tr>
                  {group.rows.map((row) => (
                    <tr key={row.label} className="border-b border-line">
                      <th scope="row" className="py-3 pr-4 font-normal">{row.label}</th>
                      {PLANS.map((p) => (
                        <td key={p.id} className="py-3 pr-4">
                          <Cell value={row.value(p)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </div>
        </Container>
      </section>

      <section className="py-16 sm:py-20">
        <Container className="grid gap-10 lg:grid-cols-[minmax(0,22rem)_1fr] lg:gap-16">
          <div className="grid content-start gap-4">
            <h2 className="display text-3xl">How AI limits work</h2>
            <p className="text-muted">
              Each AI task uses your monthly allowance when it succeeds. If a task fails, the reserved allowance is
              returned. Repeating an identical request reuses the earlier result instead of charging again.
            </p>
          </div>
          <FaqList items={billingFaq} />
        </Container>
      </section>
      <CtaBand title="Start on Free. Upgrade when it's earning its keep." />
    </>
  );
}
