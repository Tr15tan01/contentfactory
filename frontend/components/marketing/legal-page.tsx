import { PageHeader } from "./page-header";
import { Container } from "./section";

export interface LegalSection {
  title: string;
  paragraphs: string[];
}

// Legal copy must be reviewed by counsel for your jurisdiction before launch (see docs/deployment.md).
export function LegalPage({ title, updated, intro, sections }: { title: string; updated: string; intro: string; sections: LegalSection[] }) {
  return (
    <>
      <PageHeader title={title} intro={intro}>
        <p className="text-sm text-muted">Last updated {updated}</p>
      </PageHeader>
      <Container className="grid gap-12 py-14 lg:grid-cols-[14rem_1fr] lg:gap-16">
        <nav aria-label="On this page" className="hidden lg:block">
          <ol className="sticky top-24 grid gap-2 text-sm text-muted">
            {sections.map((s, i) => (
              <li key={s.title}>
                <a href={`#s${i + 1}`} className="hover:text-ink">{s.title}</a>
              </li>
            ))}
          </ol>
        </nav>
        <article className="prose-cf">
          {sections.map((s, i) => (
            <section key={s.title} id={`s${i + 1}`} className="scroll-mt-24">
              <h2>{i + 1}. {s.title}</h2>
              {s.paragraphs.map((p) => (
                <p key={p.slice(0, 40)}>{p}</p>
              ))}
            </section>
          ))}
        </article>
      </Container>
    </>
  );
}
