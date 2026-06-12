import { Brain } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import type { ReasoningItem } from "@/lib/timeline";
import { formatTime, humanize } from "@/lib/utils";

/**
 * The agent's reasoning trail, one card per thought.
 *
 * This is where the *why* lives for operators — the customer chat only ever
 * sees the customer-safe outcome message.
 */
export function ReasoningPanel({ items }: { items: ReasoningItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        icon={Brain}
        title="No reasoning yet"
        description="The agent's step-by-step reasoning will appear here as it works."
      />
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div
          key={`${item.node}-${index}`}
          className="rounded-lg border border-border border-l-2 border-l-primary/50 bg-card p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{humanize(item.node)}</Badge>
              {item.tool && (
                <Badge variant="default" className="font-mono text-[10px]">
                  {item.tool}
                </Badge>
              )}
            </div>
            {item.time && (
              <span className="text-[10px] text-muted-foreground">
                {formatTime(item.time)}
              </span>
            )}
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
            {item.thought}
          </p>
        </div>
      ))}
    </div>
  );
}
