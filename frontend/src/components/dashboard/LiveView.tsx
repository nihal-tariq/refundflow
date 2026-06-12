import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LiveEventFeed } from "@/components/logs/LiveEventFeed";
import type { LogEntry } from "@/components/logs/LogCard";
import { ReasoningPanel } from "@/components/logs/ReasoningPanel";
import {
  deriveReasoningFromEvents,
  deriveStateFromEvents,
  type ReasoningItem,
} from "@/lib/timeline";
import { useAppStore } from "@/store/useAppStore";
import { DecisionResultCard } from "./DecisionResultCard";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { StateInspector } from "./StateInspector";
import { StreamProgress } from "./StreamProgress";

type InnerTab = "timeline" | "reasoning" | "events" | "state";

/**
 * Live operations view for the active run: progress, the final-decision hero,
 * and switchable Timeline / Reasoning / Event Feed / State panels — all driven
 * by the SSE event stream held in the store.
 */
export function LiveView() {
  const { events, status, decision } = useAppStore();
  const [tab, setTab] = useState<InnerTab>("timeline");

  const entries: LogEntry[] = events.map((e) => ({
    id: e.event_id,
    eventType: e.event_type,
    nodeName: e.node_name,
    toolName: e.tool_name,
    message: e.message,
    payload: e.payload,
    time: e.timestamp,
  }));
  const liveState = deriveStateFromEvents(events);

  // Prefer the agent's full reasoning log (arrives with the decision); while
  // the run is still in flight, derive interim reasoning from the event stream.
  const reasoning: ReasoningItem[] = decision
    ? decision.reasoning_log.map((step) => ({
        node: step.node,
        thought: step.thought,
        tool: step.tool,
        time: step.timestamp,
      }))
    : deriveReasoningFromEvents(events);

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <StreamProgress events={events} status={status} />

      {decision && (
        <DecisionResultCard
          decision={decision.decision}
          rationale={decision.rationale}
          policy={decision.policy_result}
          reasonCodes={decision.reason_codes}
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
        {tab === "timeline" && <ExecutionTimeline events={events} />}
        {tab === "reasoning" && <ReasoningPanel items={reasoning} />}
        {tab === "events" && <LiveEventFeed entries={entries} />}
        {tab === "state" && <StateInspector state={liveState} />}
      </div>
    </div>
  );
}
