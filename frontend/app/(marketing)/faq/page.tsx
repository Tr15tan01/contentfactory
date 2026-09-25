import Link from "next/link";
import { PageHeader } from "@/components/marketing/page-header";
import { Container } from "@/components/marketing/section";
import { FaqList, faqLd } from "@/components/marketing/faq-list";
import { JsonLd } from "@/components/marketing/json-ld";
import { faqGroups } from "@/content/faq";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "FAQ",
  description: "Answers about ContentFactory: how the AI marketing agent works, approvals and publishing, analytics, plans and billing.",
  path: "/faq",
});

export default function FaqPage() {
  return (
    <>
      <JsonLd data={faqLd(faqGroups.flatMap((g) => g.items))} />
      <PageHeader title="Questions, answered" intro="If yours isn't here, ask us and a person will reply within one business day." >
        <p><Link href="/contact" className="font-medium text-lab underline-offset-4 hover:underline">Contact us</Link></p>
      </PageHeader>
      <Container className="grid gap-14 py-16 sm:py-20">
        {faqGroups.map((group) => (
          <section key={group.title} className="grid gap-6 lg:grid-cols-[minmax(0,16rem)_1fr] lg:gap-16">
            <h2 className="display text-2xl sm:text-3xl">{group.title}</h2>
            <FaqList items={group.items} />
          </section>
        ))}
      </Container>
    </>
  );
}
