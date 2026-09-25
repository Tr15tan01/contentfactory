import { Logo } from "@/components/brand/logo";

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle?: React.ReactNode; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,34rem)]">
      <main id="main" className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto grid w-full max-w-[25rem] flex-1 content-center gap-8 py-12">
          <div className="grid gap-2">
            <h1 className="display text-4xl">{title}</h1>
            {subtitle && <div className="text-muted">{subtitle}</div>}
          </div>
          {children}
          {footer && <div className="text-sm text-muted">{footer}</div>}
        </div>
      </main>
      <aside className="relative hidden overflow-hidden border-l border-[#24393b] bg-[#102326] p-12 text-[#e6eeec] lg:flex lg:flex-col lg:justify-end" aria-hidden>
        <div className="absolute -right-24 -top-24 size-[28rem] rounded-full border-[3.5rem] border-[#4fc1b1]/15" />
        <div className="absolute right-24 top-40 size-8 rounded-full bg-[#e8c93a]" />
        <div className="relative grid gap-6">
          <p className="display text-[2.6rem] leading-[1.02]">Tell it about your business once. It remembers.</p>
          <div className="grid gap-2 rounded-[14px] bg-[#13272a] p-5 ring-1 ring-[#24393b]">
            <p className="text-sm text-[#9db0ae]">What your agent learned, example business</p>
            <p className="text-lg leading-snug">Posts published after 18:00 reached 41% more people than morning posts.</p>
            <p className="text-sm text-[#6f8583]">Based on 22 posts over the last 60 days</p>
          </div>
        </div>
      </aside>
    </div>
  );
}
