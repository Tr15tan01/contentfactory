import { PageHeader } from "@/components/marketing/page-header";
import { Container } from "@/components/marketing/section";
import { ContactForm } from "@/components/marketing/forms/contact-form";
import { pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";

export const metadata = pageMetadata({
  title: "Contact",
  description: "Talk to the ContentFactory team about sales, support, partnerships or press. We reply within one business day.",
  path: "/contact",
});

export default function ContactPage() {
  return (
    <>
      <PageHeader title="Talk to us" intro="Questions about plans, a problem with your account, or an idea for a partnership. A person reads every message." />
      <Container className="grid gap-12 py-16 sm:py-20 lg:grid-cols-[1fr_minmax(0,22rem)] lg:gap-20">
        <ContactForm />
        <aside className="grid content-start gap-3 text-sm text-muted">
          <p className="font-semibold text-ink">Prefer email?</p>
          <p>
            Write to <a className="text-lab underline" href={`mailto:${site.supportEmail}`}>{site.supportEmail}</a>.
            We reply within one business day, Monday to Friday.
          </p>
          <p>Signed-in customers can also reach support from the Help menu in their workspace.</p>
        </aside>
      </Container>
    </>
  );
}
