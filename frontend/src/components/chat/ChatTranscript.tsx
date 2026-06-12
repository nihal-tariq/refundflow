import { useEffect, useRef } from "react";
import { MessagesSquare } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { ChatBubble } from "./ChatBubble";
import type { ChatMessage } from "@/store/useAppStore";

/**
 * Scrollable chat transcript that auto-scrolls to the latest message.
 *
 * Shows an empty state before the first turn.
 */
export function ChatTranscript({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <EmptyState
        icon={MessagesSquare}
        title="No conversation yet"
        description="Pick a scenario or submit a refund request to chat with the agent."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3 p-1">
      {messages.map((message) => (
        <ChatBubble key={message.id} message={message} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
