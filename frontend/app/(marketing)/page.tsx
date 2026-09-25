import Link from "next/link";
import { Hero } from "@/components/marketing/landing/hero";
import { Loop } from "@/components/marketing/landing/loop";
import { CalendarShowcase } from "@/components/marketing/landing/calendar-showcase";
import { Team } from "@/components/marketing/landing/team";
import { MediaFirst } from "@/components/marketing/landing/media";
import { Intelligence } from "@/components/marketing/landing/intelligence";
import { Control } from "@/components/marketing/landing/control";
import { PricingTable } from "@/components/marketing/pricing-table";
import { CtaBand } from "@/components/marketing/cta-band";
import { Container, SectionHeading } from "@/components/marketing/section";
import { JsonLd } from "@/components/marketing/json-ld";
import { organizationLd, pageMetadata, softwareLd } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "ContentFactory — Your AI Marketing Team, On Autopilot",
  description:
    "Plan, create, publish, and improve your business content with an AI marketing agent that learns what works for your business. Free plan available.",
  path: "/",
});

export default function HomePage() {
  return (
    <>
      <JsonLd data={[organizationLd, softwareLd]} />
      <Hero />
      <Loop />
      <CalendarShowcase />
      <Team />
      <MediaFirst />
      <Intelligence />
      <Control />
      <section className="border-t border-line py-20 sm:py-28">
        <Container className="grid gap-12">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <SectionHeading title="Clear limits. No surprise bills.">
              <p>Every plan has monthly quotas for AI work, so you always know what you&apos;re paying for.</p>
            </SectionHeading>
            <Link href="/pricing" className="text-sm font-medium text-lab underline-offset-4 hover:underline">
              See everything in each plan
            </Link>
          </div>
          <PricingTable compact />
        </Container>
      </section>
      <CtaBand />
    </>
  );
}
