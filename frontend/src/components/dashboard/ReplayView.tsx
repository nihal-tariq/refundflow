import { ArrowLeft, Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LiveEventFeed } from "@/components/logs/LiveEventFeed";
import type { LogEntry } from "@/components/logs/LogCard";
import { ReasoningPanel } from "@/components/logs/ReasoningPanel";
import { useTrace } from "@/hooks/useSessions";
import {
  deriveReasoningFromEvents,
  deriveStateFromEvents,
  type ReasoningItem,
} from "@/lib/timeline";
import type { Decision } from "@/types";
import { DecisionResultCard } from "./DecisionResultCard";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { StateInspector } from "./StateInspector";

type InnerTab = "timeline" | "reasoning" | "events" | "state";

/** Extract the persisted reasoning log from a state snapshot, if present. */
function reasoningFromSnapshot(snapshot: Record<string, unknown> | undefined): ReasoningItem[] {
  const log = snapshot?.reasoning_log;
  if (!Array.isArray(log)) return [];
  return log
    .filter((e): e is Record<string, unknown> => typeof e === "object" && e !== null)
    .map((e) => ({
      node: String(e.node ?? "agent"),
      thought: String(e.thought ?? ""),
      tool: typeof e.tool === "string" ? e.tool : null,
      time: typeof e.timestamp === "string" ? e.timestamp : undefined,
    }));
}

/**
 * Trace replay view. Loads a historical session's full trace (events +
 * snapshots) and reconstructs the timeline, reasoning, event feed, state, and
 * decision — durable, auditable observability.
 */
export function ReplayView({
  sessionId,
  onBack,
}: {
  sessionId: string;
  onBack: () => void;
}) {
  const { data, isLoading } = useTrace(sessionId);
  const [tab, setTab] = useState<InnerTab>("timeline");

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading trace…
      </div>
    );
  }

  const entries: LogEntry[] = data.events.map((e, i) => ({
    id: `${sessionId}-${i}`,
    eventType: e.event_type,
    nodeName: e.node_name,
    toolName: e.tool_name,
    message: e.message,
    payload: e.payload,
    time: e.created_at,
    durationMs: e.duration_ms,
  }));

  const lastSnapshot = data.snapshots[data.snapshots.length - 1]?.state_snapshot;
  const state = lastSnapshot ?? deriveStateFromEvents(data.events);
  const reasoningItems = reasoningFromSnapshot(lastSnapshot);
  const reasoning =
    reasoningItems.length > 0 ? reasoningItems : deriveReasoningFromEvents(data.events);

  const decision = data.session.final_decision as Decision | null;
  const completedEvent = data.events.find((e) => e.event_type === "execution_completed");
  const payload = completedEvent?.payload as
    | { rationale?: string; reason_codes?: string[] }
    | undefined;

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-3.5 w-3.5" /> History
        </Button>
        <span className="truncate font-mono text-xs text-muted-foreground">
          {sessionId}
        </span>
      </div>

      {decision && (
        <DecisionResultCard
          decision={decision}
          rationale={payload?.rationale ?? ""}
          reasonCodes={payload?.reason_codes}
        />
      )}

      <Tabs value={tab} onChange={(v) => setTab(v as InnerTab)}>
        <TabsList>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="reasoning">Reasoning</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="state">State</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {tab === "timeline" && <ExecutionTimeline events={data.events} />}
        {tab === "reasoning" && <ReasoningPanel items={reasoning} />}
        {tab === "events" && <LiveEventFeed entries={entries} />}
        {tab === "state" && <StateInspector state={state} />}
      </div>
    </div>
  );
}
