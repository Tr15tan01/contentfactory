"use client";

import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { productNav } from "@/lib/site";

export function ProductMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="inline-flex items-center gap-1 rounded-md px-3 py-2 text-sm text-muted outline-none transition-colors hover:text-ink data-[state=open]:text-ink">
        Product <ChevronDown className="size-3.5" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        {productNav.map((item) => (
          <DropdownMenuItem key={item.href} asChild>
            <Link href={item.href} className="grid gap-0.5">
              <span className="font-medium text-ink">{item.label}</span>
              <span className="text-xs text-muted">{item.blurb}</span>
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/features" className="text-lab">
            All features
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
