import { type HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/** Badge color variants used for tiers, statuses, and severities. */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "border-transparent bg-muted text-muted-foreground",
        primary: "border-transparent bg-primary/15 text-primary",
        success: "border-transparent bg-[hsl(var(--success)/0.15)] text-[hsl(var(--success))]",
        danger: "border-transparent bg-[hsl(var(--danger)/0.15)] text-[hsl(var(--danger))]",
        warning: "border-transparent bg-[hsl(var(--warning)/0.15)] text-[hsl(var(--warning))]",
        outline: "border-border text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

/** A small status/label pill. */
export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
