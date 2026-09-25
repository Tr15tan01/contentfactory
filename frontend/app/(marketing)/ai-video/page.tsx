import { FeaturePage } from "@/components/marketing/feature-page";
import { featureBySlug } from "@/content/features";
import { pageMetadata } from "@/lib/seo";

const page = featureBySlug("ai-video");

export const metadata = pageMetadata({ title: page.metaTitle, description: page.metaDescription, path: "/ai-video" });

export default function Page() {
  return <FeaturePage slug="ai-video" />;
}
