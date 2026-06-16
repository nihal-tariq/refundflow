import { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  PlayCircle,
  ShieldAlert,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatTime, humanize } from "@/lib/utils";
import type { AgentEventType } from "@/types";

/** Normalized shape shared by live (SSE) and persisted events. */
export interface LogEntry {
  id: string;
  eventType: AgentEventType;
  nodeName: string | null;
  toolName: string | null;
  message: string | null;
  payload: Record<string, unknown>;
  time: string;
  durationMs?: number | null;
}

/** Icon + color per event type. */
const META: Record<AgentEventType, { Icon: typeof CircleDot; tone: string }> = {
  execution_started: { Icon: PlayCircle, tone: "text-primary" },
  node_entered: { Icon: CircleDot, tone: "text-primary" },
  tool_called: { Icon: Wrench, tone: "text-muted-foreground" },
  tool_completed: { Icon: CheckCircle2, tone: "text-[hsl(var(--success))]" },
  validation_completed: { Icon: CheckCircle2, tone: "text-[hsl(var(--success))]" },
  retry_attempt: { Icon: AlertTriangle, tone: "text-[hsl(var(--warning))]" },
  escalation_triggered: { Icon: ShieldAlert, tone: "text-[hsl(var(--warning))]" },
  llm_response: { Icon: Sparkles, tone: "text-primary" },
  execution_completed: { Icon: CheckCircle2, tone: "text-[hsl(var(--success))]" },
  execution_failed: { Icon: AlertTriangle, tone: "text-[hsl(var(--danger))]" },
};

/** Human-readable label per event type ("LLM" reads better than humanize's "Llm"). */
function eventLabel(type: AgentEventType): string {
  return type === "llm_response" ? "LLM Response" : humanize(type);
}

/**
 * An expandable log card for one agent event.
 *
 * Collapsed: icon, event label, target, time. Expanded: the raw JSON payload —
 * exactly the "tool called → output → validation" trail the brief asks for.
 */
export function LogCard({ entry }: { entry: LogEntry }) {
  const [open, setOpen] = useState(false);
  const { Icon, tone } = META[entry.eventType];
  const hasPayload = entry.payload && Object.keys(entry.payload).length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className="rounded-lg border border-border bg-card"
    >
      <button
        onClick={() => hasPayload && setOpen((v) => !v)}
        className="flex w-full items-start gap-2.5 p-2.5 text-left"
      >
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", tone)} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium">{eventLabel(entry.eventType)}</span>
            {entry.toolName && (
              <Badge variant="outline" className="font-mono text-[10px]">
                {entry.toolName}
              </Badge>
            )}
            {typeof entry.durationMs === "number" && (
              <span className="text-[10px] text-muted-foreground">
                {entry.durationMs.toFixed(0)}ms
              </span>
            )}
          </div>
          {entry.message && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{entry.message}</p>
          )}
        </div>
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          {formatTime(entry.time)}
          {hasPayload && (
            <ChevronRight
              className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")}
            />
          )}
        </span>
      </button>
      {open && hasPayload && (
        <pre className="max-h-52 overflow-auto border-t border-border bg-muted/30 p-2.5 font-mono text-[10px] leading-relaxed text-muted-foreground">
          {JSON.stringify(entry.payload, null, 2)}
        </pre>
      )}
    </motion.div>
  );
}
