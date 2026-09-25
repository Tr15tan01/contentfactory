import { LegalPage } from "@/components/marketing/legal-page";
import { pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";

export const metadata = pageMetadata({ title: "Privacy Policy", description: "What data ContentFactory collects, why, and the choices you have.", path: "/privacy" });

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      updated="September 21, 2026"
      intro="What we collect, why we collect it, who we share it with, and what you can do about it."
      sections={[
        { title: "What we collect", paragraphs: [
          "Account data: your name, email address, password hash (never the password itself), time zone and sign-in history, including IP address and browser for security.",
          "Business data you provide: your business profile, brand, products, media, content and settings.",
          "Platform data: when you connect a social account, access tokens (stored encrypted) and the performance metrics the platform returns for your posts.",
          "Billing data: plan and subscription status from Paddle. We never see or store your full card number.",
        ] },
        { title: "How we use it", paragraphs: [
          "To provide the service: generating and publishing content, reporting performance, and remembering what works for your business.",
          "To keep accounts secure, prevent abuse, and meet legal obligations. To send service emails such as verification, password resets and publishing reminders you've enabled.",
        ] },
        { title: "AI processing", paragraphs: [
          "Relevant parts of your business data are sent to AI model providers to perform tasks you request. We use providers that don't train their models on API data. We don't use your data to train or fine-tune models.",
        ] },
        { title: "Who we share it with", paragraphs: [
          "Service providers who process data on our behalf: hosting, database, email delivery, AI model providers, file storage and Paddle for billing. Social platforms receive the content you publish to them. We don't sell personal data.",
        ] },
        { title: "Retention", paragraphs: [
          "We keep your data while your account is active. When you delete your account, we remove or anonymise your personal data and delete your workspaces, except where we must keep records for legal, tax or security reasons.",
        ] },
        { title: "Your rights", paragraphs: [
          "Depending on where you live, you can access, correct, export or delete your data, and object to or restrict some processing. Most of this is available in your settings; for the rest, contact us.",
        ] },
        { title: "Security", paragraphs: [
          "Passwords are hashed with Argon2id, social tokens are encrypted at rest, sessions can be reviewed and revoked from Security settings, and access within the company is limited to people who need it.",
        ] },
        { title: "Cookies", paragraphs: [
          "We use essential cookies to keep you signed in and to protect forms against cross-site request forgery. We don't use advertising cookies.",
        ] },
        { title: "Contact", paragraphs: [`Privacy questions or requests: ${site.supportEmail}.`] },
      ]}
    />
  );
}
