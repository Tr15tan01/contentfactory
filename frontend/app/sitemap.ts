import type { MetadataRoute } from "next";
import { posts } from "@/content/blog";
import { featurePages } from "@/content/features";
import { absoluteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const fixed = ["/", "/features", "/pricing", "/about", "/faq", "/contact", "/blog", "/terms", "/privacy"];
  return [
    ...fixed.map((path) => ({ url: absoluteUrl(path), changeFrequency: "monthly" as const, priority: path === "/" ? 1 : 0.6 })),
    ...featurePages.map((p) => ({ url: absoluteUrl(`/${p.slug}`), changeFrequency: "monthly" as const, priority: 0.8 })),
    ...posts.map((p) => ({ url: absoluteUrl(`/blog/${p.slug}`), lastModified: p.date, changeFrequency: "yearly" as const, priority: 0.5 })),
  ];
}
