import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CtaBand } from "@/components/marketing/cta-band";
import { Container } from "@/components/marketing/section";
import { JsonLd } from "@/components/marketing/json-ld";
import { formatDate, postBySlug, posts, type Block } from "@/content/blog";
import { breadcrumbLd, pageMetadata } from "@/lib/seo";
import { absoluteUrl, site } from "@/lib/site";

export const dynamicParams = false;

export function generateStaticParams() {
  return posts.map((p) => ({ slug: p.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = postBySlug((await params).slug);
  if (!post) return {};
  return pageMetadata({ title: post.title, description: post.description, path: `/blog/${post.slug}`, type: "article", publishedTime: post.date });
}

function renderBlock(block: Block, i: number) {
  switch (block.type) {
    case "h2":
      return <h2 key={i}>{block.text}</h2>;
    case "ul":
      return (
        <ul key={i}>
          {block.items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      );
    default:
      return <p key={i}>{block.text}</p>;
  }
}

export default async function BlogPostPage({ params }: Props) {
  const post = postBySlug((await params).slug);
  if (!post) notFound();
  const others = posts.filter((p) => p.slug !== post.slug).slice(0, 2);
  return (
    <>
      <JsonLd
        data={[
          {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            headline: post.title,
            description: post.description,
            datePublished: post.date,
            author: { "@type": "Organization", name: site.name },
            publisher: { "@type": "Organization", name: site.name, logo: { "@type": "ImageObject", url: absoluteUrl("/icon.svg") } },
            mainEntityOfPage: absoluteUrl(`/blog/${post.slug}`),
          },
          breadcrumbLd([
            { name: "Home", path: "/" },
            { name: "Blog", path: "/blog" },
            { name: post.title, path: `/blog/${post.slug}` },
          ]),
        ]}
      />
      <article>
        <header className="border-b border-line pb-12 pt-12 sm:pt-16">
          <Container className="grid max-w-[52rem] gap-5">
            <Link href="/blog" className="text-sm text-muted hover:text-ink">Blog</Link>
            <h1 className="display-tight text-[clamp(2.3rem,5.4vw,3.8rem)] leading-[1]">{post.title}</h1>
            <p className="text-lg text-muted">{post.description}</p>
            <p className="text-sm text-faint">
              <time dateTime={post.date}>{formatDate(post.date)}</time>, {post.readingMinutes} min read
            </p>
          </Container>
        </header>
        <Container className="max-w-[52rem] py-12 sm:py-14">
          <div className="prose-cf text-[1.125rem] leading-[1.7]">{post.body.map(renderBlock)}</div>
        </Container>
      </article>
      <section className="border-t border-line py-14">
        <Container className="grid max-w-[52rem] gap-5">
          <h2 className="text-lg font-semibold">Keep reading</h2>
          <ul className="grid gap-4">
            {others.map((p) => (
              <li key={p.slug}>
                <Link href={`/blog/${p.slug}`} className="font-medium text-lab underline-offset-4 hover:underline">{p.title}</Link>
              </li>
            ))}
          </ul>
        </Container>
      </section>
      <CtaBand />
    </>
  );
}
