import { LegalPage } from "@/components/marketing/legal-page";
import { pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";

export const metadata = pageMetadata({ title: "Terms of Service", description: "The terms that apply when you use ContentFactory.", path: "/terms" });

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      updated="September 21, 2026"
      intro="These terms apply when you create an account or use ContentFactory. They're written to be read, not skimmed past."
      sections={[
        { title: "Your account", paragraphs: [
          "You must provide accurate information and keep your password secure. You're responsible for activity in your account and for the people you invite to your workspaces.",
          "You must be at least 18, or the age of majority where you live, and able to enter a binding contract for the business you represent.",
        ] },
        { title: "What ContentFactory does", paragraphs: [
          "ContentFactory helps you plan, create, schedule and publish marketing content, and reports performance data provided by connected platforms. AI-generated content can contain mistakes. You're responsible for reviewing content before approving it, and for content published without approval when you turn approval off.",
          "We don't guarantee any particular marketing result, reach or revenue.",
        ] },
        { title: "Connected platforms", paragraphs: [
          "When you connect a social account, you authorise us to act on your behalf within the permissions you grant. Your use of each platform remains subject to that platform's terms. Platforms can change or restrict their APIs, which may limit what ContentFactory can do.",
        ] },
        { title: "Your content", paragraphs: [
          "You own the content you upload and the content generated for you, to the extent the law allows. You grant us the licence needed to store, process and publish it on your instructions. You confirm you have the rights to anything you upload.",
          "Generated images and video are also subject to the usage terms of the model providers we use, which we list in our documentation.",
        ] },
        { title: "Acceptable use", paragraphs: [
          "You may not use ContentFactory to publish unlawful, deceptive, hateful or infringing content, to send spam, to impersonate others, or to attempt to access other customers' data or disrupt the service.",
          "We may suspend accounts that break these rules, with notice where practical.",
        ] },
        { title: "Plans, quotas and billing", paragraphs: [
          "Paid plans are billed in advance through Paddle, our merchant of record, and renew automatically until cancelled. Each plan includes monthly quotas; nothing is unlimited. Unused allowance doesn't roll over.",
          "You can cancel at any time. Your plan stays active until the end of the paid period, then moves to Free. Refunds are handled under Paddle's refund policy and applicable law.",
        ] },
        { title: "Availability and changes", paragraphs: [
          "We work to keep ContentFactory available but can't promise uninterrupted service. We may change features; if a change materially reduces what your paid plan includes, we'll tell you in advance.",
        ] },
        { title: "Liability", paragraphs: [
          "To the extent permitted by law, our total liability for any claim is limited to the amount you paid us in the 12 months before the claim. We aren't liable for indirect or consequential losses. Nothing in these terms limits liability that can't be limited by law.",
        ] },
        { title: "Ending the agreement", paragraphs: [
          "You can delete your account at any time from Security settings. We may end the agreement if you seriously or repeatedly breach these terms.",
        ] },
        { title: "Contact", paragraphs: [`Questions about these terms: ${site.supportEmail}.`] },
      ]}
    />
  );
}
