import { FeaturePage } from "@/components/marketing/feature-page";
import { featureBySlug } from "@/content/features";
import { pageMetadata } from "@/lib/seo";

const page = featureBySlug("analytics");

export const metadata = pageMetadata({ title: page.metaTitle, description: page.metaDescription, path: "/analytics" });

export default function Page() {
  return <FeaturePage slug="analytics" />;
}
