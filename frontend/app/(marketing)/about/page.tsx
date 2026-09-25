import { PageHeader } from "@/components/marketing/page-header";
import { Container } from "@/components/marketing/section";
import { CtaBand } from "@/components/marketing/cta-band";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "About",
  description: "Why we're building ContentFactory: marketing help for small businesses that is honest about what it does and what it knows.",
  path: "/about",
});

const principles = [
  ["Real numbers or none", "We never estimate a metric a platform didn't report, and we never show a post as published unless the platform confirmed it."],
  ["You stay in charge", "Nothing is posted without your approval unless you turn approval off yourself."],
  ["No unlimited promises", "AI work costs money to run. Every plan has clear limits, and you always see what you've used."],
  ["Your data works for you", "Your business memory is used for your tasks only. It isn't used to train models, and you can edit or delete it."],
];

export default function AboutPage() {
  return (
    <>
      <PageHeader
        title="Marketing help for the people who run the shop"
        intro="Small business owners are told to post every day, on every platform, with good photos and clever captions, while also running the business. Agencies cost more than most can afford. Generic AI tools hand you a blank box and wait."
      />
      <Container className="grid gap-16 py-16 sm:py-20 lg:grid-cols-[minmax(0,22rem)_1fr]">
        <h2 className="display text-3xl">What we&apos;re building</h2>
        <div className="prose-cf text-lg">
          <p>
            ContentFactory is an AI marketing employee. It learns your business once, plans your content, writes and
            prepares the posts, publishes them when you approve, and learns from what actually happens.
          </p>
          <p>
            The goal isn&apos;t more content. It&apos;s better content for your customers, made with less of your
            time, and a clearer picture of what brings people through your door.
          </p>
        </div>
      </Container>
      <section className="border-t border-line bg-surface py-16 sm:py-20">
        <Container className="grid gap-10">
          <h2 className="display text-3xl sm:text-4xl">How we work</h2>
          <dl className="grid gap-x-12 gap-y-10 md:grid-cols-2">
            {principles.map(([title, text]) => (
              <div key={title} className="grid gap-2 border-t border-line pt-5">
                <dt className="text-lg font-semibold">{title}</dt>
                <dd className="text-muted">{text}</dd>
              </div>
            ))}
          </dl>
        </Container>
      </section>
      <CtaBand />
    </>
  );
}
