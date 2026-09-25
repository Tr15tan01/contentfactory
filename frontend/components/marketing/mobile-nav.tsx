"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/brand/logo";
import { mainNav, productNav } from "@/lib/site";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="ml-auto lg:hidden sm:ml-0" aria-label="Open menu">
          <Menu className="size-5" />
        </Button>
      </DialogTrigger>
      <DialogContent side="left" title="Menu" className="flex flex-col gap-6 overflow-y-auto">
        <Logo />
        <nav aria-label="Mobile" className="grid gap-5 text-base">
          <div className="grid gap-2">
            <p className="text-sm text-muted">Product</p>
            {productNav.map((item) => (
              <Link key={item.href} href={item.href} onClick={close} className="py-1">
                {item.label}
              </Link>
            ))}
          </div>
          <div className="grid gap-2 border-t border-line pt-5">
            {mainNav.map((item) => (
              <Link key={item.href} href={item.href} onClick={close} className="py-1">
                {item.label}
              </Link>
            ))}
          </div>
        </nav>
        <div className="mt-auto grid gap-2">
          <Button asChild size="lg">
            <Link href="/register" onClick={close}>Start free</Link>
          </Button>
          <Button asChild variant="secondary" size="lg">
            <Link href="/login" onClick={close}>Sign in</Link>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
