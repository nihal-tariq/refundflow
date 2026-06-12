import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** A pulsing placeholder used for loading states. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted/70", className)}
      {...props}
    />
  );
}
