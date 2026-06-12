import { useState } from "react";
import { Activity, History } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAppStore } from "@/store/useAppStore";
import { HistoryList } from "./HistoryList";
import { LiveView } from "./LiveView";
import { ReplayView } from "./ReplayView";

type Mode = "live" | "history";

/**
 * The observability surface: live execution view (SSE-driven) and execution
 * history with click-to-replay. Hosted inside the Admin console.
 */
export function OperationsDashboard() {
  const [mode, setMode] = useState<Mode>("live");
  const { sessionId, replaySessionId, setReplaySession } = useAppStore();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <span className="truncate font-mono text-xs text-muted-foreground">
          {sessionId ? `session ${sessionId}` : "no active session"}
        </span>
        <Tabs value={mode} onChange={(v) => setMode(v as Mode)}>
          <TabsList>
            <TabsTrigger value="live">
              <span className="flex items-center gap-1">
                <Activity className="h-3.5 w-3.5" /> Live
              </span>
            </TabsTrigger>
            <TabsTrigger value="history">
              <span className="flex items-center gap-1">
                <History className="h-3.5 w-3.5" /> History
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="min-h-0 flex-1">
        {mode === "live" && <LiveView />}
        {mode === "history" &&
          (replaySessionId ? (
            <ReplayView
              sessionId={replaySessionId}
              onBack={() => setReplaySession(null)}
            />
          ) : (
            <div className="h-full overflow-y-auto p-4">
              <HistoryList
                selectedId={replaySessionId}
                onSelect={setReplaySession}
              />
            </div>
          ))}
      </div>
    </div>
  );
}
