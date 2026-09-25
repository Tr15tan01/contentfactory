import {
  Bot,
  CalendarDays,
  ChartColumn,
  FileText,
  Images,
  LayoutDashboard,
  Lightbulb,
  Settings,
  Share2,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  match?: string[];
}

export const appNav: NavItem[][] = [
  [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/content", label: "Content", icon: FileText },
    { href: "/calendar", label: "Calendar", icon: CalendarDays },
    { href: "/media", label: "Media", icon: Images },
  ],
  [
    { href: "/agent", label: "Agent", icon: Bot },
    { href: "/analytics", label: "Analytics", icon: ChartColumn, match: ["/workspace/analytics"] },
    { href: "/insights", label: "Insights", icon: Lightbulb, match: ["/intelligence"] },
  ],
  [
    { href: "/settings/social", label: "Social accounts", icon: Share2 },
    { href: "/settings", label: "Settings", icon: Settings },
  ],
];

export function isActive(item: NavItem, pathname: string): boolean {
  if (item.href === "/settings") {
    return pathname.startsWith("/settings") && !pathname.startsWith("/settings/social");
  }
  const prefixes = [item.href, ...(item.match ?? [])];
  return prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
