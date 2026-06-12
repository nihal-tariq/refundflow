import { motion } from "framer-motion";
import { Bot } from "lucide-react";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { TypingIndicator } from "./TypingIndicator";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/store/useAppStore";

/**
 * A single chat bubble. Right-aligned for the customer, left-aligned (with an
 * avatar) for the agent. Renders a typing indicator while the agent reply is
 * pending and a decision badge once a verdict is attached.
 */
export function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  // The static welcome greeting is part of the initial page — no entry motion.
  const isStatic = message.id === "welcome";
  return (
    <motion.div
      initial={isStatic ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/15 text-primary">
          <Bot className="h-4 w-4" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[78%] rounded-2xl px-3.5 py-2 text-sm",
          isUser
            ? "rounded-br-sm bg-primary text-primary-foreground"
            : "rounded-bl-sm border border-border bg-muted/40",
        )}
      >
        {message.pending ? (
          <TypingIndicator />
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        )}
        {message.decision && (
          <div className="mt-2">
            <DecisionBadge decision={message.decision} audience="customer" />
          </div>
        )}
      </div>
    </motion.div>
  );
}
