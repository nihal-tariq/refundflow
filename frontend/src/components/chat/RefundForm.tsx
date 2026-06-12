import { useState } from "react";
import { Paperclip, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { RunArgs } from "@/hooks/useAgentRun";

/** Labelled field wrapper. */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

/**
 * Compact refund-details form (Order ID, reason, evidence toggle).
 *
 * Purely presentational + local field state; submission is delegated upward via
 * `onSubmit`, keeping all run orchestration in the hook/parent. Rendered inside
 * the chat view's collapsible "Refund details" panel.
 */
export function RefundForm({
  customerId,
  orderId,
  reason,
  onChange,
  onSubmit,
  disabled,
}: {
  customerId: string;
  orderId: string;
  reason: string;
  onChange: (patch: { orderId?: string; reason?: string }) => void;
  onSubmit: (args: RunArgs) => void;
  disabled?: boolean;
}) {
  const [evidence, setEvidence] = useState(false);

  const submit = () => {
    if (!orderId.trim() || !reason.trim()) return;
    onSubmit({
      customerId,
      orderId: orderId.trim(),
      reason: reason.trim(),
      message: `I'd like a refund for order ${orderId.trim()}. ${reason.trim()}`,
      evidenceProvided: evidence,
    });
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-[170px,1fr]">
        <Field label="Order ID">
          <Input
            value={orderId}
            placeholder="ORD-1001"
            className="h-9 font-mono text-xs"
            onChange={(e) => onChange({ orderId: e.target.value.toUpperCase() })}
          />
        </Field>
        <Field label="What went wrong?">
          <Textarea
            value={reason}
            placeholder="e.g. The item arrived damaged…"
            rows={2}
            className="min-h-[36px] text-xs"
            onChange={(e) => onChange({ reason: e.target.value })}
          />
        </Field>
      </div>
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setEvidence((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <Paperclip className="h-3.5 w-3.5" />
          <span className={evidence ? "text-primary" : ""}>
            {evidence ? "Photo evidence attached" : "Attach photo evidence"}
          </span>
        </button>
        <Button size="sm" onClick={submit} disabled={disabled || !orderId || !reason}>
          <Send className="h-3.5 w-3.5" /> Request refund
        </Button>
      </div>
    </div>
  );
}
