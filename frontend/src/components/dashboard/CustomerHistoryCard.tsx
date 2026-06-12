import { ReceiptText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useCustomer } from "@/hooks/useCustomer";
import { formatCurrency } from "@/lib/utils";

/**
 * Operator-facing list of the customer's past refunds.
 *
 * Lives in the admin rail (never the customer view) — prior refund behaviour is
 * exactly the context an operator needs to understand a decision.
 */
export function CustomerHistoryCard({ customerId }: { customerId: string }) {
  const { data } = useCustomer(customerId);
  if (!data) return null;

  const refunds = data.refund_history;

  return (
    <Card>
      <CardContent className="space-y-2 pt-4">
        <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          <ReceiptText className="h-3.5 w-3.5" /> Refund history
        </p>
        {refunds.length === 0 ? (
          <p className="text-xs text-muted-foreground">No prior refunds on file.</p>
        ) : (
          <ul className="space-y-1.5">
            {refunds.slice(0, 5).map((r, i) => (
              <li
                key={`${r.order_id}-${i}`}
                className="flex items-center justify-between gap-2 text-xs"
              >
                <span className="min-w-0">
                  <span className="font-mono text-muted-foreground">{r.date}</span>{" "}
                  <span className="truncate">{formatCurrency(r.amount)}</span>
                </span>
                <Badge variant={r.status === "approved" ? "success" : "danger"}>
                  {r.status}
                </Badge>
              </li>
            ))}
          </ul>
        )}
        <p className="pt-1 text-[11px] text-muted-foreground">
          {data.purchase_history.length} lifetime orders ·{" "}
          {formatCurrency(data.lifetime_value)} LTV
        </p>
      </CardContent>
    </Card>
  );
}
