/**
 * Shared TypeScript contracts mirroring the backend Pydantic schemas.
 * Keeping these in one module gives the whole app a single typed source of truth.
 */

export type Decision = "APPROVED" | "DENIED" | "ESCALATED";

export type ExecutionStatus = "running" | "completed" | "failed";

export interface RefundHistoryItem {
  order_id: string;
  date: string;
  amount: number;
  status: string;
  reason: string;
}

export interface CustomerProfile {
  customer_id: string;
  name: string;
  email: string;
  tier: "vip" | "standard";
  purchase_history: string[];
  refund_history: RefundHistoryItem[];
  account_age_days: number;
  fraud_risk_score: number;
  lifetime_value: number;
}

export interface OrderInfo {
  order_id: string;
  customer_id: string;
  product_name: string;
  product_category: string;
  is_digital: boolean;
  is_final_sale: boolean;
  purchase_date: string;
  amount: number;
  currency: string;
}

export interface PolicyViolation {
  rule_id: string;
  reason_code: string;
  severity: "HARD" | "SOFT";
  message: string;
}

export interface PolicyResult {
  approved: boolean;
  violations: PolicyViolation[];
}

export interface FraudResult {
  risk_score: number;
  band: "low" | "borderline" | "high";
  threshold: number;
}

export interface ReasoningStep {
  node: string;
  thought: string;
  tool: string | null;
  tool_result: Record<string, unknown> | null;
  timestamp: string;
}

export interface RefundDecisionResponse {
  session_id: string;
  decision: Decision;
  rationale: string;
  reason_codes: string[];
  customer: CustomerProfile | null;
  order: OrderInfo | null;
  policy_result: PolicyResult | null;
  fraud_result: FraudResult | null;
  reasoning_log: ReasoningStep[];
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  decision: Decision | null;
  decision_detail: RefundDecisionResponse | null;
}

export type AgentEventType =
  | "execution_started"
  | "node_entered"
  | "tool_called"
  | "tool_completed"
  | "validation_completed"
  | "retry_attempt"
  | "escalation_triggered"
  | "execution_completed"
  | "execution_failed";

export interface AgentEvent {
  event_id: string;
  session_id: string;
  event_type: AgentEventType;
  node_name: string | null;
  tool_name: string | null;
  message: string | null;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface SessionSummary {
  session_id: string;
  customer_id: string;
  order_id: string | null;
  status: ExecutionStatus;
  final_decision: Decision | null;
  created_at: string;
  completed_at: string | null;
}

export interface PersistedEvent {
  event_type: AgentEventType;
  node_name: string | null;
  tool_name: string | null;
  message: string | null;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  created_at: string;
}

export interface StateSnapshot {
  graph_node: string;
  state_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface TraceResponse {
  session: SessionSummary;
  events: PersistedEvent[];
  snapshots: StateSnapshot[];
}

/** Canonical graph node order, used to render the execution timeline. */
export const GRAPH_NODES = [
  "customer_lookup",
  "order_lookup",
  "policy_validation",
  "fraud_check",
  "decision",
] as const;

export type GraphNode = (typeof GRAPH_NODES)[number];
