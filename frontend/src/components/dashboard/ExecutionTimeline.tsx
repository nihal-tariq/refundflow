import { motion } from "framer-motion";
import {
  CheckCircle2,
  CreditCard,
  Loader2,
  ScrollText,
  ShieldAlert,
  User,
  Circle,
} from "lucide-react";
import { deriveNodeStatuses, type NodeStatus } from "@/lib/timeline";
import { cn, humanize } from "@/lib/utils";
import { GRAPH_NODES, type AgentEvent, type GraphNode, type PersistedEvent } from "@/types";

/** Icon per graph node. */
const NODE_ICONS: Record<GraphNode, typeof User> = {
  customer_lookup: User,
  order_lookup: CreditCard,
  policy_validation: ScrollText,
  fraud_check: ShieldAlert,
  decision: CheckCircle2,
};

/** Status dot/icon for a node. */
function StatusIcon({ status, Icon }: { status: NodeStatus; Icon: typeof User }) {
  if (status === "active")
    return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (status === "done")
    return <Icon className="h-4 w-4 text-[hsl(var(--success))]" />;
  return <Circle className="h-4 w-4 text-muted-foreground/40" />;
}

/**
 * Vertical node-by-node execution timeline.
 *
 * Renders the canonical graph order and lights nodes up as the event stream
 * (live or replayed) reports entry/completion.
 */
export function ExecutionTimeline({
  events,
}: {
  events: (AgentEvent | PersistedEvent)[];
}) {
  const statuses = deriveNodeStatuses(events);

  return (
    <div className="space-y-0.5">
      {GRAPH_NODES.map((node, index) => {
        const status = statuses[node];
        const Icon = NODE_ICONS[node];
        return (
          <div key={node} className="flex items-stretch gap-3">
            <div className="flex flex-col items-center">
              <motion.div
                animate={{ scale: status === "active" ? [1, 1.12, 1] : 1 }}
                transition={{ duration: 1, repeat: status === "active" ? Infinity : 0 }}
                className={cn(
                  "grid h-8 w-8 place-items-center rounded-full border",
                  status === "pending"
                    ? "border-border bg-muted/30"
                    : status === "active"
                      ? "border-primary bg-primary/15"
                      : "border-[hsl(var(--success)/0.4)] bg-[hsl(var(--success)/0.12)]",
                )}
              >
                <StatusIcon status={status} Icon={Icon} />
              </motion.div>
              {index < GRAPH_NODES.length - 1 && (
                <div
                  className={cn(
                    "w-px flex-1",
                    status === "done" ? "bg-[hsl(var(--success)/0.4)]" : "bg-border",
                  )}
                />
              )}
            </div>
            <div className={cn("pb-4", status === "pending" && "opacity-50")}>
              <p className="text-sm font-medium">{humanize(node)}</p>
              <p className="text-xs capitalize text-muted-foreground">{status}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
