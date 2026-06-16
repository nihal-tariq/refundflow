/**
 * SSE (Server-Sent Events) subscription helper.
 *
 * The backend emits named SSE events (`event: node_entered`, etc.), so we attach
 * a listener per event type. Returns an unsubscribe function that closes the
 * underlying `EventSource`.
 */

import type { AgentEvent, AgentEventType } from "@/types";
import { eventStreamUrl } from "./client";

const EVENT_TYPES: AgentEventType[] = [
  "execution_started",
  "node_entered",
  "tool_called",
  "tool_completed",
  "validation_completed",
  "retry_attempt",
  "escalation_triggered",
  "llm_response",
  "execution_completed",
  "execution_failed",
];

export interface EventStreamHandlers {
  onEvent: (event: AgentEvent) => void;
  onOpen?: () => void;
  onError?: (error: Event) => void;
}

/**
 * Subscribe to the live agent event stream for a session.
 *
 * @param sessionId - The session to subscribe to.
 * @param handlers - Callbacks for events and errors.
 * @returns A cleanup function that closes the stream.
 */
export function subscribeToEvents(
  sessionId: string,
  handlers: EventStreamHandlers,
): () => void {
  const source = new EventSource(eventStreamUrl(sessionId));

  const handle = (raw: MessageEvent) => {
    try {
      handlers.onEvent(JSON.parse(raw.data) as AgentEvent);
    } catch {
      /* ignore malformed frames */
    }
  };

  for (const type of EVENT_TYPES) {
    source.addEventListener(type, handle as EventListener);
  }
  source.addEventListener("message", handle as EventListener);
  source.onopen = () => handlers.onOpen?.();

  source.onerror = (error) => {
    handlers.onError?.(error);
    // The server closes the stream after the terminal event; that surfaces here
    // as an error. Close defensively to avoid the browser auto-reconnecting.
    source.close();
  };

  return () => source.close();
}
