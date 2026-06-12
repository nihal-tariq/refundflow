import { Braces } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { humanize } from "@/lib/utils";

/**
 * Inspector showing the agent's current state as labelled JSON sections
 * (current node, customer, order, policy result, fraud result).
 *
 * Accepts a plain state object so it works identically for the live run and a
 * replayed snapshot.
 */
export function StateInspector({ state }: { state: Record<string, unknown> | null }) {
  if (!state || Object.keys(state).length === 0) {
    return (
      <EmptyState
        icon={Braces}
        title="No state captured yet"
        description="The state inspector populates as the agent records snapshots."
      />
    );
  }

  const sections: { key: string; value: unknown }[] = [
    { key: "current_node", value: state.current_node },
    { key: "customer_data", value: state.customer_data },
    { key: "order_data", value: state.order_data },
    { key: "policy_result", value: state.policy_result },
    { key: "fraud_result", value: state.fraud_result },
    { key: "final_decision", value: state.final_decision },
  ].filter((s) => s.value !== undefined && s.value !== null && s.value !== "");

  return (
    <div className="space-y-2">
      {sections.map(({ key, value }) => (
        <div key={key} className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {humanize(key)}
          </div>
          <pre className="max-h-44 overflow-auto p-3 font-mono text-[10px] leading-relaxed text-muted-foreground">
            {typeof value === "object"
              ? JSON.stringify(value, null, 2)
              : String(value)}
          </pre>
        </div>
      ))}
    </div>
  );
}
