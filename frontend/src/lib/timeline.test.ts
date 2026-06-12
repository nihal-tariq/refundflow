import { describe, expect, it } from "vitest";
import { deriveNodeStatuses, deriveStateFromEvents, progressFraction } from "./timeline";
import type { PersistedEvent } from "@/types";

const ev = (
  event_type: PersistedEvent["event_type"],
  node_name: string | null = null,
  payload: Record<string, unknown> = {},
): PersistedEvent => ({
  event_type,
  node_name,
  tool_name: null,
  message: null,
  payload,
  duration_ms: null,
  created_at: "2026-06-12T00:00:00Z",
});

describe("deriveNodeStatuses", () => {
  it("marks entered-but-not-final nodes as done and the last as active", () => {
    const statuses = deriveNodeStatuses([
      ev("node_entered", "customer_lookup"),
      ev("node_entered", "order_lookup"),
    ]);
    expect(statuses.customer_lookup).toBe("done");
    expect(statuses.order_lookup).toBe("active");
    expect(statuses.decision).toBe("pending");
  });

  it("marks all entered nodes as done once execution completes", () => {
    const statuses = deriveNodeStatuses([
      ev("node_entered", "customer_lookup"),
      ev("node_entered", "decision"),
      ev("execution_completed", "decision"),
    ]);
    expect(statuses.customer_lookup).toBe("done");
    expect(statuses.decision).toBe("done");
  });
});

describe("progressFraction", () => {
  it("is zero with no events and grows as nodes complete", () => {
    expect(progressFraction([])).toBe(0);
    const frac = progressFraction([
      ev("node_entered", "customer_lookup"),
      ev("node_entered", "order_lookup"),
    ]);
    expect(frac).toBeGreaterThan(0);
  });
});

describe("deriveStateFromEvents", () => {
  it("captures the final decision from the completion payload", () => {
    const state = deriveStateFromEvents([
      ev("execution_completed", "decision", { decision: "APPROVED" }),
    ]);
    expect(state.final_decision).toBe("APPROVED");
  });
});
