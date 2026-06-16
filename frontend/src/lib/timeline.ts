/**
 * Pure helpers that derive UI view-models from a raw agent event stream.
 * Keeping this logic out of components makes it unit-testable and reusable by
 * both the live view and historical replay.
 */

import { GRAPH_NODES, type AgentEvent, type GraphNode, type PersistedEvent } from "@/types";

export type NodeStatus = "pending" | "active" | "done";

type AnyEvent = Pick<AgentEvent | PersistedEvent, "event_type" | "node_name">;

/**
 * Compute the status of every graph node from the event stream.
 *
 * @param events - Ordered live or persisted events.
 * @returns A map of node → status driving the execution timeline.
 */
export function deriveNodeStatuses(events: AnyEvent[]): Record<GraphNode, NodeStatus> {
  const entered = events
    .filter((e) => e.event_type === "node_entered" && e.node_name)
    .map((e) => e.node_name as GraphNode);
  const current = entered[entered.length - 1];
  const completed = events.some((e) => e.event_type === "execution_completed");

  const statuses = {} as Record<GraphNode, NodeStatus>;
  for (const node of GRAPH_NODES) {
    if (!entered.includes(node)) statuses[node] = "pending";
    else if (completed) statuses[node] = "done";
    else statuses[node] = node === current ? "active" : "done";
  }
  return statuses;
}

/** Overall progress fraction (0–1) for a progress bar. */
export function progressFraction(events: AnyEvent[]): number {
  const statuses = deriveNodeStatuses(events);
  const done = Object.values(statuses).filter((s) => s === "done").length;
  return done / GRAPH_NODES.length;
}

/** A reasoning line shown in the dashboard's Reasoning tab. */
export interface ReasoningItem {
  node: string;
  thought: string;
  tool?: string | null;
  time?: string;
}

const _REASONING_EVENTS = new Set([
  "execution_started",
  "tool_completed",
  "validation_completed",
  "escalation_triggered",
  "llm_response",
  "execution_completed",
  "execution_failed",
]);

/**
 * Derive interim reasoning lines from the live event stream.
 *
 * Used while a run is in flight (before the final ``reasoning_log`` arrives
 * with the decision) and as a fallback for replays without snapshots.
 */
export function deriveReasoningFromEvents(
  events: (AgentEvent | PersistedEvent)[],
): ReasoningItem[] {
  return events
    .filter((e) => e.message && _REASONING_EVENTS.has(e.event_type))
    .map((e) => ({
      node: e.node_name ?? "agent",
      thought: e.message as string,
      tool: e.tool_name,
      time: "timestamp" in e ? e.timestamp : e.created_at,
    }));
}

type PayloadEvent = Pick<
  AgentEvent | PersistedEvent,
  "event_type" | "node_name" | "payload"
>;

/**
 * Reconstruct a partial agent-state object from the event stream so the State
 * Inspector can update live (before the final decision payload arrives).
 *
 * @param events - Ordered live or persisted events carrying tool payloads.
 * @returns A state object shaped like the backend snapshot.
 */
export function deriveStateFromEvents(
  events: PayloadEvent[],
): Record<string, unknown> {
  const state: Record<string, unknown> = {};
  for (const event of events) {
    const payload = event.payload ?? {};
    if (event.event_type === "node_entered") state.current_node = event.node_name;
    if (event.node_name === "customer_lookup" && event.event_type === "tool_completed")
      state.customer_data = payload;
    if (event.node_name === "order_lookup" && event.event_type === "tool_completed")
      state.order_data = payload;
    if (event.event_type === "validation_completed") state.policy_result = payload;
    if (event.node_name === "fraud_check" && event.event_type === "tool_completed")
      state.fraud_result = payload;
    if (event.event_type === "execution_completed")
      state.final_decision = (payload as { decision?: string }).decision;
  }
  return state;
}
