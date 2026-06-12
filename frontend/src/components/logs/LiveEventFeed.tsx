import { useState } from "react";
import { Activity } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { cn } from "@/lib/utils";
import { LogCard, type LogEntry } from "./LogCard";

type Filter = "all" | "tools";

/**
 * Reverse-chronological feed of agent log cards with an All / Tool-calls
 * filter, so operators can audit tool usage in isolation. Shared by the live
 * view and historical replay.
 */
export function LiveEventFeed({ entries }: { entries: LogEntry[] }) {
  const [filter, setFilter] = useState<Filter>("all");

  if (entries.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="Awaiting events"
        description="Agent lifecycle events will stream here as the graph executes."
      />
    );
  }

  const toolEntries = entries.filter((e) => e.toolName);
  const visible = filter === "tools" ? toolEntries : entries;
  const chips: { key: Filter; label: string }[] = [
    { key: "all", label: `All (${entries.length})` },
    { key: "tools", label: `Tool calls (${toolEntries.length})` },
  ];

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5">
        {chips.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cn(
              "rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors",
              filter === key
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <p className="px-1 py-6 text-center text-xs text-muted-foreground">
          No tool calls in this run yet.
        </p>
      ) : (
        <div className="space-y-1.5">
          {[...visible].reverse().map((entry) => (
            <LogCard key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
