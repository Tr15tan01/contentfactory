"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronsUpDown, LogOut, Menu, Plus, Shield, UserRound } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { authApi } from "@/lib/api/endpoints";
import { cn, initials } from "@/lib/utils";
import { appNav, isActive } from "./nav";
import { NotificationBell } from "./notification-bell";
import { useSession } from "./session";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useSession();
  return (
    <nav aria-label="Workspace" className="grid gap-5">
      {appNav.map((group, i) => (
        <ul key={i} className="grid gap-0.5">
          {group.map((item) => {
            const active = isActive(item, pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-sm text-muted transition-colors hover:bg-sunk hover:text-ink",
                    active && "bg-surface font-medium text-ink shadow-[0_1px_0_var(--line)] ring-1 ring-line",
                  )}
                >
                  <item.icon className={cn("size-4", active && "text-lab")} aria-hidden />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      ))}
      {user.is_superuser && (
        <Link href="/admin" onClick={onNavigate} aria-current={pathname.startsWith("/admin") ? "page" : undefined}
          className={cn("flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-sm text-muted hover:bg-sunk hover:text-ink", pathname.startsWith("/admin") && "bg-surface font-medium text-ink ring-1 ring-line")}>
          <Shield className="size-4" aria-hidden /> Admin
        </Link>
      )}
    </nav>
  );
}

function WorkspaceSwitcher() {
  const { workspace, workspaces, selectWorkspace } = useSession();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-3 rounded-[var(--radius-control)] px-2 py-2 text-left outline-none hover:bg-sunk focus-visible:ring-2 focus-visible:ring-lab">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-lab-soft text-xs font-semibold text-lab">
          {initials(workspace.name)}
        </span>
        <span className="grid min-w-0 flex-1">
          <span className="truncate text-sm font-semibold">{workspace.name}</span>
          <span className="truncate text-xs text-muted">{workspace.is_demo ? "Demo workspace" : workspace.role.charAt(0).toUpperCase() + workspace.role.slice(1)}</span>
        </span>
        <ChevronsUpDown className="size-4 text-muted" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel className="text-xs text-muted">Workspaces</DropdownMenuLabel>
        {workspaces.map((w) => (
          <DropdownMenuItem key={w.id} onSelect={() => selectWorkspace(w.id)}>
            <span className="flex-1 truncate">{w.name}</span>
            {w.id === workspace.id && <Check className="!text-lab" aria-label="Current" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          <Plus /> Add a business
          <span className="ml-auto text-xs">Soon</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu() {
  const { user } = useSession();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    await authApi.logout().catch(() => undefined);
    queryClient.clear();
    router.replace("/login");
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="grid size-9 place-items-center overflow-hidden rounded-full bg-sunk text-xs font-semibold outline-none ring-1 ring-line focus-visible:ring-2 focus-visible:ring-lab"
        aria-label="Account menu"
      >
        {user.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- remote avatar, tiny, no optimisation needed
          <img src={user.avatar_url} alt="" className="size-full object-cover" referrerPolicy="no-referrer" />
        ) : (
          initials(user.full_name ?? user.email)
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="grid">
          <span className="truncate font-medium">{user.full_name ?? "Your account"}</span>
          <span className="truncate text-xs font-normal text-muted">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings"><UserRound /> Profile and workspace</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/settings/security"><Shield /> Security</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <div className="flex items-center justify-between px-2.5 py-1.5 text-sm">
          <span className="text-muted">Theme</span>
          <ThemeToggle />
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={(e) => { e.preventDefault(); void signOut(); }} disabled={signingOut}>
          <LogOut /> {signingOut ? "Signing out" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { workspace } = useSession();
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[15.5rem_1fr]">
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 border-r border-line bg-paper px-3 py-4 lg:flex">
        <div className="px-2"><Logo href="/dashboard" /></div>
        <WorkspaceSwitcher />
        <div className="flex-1 overflow-y-auto"><NavLinks /></div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-paper/85 px-4 backdrop-blur-md sm:px-6">
          <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
            <DialogTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                <Menu className="size-5" />
              </Button>
            </DialogTrigger>
            <DialogContent side="left" title="Navigation" className="flex flex-col gap-6 overflow-y-auto bg-paper">
              <Logo href="/dashboard" />
              <WorkspaceSwitcher />
              <NavLinks onNavigate={() => setMenuOpen(false)} />
            </DialogContent>
          </Dialog>
          <p className="truncate text-sm font-medium lg:hidden">{workspace.name}</p>
          <div className="ml-auto flex items-center gap-2">
            <Button asChild size="sm" className="hidden sm:inline-flex">
              <Link href="/content/new"><Plus /> Create post</Link>
            </Button>
            <NotificationBell />
            <UserMenu />
          </div>
        </header>
        <main id="main" className="flex-1 px-4 py-6 sm:px-8 sm:py-8">{children}</main>
      </div>
    </div>
  );
}

export function ShellSkeleton() {
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[15.5rem_1fr]" aria-busy="true" aria-label="Loading your workspace">
      <aside className="hidden border-r border-line lg:block" />
      <div className="grid content-start gap-6 p-8">
        <div className="h-8 w-64 animate-pulse rounded-md bg-sunk" />
        <div className="h-24 animate-pulse rounded-xl bg-sunk" />
        <div className="grid gap-6 xl:grid-cols-2">
          <div className="h-64 animate-pulse rounded-xl bg-sunk" />
          <div className="h-64 animate-pulse rounded-xl bg-sunk" />
        </div>
      </div>
    </div>
  );
}
