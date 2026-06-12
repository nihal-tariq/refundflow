import { motion } from "framer-motion";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { Badge } from "@/components/ui/badge";
import type { Decision, PolicyResult } from "@/types";

/** Border/glow tint per decision. */
const TINT: Record<Decision, string> = {
  APPROVED: "border-[hsl(var(--success)/0.5)] bg-[hsl(var(--success)/0.06)]",
  DENIED: "border-[hsl(var(--danger)/0.5)] bg-[hsl(var(--danger)/0.06)]",
  ESCALATED: "border-[hsl(var(--warning)/0.5)] bg-[hsl(var(--warning)/0.06)]",
};

/**
 * Hero card summarizing the final decision: outcome badge, internal rationale,
 * and the triggering reason codes.
 *
 * Prefers the policy violations (which carry severity); falls back to the
 * composed `reasonCodes` so fraud-driven outcomes (composed outside the policy
 * result) still show their codes.
 */
export function DecisionResultCard({
  decision,
  rationale,
  policy,
  reasonCodes,
}: {
  decision: Decision;
  rationale: string;
  policy?: PolicyResult | null;
  reasonCodes?: string[];
}) {
  const fallbackVariant: "danger" | "warning" =
    decision === "DENIED" ? "danger" : "warning";
  const chips =
    policy && policy.violations.length > 0
      ? policy.violations.map((v) => ({
          code: v.reason_code,
          variant: (v.severity === "HARD" ? "danger" : "warning") as "danger" | "warning",
        }))
      : (reasonCodes ?? []).map((code) => ({ code, variant: fallbackVariant }));

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`rounded-lg border p-4 ${TINT[decision]}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Final decision
        </span>
        <DecisionBadge decision={decision} size="lg" />
      </div>
      <p className="mt-2 text-sm leading-relaxed">{rationale}</p>
      {chips.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {chips.map(({ code, variant }) => (
            <Badge key={code} variant={variant} className="font-mono text-[10px]">
              {code}
            </Badge>
          ))}
        </div>
      )}
    </motion.div>
  );
}
