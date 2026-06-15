/**
 * Typed API surface for refund, customer, and trace endpoints.
 * Each function maps 1:1 to a backend route and returns a typed payload.
 */

import type {
  ChatResponse,
  CustomerProfile,
  RefundDecisionResponse,
  SessionSummary,
  TraceResponse,
} from "@/types";
import { apiGet, apiPost } from "./client";

export interface ChatPayload {
  customer_id: string;
  message: string;
  conversation_id?: string;
  session_id?: string;
  order_id?: string;
  reason?: string;
  evidence_provided?: boolean;
}

export interface RefundPayload {
  customer_id: string;
  order_id: string;
  reason: string;
  evidence_provided?: boolean;
}

/** Fetch a single customer profile by id. */
export const fetchCustomer = (id: string): Promise<CustomerProfile> =>
  apiGet<CustomerProfile>(`/customer/${id}`);

/** Fetch all demo customers (for the picker). */
export const fetchCustomers = (): Promise<CustomerProfile[]> =>
  apiGet<CustomerProfile[]>("/customer");

/** Run the agent on a structured refund request. */
export const submitRefund = (
  payload: RefundPayload,
): Promise<RefundDecisionResponse> =>
  apiPost<RefundDecisionResponse>("/refund-request", payload);

/** Send a conversational turn to the agent. */
export const sendChat = (payload: ChatPayload): Promise<ChatResponse> =>
  apiPost<ChatResponse>("/chat", payload);

/** List recent agent executions for the history view. */
export const fetchSessions = (limit = 50): Promise<SessionSummary[]> =>
  apiGet<SessionSummary[]>(`/sessions?limit=${limit}`);

/** Fetch the full execution trace for a session (for replay). */
export const fetchTrace = (sessionId: string): Promise<TraceResponse> =>
  apiGet<TraceResponse>(`/logs/${sessionId}`);
