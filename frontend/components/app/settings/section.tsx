export function SettingsSection({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-6 border-b border-line pb-10 last:border-b-0 lg:grid-cols-[minmax(0,18rem)_1fr] lg:gap-12">
      <div className="grid content-start gap-1.5">
        <h2 className="text-lg font-semibold">{title}</h2>
        {description && <p className="text-sm text-muted">{description}</p>}
      </div>
      <div className="max-w-xl">{children}</div>
    </section>
  );
}
