import type { Metadata } from "next";
import { absoluteUrl, site } from "./site";
import { PLANS } from "./plans";

/** Page metadata with canonical, Open Graph and X/Twitter cards filled consistently. */
export function pageMetadata({
  title,
  description,
  path,
  type = "website",
  publishedTime,
}: {
  title: string;
  description: string;
  path: string;
  type?: "website" | "article";
  publishedTime?: string;
}): Metadata {
  const url = absoluteUrl(path);
  return {
    title: path === "/" ? { absolute: title } : title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, siteName: site.name, type, ...(publishedTime ? { publishedTime } : {}) },
    twitter: { card: "summary_large_image", title, description },
  };
}

export const organizationLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: site.name,
  url: site.url,
  logo: absoluteUrl("/icon.svg"),
  email: site.supportEmail,
};

export const softwareLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: site.name,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description: site.description,
  url: site.url,
  offers: PLANS.map((p) => ({
    "@type": "Offer",
    name: p.name,
    price: p.priceUsd.toFixed(2),
    priceCurrency: "USD",
    ...(p.priceUsd > 0
      ? { priceSpecification: { "@type": "UnitPriceSpecification", price: p.priceUsd.toFixed(2), priceCurrency: "USD", unitCode: "MON" } }
      : {}),
  })),
};

export function breadcrumbLd(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}
