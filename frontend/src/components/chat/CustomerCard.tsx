import { motion } from "framer-motion";
import { ShieldCheck, Star, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCustomer } from "@/hooks/useCustomer";
import { formatCurrency } from "@/lib/utils";

/** A small labelled stat used inside the customer card. */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="truncate whitespace-nowrap text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="truncate text-sm font-medium">{value}</p>
    </div>
  );
}

/**
 * Customer profile card. Fetches the selected customer via React Query and shows
 * tier, fraud risk, account age, and lifetime value. Renders a skeleton while
 * loading and an inline error when the id is unknown.
 */
export function CustomerCard({ customerId }: { customerId: string }) {
  const { data, isLoading, isError } = useCustomer(customerId);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="space-y-3 pt-4">
          <Skeleton className="h-5 w-40" />
          <div className="grid grid-cols-3 gap-3">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 pt-4 text-sm text-muted-foreground">
          <User className="h-4 w-4" />
          No customer found for “{customerId}”.
        </CardContent>
      </Card>
    );
  }

  const fraudPct = Math.round(data.fraud_risk_score * 100);
  const highRisk = data.fraud_risk_score >= 0.7;

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card>
        <CardContent className="space-y-3 pt-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
                {data.name.charAt(0)}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold leading-tight">{data.name}</p>
                <p className="truncate text-xs text-muted-foreground">{data.email}</p>
              </div>
            </div>
            {data.tier === "vip" ? (
              <Badge variant="primary" className="shrink-0">
                <Star className="h-3 w-3" /> VIP
              </Badge>
            ) : (
              <Badge variant="outline" className="shrink-0">Standard</Badge>
            )}
          </div>

          <div className="grid grid-cols-3 gap-3 rounded-md border border-border bg-muted/30 p-3">
            <Stat label="Age" value={`${data.account_age_days}d`} />
            <Stat label="Refunds" value={`${data.refund_history.length}`} />
            <Stat label="LTV" value={formatCurrency(data.lifetime_value)} />
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1 text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" /> Fraud risk
            </span>
            <Badge variant={highRisk ? "danger" : fraudPct >= 55 ? "warning" : "success"}>
              {fraudPct}%
            </Badge>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
