/**
 * Curated demo scenarios for one-click walkthroughs (used by quick-fill chips).
 * Each maps to a customer/order whose data deterministically produces the
 * labeled outcome — ideal for the Loom demo.
 */

export interface DemoScenario {
  label: string;
  customerId: string;
  orderId: string;
  reason: string;
  evidenceProvided?: boolean;
  expected: "APPROVED" | "DENIED" | "ESCALATED";
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    label: "Happy path → Approve",
    customerId: "CUST-001",
    orderId: "ORD-1001",
    reason: "The headphones stopped working after a few days.",
    evidenceProvided: true,
    expected: "APPROVED",
  },
  {
    label: "Repeat abuser → Deny",
    customerId: "CUST-004",
    orderId: "ORD-1004",
    reason: "Changed my mind, want my money back.",
    expected: "DENIED",
  },
  {
    label: "VIP, out of window → Escalate",
    customerId: "CUST-007",
    orderId: "ORD-1007",
    reason: "No longer need the espresso machine.",
    expected: "ESCALATED",
  },
  {
    label: "Digital product → Deny",
    customerId: "CUST-002",
    orderId: "ORD-1002",
    reason: "The software didn't fit my needs.",
    expected: "DENIED",
  },
  {
    label: "High fraud risk → Deny",
    customerId: "CUST-009",
    orderId: "ORD-1009",
    reason: "Phone never arrived.",
    expected: "DENIED",
  },
  {
    label: "New customer, borderline → Escalate",
    customerId: "CUST-012",
    orderId: "ORD-1012",
    reason: "The handbag color is different from the listing.",
    expected: "ESCALATED",
  },
];
