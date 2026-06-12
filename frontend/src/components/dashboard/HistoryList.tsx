import { History, Loader2 } from "lucide-react";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { useSessions } from "@/hooks/useSessions";
import { cn, formatTime } from "@/lib/utils";
import type { Decision } from "@/types";

/**
 * Execution history list. Each row is a past run; clicking it selects the
 * session for trace replay in the dashboard.
 */
export function HistoryList({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (sessionId: string) => void;
}) {
  const { data, isLoading } = useSessions();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading history…
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No executions yet"
        description="Completed agent runs will appear here for replay."
      />
    );
  }

  return (
    <div className="space-y-1.5">
      {data.map((session) => (
        <button
          key={session.session_id}
          onClick={() => onSelect(session.session_id)}
          className={cn(
            "flex w-full items-center justify-between rounded-lg border p-2.5 text-left transition-colors",
            selectedId === session.session_id
              ? "border-primary/60 bg-primary/5"
              : "border-border bg-card hover:border-primary/40",
          )}
        >
          <div className="min-w-0">
            <p className="truncate font-mono text-xs">{session.session_id}</p>
            <p className="text-[11px] text-muted-foreground">
              {session.customer_id} · {session.order_id ?? "—"} ·{" "}
              {formatTime(session.created_at)}
            </p>
          </div>
          {session.final_decision ? (
            <DecisionBadge decision={session.final_decision as Decision} />
          ) : (
            <span className="text-[10px] capitalize text-muted-foreground">
              {session.status}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
