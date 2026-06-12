/** React Query hooks for execution history and trace replay. */

import { useQuery } from "@tanstack/react-query";
import { fetchSessions, fetchTrace } from "@/api/refundApi";
import type { SessionSummary, TraceResponse } from "@/types";

/**
 * Fetch recent execution summaries for the history panel.
 *
 * Polls modestly so newly-completed runs appear without a manual refresh; the
 * live run itself uses SSE, not this query.
 */
export function useSessions() {
  return useQuery<SessionSummary[]>({
    queryKey: ["sessions"],
    queryFn: () => fetchSessions(50),
    refetchInterval: 8000,
  });
}

/**
 * Fetch the full trace for a session (events + snapshots) for replay.
 *
 * @param sessionId - Session to load, or null to disable the query.
 */
export function useTrace(sessionId: string | null) {
  return useQuery<TraceResponse>({
    queryKey: ["trace", sessionId],
    queryFn: () => fetchTrace(sessionId as string),
    enabled: Boolean(sessionId),
  });
}
