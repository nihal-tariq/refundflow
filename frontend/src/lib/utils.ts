import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class names, resolving conflicts (shadcn/ui convention).
 *
 * @param inputs - Class values (strings, arrays, conditional objects).
 * @returns A single deduplicated class string.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format an ISO timestamp as a short, locale-aware time (HH:MM:SS).
 *
 * @param iso - ISO-8601 timestamp string.
 * @returns A short time string, or an empty string for invalid input.
 */
export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Convert a snake_case node/event key into a Title Cased label.
 *
 * @param value - e.g. "policy_validation".
 * @returns e.g. "Policy Validation".
 */
export function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Format a number as USD currency. */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}
