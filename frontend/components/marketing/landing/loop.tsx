import { Container, SectionHeading } from "../section";

const stages = [
  { name: "Business", text: "You describe your business, customers, products and voice once." },
  { name: "AI Strategy", text: "Your agent sets content pillars and a weekly mix for your goals." },
  { name: "Content", text: "Captions, hooks, carousels and video scripts, using your photos first." },
  { name: "Publishing", text: "You approve; it posts at the planned time on each connected platform." },
  { name: "Analytics", text: "It collects the numbers each platform actually provides." },
  { name: "Learning", text: "What worked is saved to your business memory and shapes next week." },
];

export function Loop() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-y border-line bg-surface py-20 sm:py-24">
      <Container>
        <SectionHeading title="One loop, every week, getting sharper.">
          <p>
            ContentFactory doesn&apos;t retrain an AI model on your data. It keeps a record of what your audience
            responds to, and every new plan starts from that record.
          </p>
        </SectionHeading>

        <ol className="relative mt-14 grid gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-6">
          {/* Track connecting the stages on wide screens */}
          <div aria-hidden className="absolute left-0 right-0 top-[1.05rem] hidden h-px bg-line-strong lg:block" />
          {stages.map((stage, i) => (
            <li key={stage.name} className="relative grid content-start gap-3">
              <span
                className={
                  "numeric relative grid size-[2.1rem] place-items-center rounded-full text-sm font-semibold ring-4 ring-surface " +
                  (i === stages.length - 1 ? "bg-marker text-[#102326]" : "bg-lab text-on-lab")
                }
              >
                {i + 1}
              </span>
              <h3 className="text-lg font-semibold leading-tight">{stage.name}</h3>
              <p className="text-sm text-muted">{stage.text}</p>
            </li>
          ))}
        </ol>

        {/* The return path is the point: learning flows back into strategy. */}
        <div className="mt-10 hidden lg:block" aria-hidden>
          <svg viewBox="0 0 1000 60" className="h-12 w-full text-line-strong" preserveAspectRatio="none">
            <path
              d="M 925 4 C 925 50, 900 52, 860 52 L 230 52 C 195 52, 175 50, 175 8"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeDasharray="5 6"
              vectorEffect="non-scaling-stroke"
            />
            <path d="M 168 16 L 175 4 L 182 16" fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          </svg>
        </div>
        <p className="mt-2 text-sm text-muted lg:text-center">
          Learning feeds the next strategy. Week four is planned with everything weeks one to three taught it.
        </p>
      </Container>
    </section>
  );
}
