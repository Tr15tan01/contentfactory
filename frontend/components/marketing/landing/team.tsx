import { Container, SectionHeading } from "../section";

// The seven agents (spec §26), presented the way you'd introduce new staff.
export const agents = [
  { role: "Content", does: "Writes hooks, captions, scripts and CTAs in your brand voice, using what it has learned about your audience.", handsTo: "Creative" },
  { role: "Creative", does: "Picks your own photos when they fit, generates an image when they don't, and builds short videos from your clips.", handsTo: "Publishing" },
  { role: "Publishing", does: "Adapts each post to the platform, checks approval, and publishes on time without duplicates.", handsTo: "Analytics" },
  { role: "Analytics", does: "Collects reach, views, saves, shares and comments where each platform provides them, and spots what works.", handsTo: "Content" },
  { role: "Strategy (coming soon)", does: "Will plan the week's content pillars and campaigns on its own.", handsTo: "Content" },
  { role: "Research (coming soon)", does: "Will track seasonal moments, customer questions and trends.", handsTo: "Strategy" },
];

export function Team() {
  return (
    <section className="border-y border-line bg-surface py-20 sm:py-28">
      <Container className="grid gap-12 lg:grid-cols-[minmax(0,24rem)_1fr] lg:gap-16">
        <SectionHeading title="Specialists that hand work to each other.">
          <p>
            Each agent does one job and hands off to the next. Every step is logged on your activity timeline, so you
            can see what it did and why.
          </p>
          <p className="mt-4 text-sm">
            Every run has a step limit, a time limit, a cost ceiling and a retry limit. Agents can&apos;t loop
            forever or quietly burn through your credits.
          </p>
        </SectionHeading>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-left">
            <caption className="sr-only">The agents and what they do</caption>
            <thead>
              <tr className="border-b border-line-strong text-sm text-muted">
                <th scope="col" className="pb-3 pr-6 font-medium">Agent</th>
                <th scope="col" className="pb-3 pr-6 font-medium">What it does</th>
                <th scope="col" className="pb-3 font-medium">Hands off to</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr key={a.role} className="border-b border-line align-top">
                  <th scope="row" className="py-4 pr-6 font-semibold">{a.role}</th>
                  <td className="py-4 pr-6 text-sm text-muted">{a.does}</td>
                  <td className="py-4 text-sm text-lab">{a.handsTo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Container>
    </section>
  );
}
