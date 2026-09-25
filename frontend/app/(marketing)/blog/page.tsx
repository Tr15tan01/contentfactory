import Link from "next/link";
import { PageHeader } from "@/components/marketing/page-header";
import { Container } from "@/components/marketing/section";
import { formatDate, posts } from "@/content/blog";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Blog",
  description: "Practical social media marketing advice for small business owners: what to post, how often, and how to learn from your own results.",
  path: "/blog",
});

export default function BlogIndex() {
  const sorted = [...posts].sort((a, b) => b.date.localeCompare(a.date));
  return (
    <>
      <PageHeader title="Marketing notes for small businesses" intro="Practical advice you can use this week, without the jargon." />
      <Container className="py-12 sm:py-16">
        <ol className="divide-y divide-line border-y border-line">
          {sorted.map((post) => (
            <li key={post.slug}>
              <article className="grid gap-3 py-8 md:grid-cols-[11rem_1fr] md:gap-10">
                <p className="text-sm text-muted">
                  <time dateTime={post.date}>{formatDate(post.date)}</time>
                </p>
                <div className="grid max-w-2xl gap-2">
                  <h2 className="text-xl font-semibold leading-snug">
                    <Link href={`/blog/${post.slug}`} className="hover:text-lab">{post.title}</Link>
                  </h2>
                  <p className="text-muted">{post.description}</p>
                  <p className="text-sm text-faint">{post.readingMinutes} min read</p>
                </div>
              </article>
            </li>
          ))}
        </ol>
      </Container>
    </>
  );
}
