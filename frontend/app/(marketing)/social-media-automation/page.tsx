import { FeaturePage } from "@/components/marketing/feature-page";
import { featureBySlug } from "@/content/features";
import { pageMetadata } from "@/lib/seo";

const page = featureBySlug("social-media-automation");

export const metadata = pageMetadata({ title: page.metaTitle, description: page.metaDescription, path: "/social-media-automation" });

export default function Page() {
  return <FeaturePage slug="social-media-automation" />;
}
