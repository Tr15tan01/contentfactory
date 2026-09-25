import * as React from "react";
import { Slot } from "radix-ui";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background-color,color,box-shadow,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-55 [&_svg]:size-[1.05em] [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-lab text-on-lab hover:bg-lab-strong",
        secondary: "bg-surface text-ink ring-1 ring-inset ring-line-strong hover:bg-sunk",
        ghost: "text-ink hover:bg-sunk",
        quiet: "text-muted hover:text-ink",
        danger: "bg-signal text-white hover:brightness-110",
        link: "text-lab underline-offset-4 hover:underline px-0 h-auto",
      },
      size: {
        sm: "h-8 rounded-[var(--radius-control)] px-3 text-sm",
        md: "h-10 rounded-[var(--radius-control)] px-4 text-sm",
        lg: "h-12 rounded-[var(--radius-control)] px-6 text-base",
        icon: "size-9 rounded-[var(--radius-control)]",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export function Button({ className, variant, size, asChild, loading, disabled, children, ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={asChild ? undefined : disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading && <Loader2 className="animate-spin" aria-hidden />}
          {children}
        </>
      )}
    </Comp>
  );
}

export { buttonVariants };
