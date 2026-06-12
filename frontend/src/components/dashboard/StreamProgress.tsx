import { motion } from "framer-motion";
import { Loader2, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { progressFraction } from "@/lib/timeline";
import type { AgentEvent, PersistedEvent } from "@/types";
import type { RunStatus } from "@/store/useAppStore";

/** Status → badge tone/label. */
const STATUS_META: Record<RunStatus, { tone: "primary" | "success" | "danger" | "default"; label: string }> = {
  idle: { tone: "default", label: "Idle" },
  running: { tone: "primary", label: "Running" },
  completed: { tone: "success", label: "Completed" },
  failed: { tone: "danger", label: "Failed" },
};

/**
 * Header bar with a live status badge and an animated progress bar derived from
 * how many graph nodes have completed.
 */
export function StreamProgress({
  events,
  status,
}: {
  events: (AgentEvent | PersistedEvent)[];
  status: RunStatus;
}) {
  const fraction = progressFraction(events);
  const meta = STATUS_META[status];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          {status === "running" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          ) : (
            <Radio className="h-3.5 w-3.5" />
          )}
          Agent execution
        </span>
        <Badge variant={meta.tone}>{meta.label}</Badge>
      </div>
      <div
        className={cn(
          "h-1.5 overflow-hidden rounded-full transition-colors",
          status === "idle" ? "bg-transparent" : "bg-muted",
        )}
      >
        <motion.div
          className="h-full rounded-full bg-primary"
          animate={{ width: `${Math.round(fraction * 100)}%` }}
          transition={{ ease: "easeOut", duration: 0.4 }}
        />
      </div>
    </div>
  );
}
