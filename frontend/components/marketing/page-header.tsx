import Link from "next/link";
import { Container } from "./section";

export function PageHeader({
  title,
  intro,
  crumbs,
  children,
}: {
  title: string;
  intro?: string;
  crumbs?: { href: string; label: string }[];
  children?: React.ReactNode;
}) {
  return (
    <header className="border-b border-line pb-14 pt-12 sm:pb-16 sm:pt-16">
      <Container className="grid gap-6">
        {crumbs && (
          <nav aria-label="Breadcrumb">
            <ol className="flex flex-wrap items-center gap-2 text-sm text-muted">
              {crumbs.map((c, i) => (
                <li key={c.href} className="flex items-center gap-2">
                  {i > 0 && <span aria-hidden className="text-faint">/</span>}
                  {i === crumbs.length - 1 ? (
                    <span aria-current="page" className="text-ink">{c.label}</span>
                  ) : (
                    <Link href={c.href} className="hover:text-ink">{c.label}</Link>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        )}
        <h1 className="display-tight max-w-4xl text-[clamp(2.5rem,6vw,4.4rem)] leading-[0.98]">{title}</h1>
        {intro && <p className="max-w-2xl text-lg text-muted">{intro}</p>}
        {children}
      </Container>
    </header>
  );
}
