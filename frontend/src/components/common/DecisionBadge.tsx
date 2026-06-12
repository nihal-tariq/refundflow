import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Decision } from "@/types";

/** Visual config (icon, color variant, labels) for each decision outcome. */
const CONFIG = {
  APPROVED: {
    variant: "success",
    admin: "Approved",
    customer: "Refund approved",
    Icon: CheckCircle2,
  },
  DENIED: {
    variant: "danger",
    admin: "Denied",
    customer: "Not approved",
    Icon: XCircle,
  },
  ESCALATED: {
    variant: "warning",
    admin: "Escalated",
    customer: "Under review",
    Icon: ShieldAlert,
  },
} as const;

/**
 * Render a colored badge for a refund decision.
 *
 * @param decision - The decision to display.
 * @param size - Optional larger presentation for the hero decision card.
 * @param audience - "admin" shows the raw verdict; "customer" shows a friendlier
 *   label (e.g. "Not approved" instead of "Denied") for the chat bubble.
 */
export function DecisionBadge({
  decision,
  size = "sm",
  audience = "admin",
}: {
  decision: Decision;
  size?: "sm" | "lg";
  audience?: "admin" | "customer";
}) {
  const { variant, Icon, ...labels } = CONFIG[decision];
  const label = audience === "customer" ? labels.customer : labels.admin;
  return (
    <Badge variant={variant} className={size === "lg" ? "px-3 py-1 text-sm" : ""}>
      <Icon className={size === "lg" ? "h-4 w-4" : "h-3 w-3"} />
      {label}
    </Badge>
  );
}
