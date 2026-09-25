"use client";

import * as React from "react";
import { Dialog as Primitive } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = Primitive.Root;
export const DialogTrigger = Primitive.Trigger;
export const DialogClose = Primitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
  side,
  ...props
}: React.ComponentProps<typeof Primitive.Content> & { title: string; description?: string; side?: "left" }) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-[rgb(8_20_22/55%)] backdrop-blur-[2px]" />
      <Primitive.Content
        className={cn(
          "fixed z-50 bg-surface text-ink shadow-[var(--shadow-frame)] ring-1 ring-line focus:outline-none",
          side === "left"
            ? "inset-y-0 left-0 w-[min(20rem,88vw)] p-4"
            : "left-1/2 top-1/2 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-frame)] p-6",
          className,
        )}
        {...props}
      >
        <Primitive.Title className={cn(side === "left" ? "sr-only" : "text-lg font-semibold")}>{title}</Primitive.Title>
        {description ? (
          <Primitive.Description className="mt-1.5 text-sm text-muted">{description}</Primitive.Description>
        ) : (
          <Primitive.Description className="sr-only">{title}</Primitive.Description>
        )}
        {children}
        <Primitive.Close
          className="absolute right-3 top-3 grid size-8 place-items-center rounded-md text-muted hover:bg-sunk hover:text-ink"
          aria-label="Close"
        >
          <X className="size-4" />
        </Primitive.Close>
      </Primitive.Content>
    </Primitive.Portal>
  );
}
