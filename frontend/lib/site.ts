export const site = {
  name: "ContentFactory",
  url: (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000").replace(/\/$/, ""),
  description:
    "An AI marketing agent for small businesses. It plans, creates, schedules, publishes and improves your social content, and learns what works for your business.",
  supportEmail: "hello@contentfactory.app",
} as const;

export function absoluteUrl(path = "/"): string {
  return `${site.url}${path.startsWith("/") ? path : `/${path}`}`;
}

export const productNav = [
  { href: "/ai-marketing-agent", label: "AI marketing agent", blurb: "An agent that plans and runs your content" },
  { href: "/content-creation", label: "Content creation", blurb: "Captions, hooks, scripts and carousels" },
  { href: "/social-media-automation", label: "Social media automation", blurb: "Calendar, approvals and publishing" },
  { href: "/analytics", label: "Analytics", blurb: "Real platform numbers, honestly reported" },
  { href: "/ai-images", label: "AI images", blurb: "Brand-aware visuals, your photos first" },
  { href: "/ai-video", label: "AI video", blurb: "Scripts, scene plans and edits" },
] as const;

export const mainNav = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" },
  { href: "/about", label: "About" },
] as const;
