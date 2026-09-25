"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/settings", label: "Profile and workspace" },
  { href: "/settings/business", label: "Business" },
  { href: "/settings/security", label: "Security" },
  { href: "/settings/notifications", label: "Notifications" },
  { href: "/settings/social", label: "Social accounts" },
  { href: "/settings/billing", label: "Billing" },
];

export function SettingsTabs() {
  const pathname = usePathname();
  return (
    <nav aria-label="Settings" className="-mx-4 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0">
      <ul className="flex gap-6 text-sm">
        {tabs.map((t) => {
          const active = pathname === t.href;
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                aria-current={active ? "page" : undefined}
                className={cn("-mb-px inline-block whitespace-nowrap border-b-2 border-transparent pb-3 text-muted hover:text-ink", active && "border-lab font-medium text-ink")}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
