import { Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCustomer } from "@/hooks/useCustomer";

/**
 * Compact, customer-safe identity chip (name + tier).
 *
 * Deliberately shows none of the internal CRM signals (fraud risk, refund
 * history, LTV) — those belong to the admin console's CustomerCard, never to
 * the customer-facing page.
 */
export function CustomerIdentity({ customerId }: { customerId: string }) {
  const { data, isLoading, isError } = useCustomer(customerId);

  if (isLoading) return <Skeleton className="h-7 w-32" />;
  if (isError || !data) return <Badge variant="danger">Unknown ID</Badge>;

  return (
    <div className="flex items-center gap-2">
      <div className="grid h-7 w-7 place-items-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
        {data.name.charAt(0)}
      </div>
      <span className="max-w-[140px] truncate text-sm font-medium">{data.name}</span>
      {data.tier === "vip" && (
        <Badge variant="primary">
          <Star className="h-3 w-3" /> VIP
        </Badge>
      )}
    </div>
  );
}
