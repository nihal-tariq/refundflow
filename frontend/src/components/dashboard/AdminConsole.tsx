import { Badge } from "@/components/ui/badge";
import { CustomerCard } from "@/components/chat/CustomerCard";
import { useHealth } from "@/hooks/useHealth";
import { useAppStore } from "@/store/useAppStore";
import { CustomerHistoryCard } from "./CustomerHistoryCard";
import { OperationsDashboard } from "./OperationsDashboard";

/**
 * The admin console view (hidden behind the sidebar's second nav item).
 *
 * Left rail: the full CRM profile of the active customer — including internal
 * signals like fraud risk that are deliberately *not* shown on the customer
 * page. Main area: the live/replay observability dashboard.
 */
export function AdminConsole() {
  const customerId = useAppStore((s) => s.customerId);
  const { data: health } = useHealth();

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <div>
          <h1 className="text-sm font-semibold">Admin Console</h1>
          <p className="text-xs text-muted-foreground">
            Real-time agent reasoning, tool calls, and execution traces
          </p>
        </div>
        <Badge variant="outline">
          {health?.llm_enabled ? `LLM: ${health.llm_provider}` : "deterministic mode"}
        </Badge>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[320px,1fr]">
        <aside className="space-y-3 overflow-y-auto border-b border-border p-4 lg:border-b-0 lg:border-r">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Active customer
          </p>
          <CustomerCard customerId={customerId} />
          <CustomerHistoryCard customerId={customerId} />
        </aside>
        <OperationsDashboard />
      </div>
    </div>
  );
}
