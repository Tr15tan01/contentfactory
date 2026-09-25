import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Container } from "./section";

export function CtaBand({
  title = "Tell us about your business once.",
  text = "Your agent drafts a strategy and a first week of posts in minutes. You approve what goes out.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <section className="bg-[#102326] py-20 text-[#e6eeec] dark:bg-surface sm:py-24">
      <Container className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="grid max-w-2xl gap-4">
          <h2 className="display text-4xl sm:text-5xl">{title}</h2>
          <p className="text-lg text-[#b5c6c3]">{text}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg" className="bg-[#4fc1b1] text-[#07201e] hover:bg-[#6fd3c4]">
            <Link href="/register">Start free</Link>
          </Button>
          <Button asChild size="lg" variant="ghost" className="text-[#e6eeec] ring-1 ring-inset ring-[#2f4a4d] hover:bg-[#13272a]">
            <Link href="/pricing">Compare plans</Link>
          </Button>
        </div>
      </Container>
    </section>
  );
}
