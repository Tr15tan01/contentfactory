import { Container, SectionHeading } from "../section";

// Numbers match the development seed for Tbilisi Coffee Lab, where the insight is computed
// from seeded metrics rather than typed in. Labelled as an example on the page.
const bars = [
  { label: "Educational", saves: 34, posts: 8 },
  { label: "Promotional", saves: 18, posts: 6 },
];

const metrics = [
  { name: "Reach", ig: "1,240", fb: "860" },
  { name: "Saves", ig: "41", fb: null },
  { name: "Shares", ig: "17", fb: "9" },
  { name: "Watch time", ig: "3.1 h", fb: null },
];

export function Intelligence() {
  const max = Math.max(...bars.map((b) => b.saves));
  return (
    <section className="py-20 sm:py-28">
      <Container className="grid gap-14 lg:grid-cols-2 lg:gap-20">
        <div className="grid content-start gap-10">
          <SectionHeading title="It learns from your numbers, not from guesses.">
            <p>
              Marketing Intelligence compares what you published against how it performed. Every insight shows its
              sample size and time period, and small samples don&apos;t get conclusions.
            </p>
          </SectionHeading>
          <figure className="grid gap-5 rounded-[var(--radius-frame)] bg-surface p-6 ring-1 ring-line">
            <figcaption className="text-sm text-muted">What your agent learned, example business</figcaption>
            <p className="text-xl font-medium leading-snug">
              <span className="marker">Educational posts averaged 34 saves versus 18 for promotional posts (+87%).</span>
            </p>
            <div className="grid gap-3" role="img" aria-label="Average saves: educational 34, promotional 18">
              {bars.map((b) => (
                <div key={b.label} className="grid grid-cols-[6.5rem_1fr_2.5rem] items-center gap-3 text-sm">
                  <span className="text-muted">{b.label}</span>
                  <span className="h-3 rounded-full bg-sunk">
                    <span
                      className={"block h-full rounded-full " + (b.label === "Educational" ? "bg-lab" : "bg-line-strong")}
                      style={{ width: `${(b.saves / max) * 100}%` }}
                    />
                  </span>
                  <span className="numeric text-right font-medium">{b.saves}</span>
                </div>
              ))}
            </div>
            <dl className="grid grid-cols-3 gap-4 border-t border-line pt-4 text-sm">
              <div>
                <dt className="text-muted">Sample</dt>
                <dd className="numeric font-medium">14 posts</dd>
              </div>
              <div>
                <dt className="text-muted">Period</dt>
                <dd className="font-medium">Last 30 days</dd>
              </div>
              <div>
                <dt className="text-muted">Platform</dt>
                <dd className="font-medium">Instagram</dd>
              </div>
            </dl>
          </figure>
        </div>

        <div className="grid content-start gap-6 lg:pt-44">
          <h3 className="text-xl font-semibold">If a platform doesn&apos;t report it, we don&apos;t invent it.</h3>
          <p className="text-muted">
            Platforms expose different metrics. Where a number isn&apos;t available, the report says so instead of
            filling the gap with an estimate.
          </p>
          <div className="overflow-hidden rounded-[var(--radius-card)] ring-1 ring-line">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Metrics available per platform for one post</caption>
              <thead className="bg-sunk text-muted">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Metric</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Instagram</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Facebook</th>
                </tr>
              </thead>
              <tbody className="bg-surface">
                {metrics.map((m) => (
                  <tr key={m.name} className="border-t border-line">
                    <th scope="row" className="px-4 py-2.5 font-medium">{m.name}</th>
                    <td className="numeric px-4 py-2.5">{m.ig}</td>
                    <td className="px-4 py-2.5">
                      {m.fb ?? <span className="text-xs text-muted">Not available from this platform</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Container>
    </section>
  );
}
