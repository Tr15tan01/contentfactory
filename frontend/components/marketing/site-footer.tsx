import Link from "next/link";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { productNav } from "@/lib/site";

const groups = [
  { title: "Product", links: [...productNav.map(({ href, label }) => ({ href, label })), { href: "/pricing", label: "Pricing" }] },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/blog", label: "Blog" },
      { href: "/faq", label: "FAQ" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/terms", label: "Terms of service" },
      { href: "/privacy", label: "Privacy policy" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto grid max-w-[76rem] gap-12 px-5 py-14 sm:px-8 lg:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="grid content-start gap-4">
          <Logo />
          <p className="max-w-xs text-sm text-muted">
            An AI marketing agent for small businesses. Tell it about your business once; it plans, creates,
            publishes and learns.
          </p>
        </div>
        {groups.map((group) => (
          <nav key={group.title} aria-label={group.title} className="grid content-start gap-2.5 text-sm">
            <p className="font-semibold text-ink">{group.title}</p>
            {group.links.map((link) => (
              <Link key={link.href} href={link.href} className="text-muted transition-colors hover:text-ink">
                {link.label}
              </Link>
            ))}
          </nav>
        ))}
      </div>
      <div className="mx-auto flex max-w-[76rem] flex-wrap items-center justify-between gap-4 border-t border-line px-5 py-6 text-sm text-muted sm:px-8">
        <p>© {new Date().getFullYear()} ContentFactory</p>
        <ThemeToggle />
      </div>
    </footer>
  );
}
