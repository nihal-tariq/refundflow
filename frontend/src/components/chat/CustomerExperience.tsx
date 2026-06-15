import { useState } from "react";
import { Bot, ChevronDown, ReceiptText, RotateCcw, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useAgentRun, type RunArgs } from "@/hooks/useAgentRun";
import { cn } from "@/lib/utils";
import type { DemoScenario } from "@/lib/demoScenarios";
import { useAppStore, type ChatMessage } from "@/store/useAppStore";
import { ChatTranscript } from "./ChatTranscript";
import { CustomerIdentity } from "./CustomerIdentity";
import { RefundForm } from "./RefundForm";
import { SuggestedPrompts } from "./SuggestedPrompts";
import { VoiceButton } from "./VoiceButton";

/** Static greeting shown before the first turn (not stored in the transcript). */
const WELCOME: ChatMessage = {
  id: "welcome",
  role: "agent",
  content:
    "Hi! I'm the RefundFlow assistant. I can check your refund in seconds — " +
    "pick a demo scenario below, or open “Refund details” and tell me your " +
    "order ID and what went wrong.",
};

/**
 * The customer-facing support chat page.
 *
 * A centered, helpdesk-style experience: brand bar with the customer's
 * identity, the conversation, demo scenario chips, a collapsible refund-details
 * form, and a free-text composer. Internal signals (fraud risk, reasoning) are
 * never shown here — they live in the admin console.
 */
export function CustomerExperience() {
  const { customerId, setCustomerId, messages, status, resetChat } = useAppStore();
  const { run } = useAgentRun();
  const { toast } = useToast();
  const [orderId, setOrderId] = useState("ORD-1001");
  const [reason, setReason] = useState("");
  const [draft, setDraft] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(true);

  const running = status === "running";
  const displayMessages = messages.length > 0 ? messages : [WELCOME];

  const launch = (args: RunArgs) => {
    setDetailsOpen(false);
    run(args);
    toast("Checking your refund…", { tone: "info", description: args.orderId });
  };

  const onScenario = (scenario: DemoScenario) => {
    setCustomerId(scenario.customerId);
    setOrderId(scenario.orderId);
    setReason(scenario.reason);
    launch({
      customerId: scenario.customerId,
      orderId: scenario.orderId,
      reason: scenario.reason,
      message: `I'd like a refund for order ${scenario.orderId}. ${scenario.reason}`,
      evidenceProvided: scenario.evidenceProvided,
    });
  };

  const sendFreeText = () => {
    if (!draft.trim() || running) return;
    launch({ customerId, message: draft.trim() });
    setDraft("");
  };

  return (
    <div className="flex h-full flex-col">
      {/* Support header */}
      <header className="border-b border-border bg-card/40">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-primary/15 text-primary">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold leading-tight">RefundFlow Support</p>
              <p className="text-[11px] text-muted-foreground">
                Typically replies in seconds
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={resetChat}
                disabled={running}
                title="Start a new conversation"
              >
                <RotateCcw className="h-3.5 w-3.5" /> New chat
              </Button>
            )}
            <Input
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value.toUpperCase())}
              placeholder="CUST-001"
              className="h-8 w-28 font-mono text-xs"
              aria-label="Customer ID"
            />
            <CustomerIdentity customerId={customerId} />
          </div>
        </div>
      </header>

      {/* Conversation (anchored to the bottom so sparse chats look natural) */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-end px-4 py-4">
          <ChatTranscript messages={displayMessages} />
        </div>
      </div>

      {/* Scenario chips + refund details + composer */}
      <footer className="border-t border-border bg-card/40">
        <div className="mx-auto w-full max-w-3xl space-y-3 px-4 py-3">
          <SuggestedPrompts onPick={onScenario} disabled={running} />

          <div className="rounded-lg border border-border bg-card">
            <button
              onClick={() => setDetailsOpen((v) => !v)}
              className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium"
              aria-expanded={detailsOpen}
            >
              <span className="flex items-center gap-1.5">
                <ReceiptText className="h-3.5 w-3.5 text-muted-foreground" />
                Refund details
                <span className="font-mono text-[10px] text-muted-foreground">
                  {orderId || "—"}
                </span>
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform",
                  detailsOpen && "rotate-180",
                )}
              />
            </button>
            {detailsOpen && (
              <div className="border-t border-border p-3">
                <RefundForm
                  customerId={customerId}
                  orderId={orderId}
                  reason={reason}
                  onChange={(patch) => {
                    if (patch.orderId !== undefined) setOrderId(patch.orderId);
                    if (patch.reason !== undefined) setReason(patch.reason);
                  }}
                  onSubmit={launch}
                  disabled={running}
                />
              </div>
            )}
          </div>

          <div className="flex items-end gap-2">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendFreeText()}
              placeholder="Write a message…"
              disabled={running}
            />
            <VoiceButton customerId={customerId} disabled={running} />
            <Button size="icon" onClick={sendFreeText} disabled={running || !draft.trim()} aria-label="Send">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </footer>
    </div>
  );
}
