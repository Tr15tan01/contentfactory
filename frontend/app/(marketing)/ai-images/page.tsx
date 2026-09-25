import { FeaturePage } from "@/components/marketing/feature-page";
import { featureBySlug } from "@/content/features";
import { pageMetadata } from "@/lib/seo";

const page = featureBySlug("ai-images");

export const metadata = pageMetadata({ title: page.metaTitle, description: page.metaDescription, path: "/ai-images" });

export default function Page() {
  return <FeaturePage slug="ai-images" />;
}
