/**
 * Orchestrates a single live agent run with real-time SSE streaming.
 *
 * Flow (the ordering matters): we generate the session id on the client, open
 * the SSE stream first, and only fire the chat POST once the stream is open.
 * This guarantees we observe every event the (fast) graph emits — no polling,
 * no missed frames. The terminal decision arrives in the POST response.
 */

import { useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { subscribeToEvents } from "@/api/eventStream";
import { sendChat, type ChatPayload } from "@/api/refundApi";
import { useAppStore } from "@/store/useAppStore";

/** Generate a backend-compatible session id (`sess-<hex>`). */
function newSessionId(): string {
  const hex =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().replace(/-/g, "").slice(0, 12)
      : Math.random().toString(16).slice(2, 14);
  return `sess-${hex}`;
}

export interface RunArgs {
  customerId: string;
  message: string;
  orderId: string;
  reason: string;
  evidenceProvided?: boolean;
}

/**
 * Returns a `run` callback that executes one agent turn with live streaming.
 */
export function useAgentRun() {
  const queryClient = useQueryClient();
  const cleanupRef = useRef<(() => void) | null>(null);
  const {
    startRun,
    pushEvent,
    finishRun,
    addMessage,
    updateMessage,
  } = useAppStore();

  const run = useCallback(
    async (args: RunArgs) => {
      cleanupRef.current?.();
      const sessionId = newSessionId();
      startRun(sessionId);

      // Optimistic transcript: user message + pending agent bubble.
      const userId = `u-${sessionId}`;
      const agentId = `a-${sessionId}`;
      addMessage({ id: userId, role: "user", content: args.message });
      addMessage({ id: agentId, role: "agent", content: "", pending: true });

      const payload: ChatPayload = {
        customer_id: args.customerId,
        message: args.message,
        session_id: sessionId,
        order_id: args.orderId,
        reason: args.reason,
        evidence_provided: args.evidenceProvided,
      };

      const fire = async () => {
        try {
          const response = await sendChat(payload);
          finishRun(response.decision_detail, "completed");
          updateMessage(agentId, {
            content: response.reply,
            decision: response.decision,
            pending: false,
          });
          queryClient.invalidateQueries({ queryKey: ["sessions"] });
        } catch (error) {
          finishRun(null, "failed");
          updateMessage(agentId, {
            content:
              "Sorry — something went wrong while processing your request. Please try again.",
            pending: false,
          });
          // eslint-disable-next-line no-console
          console.error(error);
        }
      };

      let fired = false;
      const fireOnce = () => {
        if (fired) return;
        fired = true;
        void fire();
      };

      cleanupRef.current = subscribeToEvents(sessionId, {
        onOpen: fireOnce,
        onEvent: (event) => {
          pushEvent(event);
          if (event.event_type === "execution_failed") finishRun(null, "failed");
        },
        onError: () => {
          // If the stream never opened (e.g. EventSource unsupported), still run.
          fireOnce();
        },
      });

      // Safety net: fire the request even if `onOpen` is delayed.
      setTimeout(fireOnce, 600);
    },
    [startRun, pushEvent, finishRun, addMessage, updateMessage, queryClient],
  );

  return { run };
}
