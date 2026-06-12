import { type LucideIcon } from "lucide-react";

/**
 * A centered empty-state placeholder with an icon, title, and hint.
 *
 * Used wherever a panel has no data yet (no run started, no history, etc.).
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="rounded-full border border-border bg-muted/40 p-3">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-1 max-w-xs text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
