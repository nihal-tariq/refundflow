/**
 * VoiceButton — a self-contained mic button that embeds a LiveKit voice
 * session into the chat footer.
 *
 * States at a glance:
 *   idle        → phone icon, click to call
 *   connecting  → spinner + "Connecting…" tooltip
 *   active      → red hang-up button + optional mute toggle + speaking indicator
 *   error       → pulsing icon + error tooltip
 */

import { useEffect, useRef } from "react";
import { Loader2, Mic, MicOff, Phone, PhoneOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { useVoiceSession } from "@/hooks/useVoiceSession";

interface VoiceButtonProps {
  customerId: string;
  disabled?: boolean;
}

export function VoiceButton({ customerId, disabled }: VoiceButtonProps) {
  const {
    voiceState,
    isMuted,
    agentSpeaking,
    errorMessage,
    transcript,
    connect,
    disconnect,
    toggleMute,
  } = useVoiceSession(customerId);

  const isIdle = voiceState === "idle";
  const isConnecting = voiceState === "connecting";
  const isActive = voiceState === "active";
  const isError = voiceState === "error";

  // Keep the transcript pinned to the latest line as it streams in.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [transcript]);

  const showTranscript = transcript.length > 0 && (isActive || isConnecting);

  return (
    <div className="relative flex items-center gap-1.5">
      {/* ── live call transcript ─────────────────────────────────────── */}
      {showTranscript && (
        <div className="absolute bottom-full right-0 mb-2 w-80 max-w-[80vw] overflow-hidden rounded-lg border border-border bg-card shadow-lg">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="text-xs font-semibold">Live transcript</span>
            {isActive && (
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-danger" />
                recording
              </span>
            )}
          </div>
          <div ref={scrollRef} className="max-h-64 space-y-2 overflow-y-auto px-3 py-2">
            {transcript.map((entry) => (
              <div
                key={entry.id}
                className={cn(
                  "flex flex-col gap-0.5",
                  entry.speaker === "you" ? "items-end" : "items-start",
                )}
              >
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  {entry.speaker === "you" ? "You" : "Maya"}
                </span>
                <span
                  className={cn(
                    "max-w-[85%] rounded-lg px-2.5 py-1.5 text-xs leading-snug",
                    entry.speaker === "you"
                      ? "bg-primary/15 text-foreground"
                      : "bg-muted text-foreground",
                    !entry.final && "italic opacity-60",
                  )}
                >
                  {entry.text}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── speaking ripple ─────────────────────────────────────────── */}
      {isActive && (
        <span
          className={cn(
            "relative flex h-2 w-2",
            agentSpeaking ? "opacity-100" : "opacity-30",
          )}
          title={agentSpeaking ? "Agent speaking…" : "Agent listening"}
        >
          {agentSpeaking && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
          )}
          <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
        </span>
      )}

      {/* ── mute toggle (only while active) ─────────────────────────── */}
      {isActive && (
        <button
          onClick={toggleMute}
          title={isMuted ? "Unmute mic" : "Mute mic"}
          className={cn(
            "grid h-8 w-8 place-items-center rounded-full border transition-colors",
            isMuted
              ? "border-warning/60 bg-warning/10 text-warning hover:bg-warning/20"
              : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground",
          )}
          aria-label={isMuted ? "Unmute microphone" : "Mute microphone"}
        >
          {isMuted ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
        </button>
      )}

      {/* ── primary call button ──────────────────────────────────────── */}
      <button
        onClick={isActive ? disconnect : connect}
        disabled={disabled || isConnecting}
        title={
          isError
            ? (errorMessage ?? "Voice unavailable")
            : isConnecting
              ? "Connecting to voice agent…"
              : isActive
                ? "End voice call"
                : "Start voice call with agent"
        }
        aria-label={isActive ? "End voice call" : "Start voice call"}
        className={cn(
          "relative grid h-8 w-8 place-items-center rounded-full border transition-all duration-200",
          // idle
          isIdle &&
            "border-border bg-card text-muted-foreground hover:border-primary/50 hover:bg-primary/10 hover:text-primary",
          // connecting
          isConnecting && "cursor-wait border-primary/40 bg-primary/10 text-primary",
          // active — red "hang up" state
          isActive &&
            "border-danger/60 bg-danger/15 text-danger hover:bg-danger/25",
          // error
          isError &&
            "animate-pulse border-warning/60 bg-warning/10 text-warning hover:bg-warning/20",
          // disabled
          (disabled || isConnecting) && "pointer-events-none opacity-50",
        )}
      >
        {isConnecting ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : isActive ? (
          <PhoneOff className="h-3.5 w-3.5" />
        ) : (
          <Phone className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  );
}
