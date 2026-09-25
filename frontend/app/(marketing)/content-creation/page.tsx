import { FeaturePage } from "@/components/marketing/feature-page";
import { featureBySlug } from "@/content/features";
import { pageMetadata } from "@/lib/seo";

const page = featureBySlug("content-creation");

export const metadata = pageMetadata({ title: page.metaTitle, description: page.metaDescription, path: "/content-creation" });

export default function Page() {
  return <FeaturePage slug="content-creation" />;
}
