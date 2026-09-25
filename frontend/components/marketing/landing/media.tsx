import { Container, SectionHeading } from "../section";
import { PhotoTile, type PhotoKind } from "../photo-tile";

const library: { kind: PhotoKind; name: string; tags: string }[] = [
  { kind: "espresso", name: "morning-shot.jpg", tags: "espresso, bar" },
  { kind: "latte", name: "flat-white-02.jpg", tags: "milk, latte art" },
  { kind: "pastry", name: "cardamom-bun.jpg", tags: "pastries, new" },
  { kind: "coldbrew", name: "cold-brew-bar.jpg", tags: "cold brew, summer" },
];

const options = ["Always", "When relevant", "Never"];

export function MediaFirst() {
  return (
    <section className="py-20 sm:py-28">
      <Container className="grid items-center gap-14 lg:grid-cols-[1fr_1.1fr] lg:gap-20">
        <SectionHeading title="Your photos first. Generated images when they help.">
          <p>
            Upload your own photos and videos once. Your agent reads their tags and descriptions, and picks the right
            one for each post. When nothing fits, it can create a brand-aware image, which is saved to your library so
            it&apos;s never generated twice.
          </p>
        </SectionHeading>

        <div className="grid gap-4 rounded-[var(--radius-frame)] bg-surface p-4 ring-1 ring-line sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold">Prefer my media</p>
            <div className="inline-flex rounded-[var(--radius-control)] bg-sunk p-1 text-sm" aria-hidden>
              {options.map((o) => (
                <span
                  key={o}
                  className={
                    "rounded-[7px] px-3 py-1.5 " + (o === "When relevant" ? "bg-surface font-medium shadow-sm" : "text-muted")
                  }
                >
                  {o}
                </span>
              ))}
            </div>
          </div>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {library.map((m) => (
              <li key={m.name} className="grid gap-1.5">
                <PhotoTile kind={m.kind} label={m.name} className="aspect-square" />
                <span className="px-0.5 text-xs text-muted">{m.tags}</span>
              </li>
            ))}
          </ul>
        </div>
      </Container>
    </section>
  );
}
