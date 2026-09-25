import { Plus } from "lucide-react";

/** Native <details> accordion: works without JavaScript and is fully keyboard accessible. */
export function FaqList({ items }: { items: { q: string; a: string }[] }) {
  return (
    <div className="divide-y divide-line border-y border-line">
      {items.map((item) => (
        <details key={item.q} className="group py-1">
          <summary className="flex cursor-pointer list-none items-start justify-between gap-6 py-4 text-lg font-medium [&::-webkit-details-marker]:hidden">
            {item.q}
            <Plus className="mt-1 size-5 shrink-0 text-muted transition-transform duration-200 group-open:rotate-45" aria-hidden />
          </summary>
          <p className="max-w-3xl pb-5 text-muted">{item.a}</p>
        </details>
      ))}
    </div>
  );
}

export function faqLd(items: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((i) => ({ "@type": "Question", name: i.q, acceptedAnswer: { "@type": "Answer", text: i.a } })),
  };
}
