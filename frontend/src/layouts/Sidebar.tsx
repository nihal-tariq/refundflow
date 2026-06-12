import { Activity, MessagesSquare, Moon, ScanFace, Sun } from "lucide-react";
import { useHealth } from "@/hooks/useHealth";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";
import { useAppStore, type AppView } from "@/store/useAppStore";

const NAV_ITEMS: { key: AppView; icon: typeof MessagesSquare; label: string }[] = [
  { key: "chat", icon: MessagesSquare, label: "Support chat" },
  { key: "admin", icon: Activity, label: "Admin console" },
];

/**
 * Left navigation rail (Linear-style icon sidebar).
 *
 * The customer chat is the primary view; the admin observability console is
 * tucked behind the second nav item, keeping the customer experience clean.
 * Also hosts the backend-connection indicator and the theme toggle.
 */
export function Sidebar() {
  const { view, setView } = useAppStore();
  const { theme, toggle } = useTheme();
  const { data, isError } = useHealth();
  const online = Boolean(data) && !isError;

  return (
    <aside className="flex h-full w-16 shrink-0 flex-col items-center border-r border-border bg-card/60 py-4">
      <div
        className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground"
        title="RefundFlow AI"
      >
        <ScanFace className="h-5 w-5" />
      </div>

      <nav className="mt-8 flex flex-col gap-2" aria-label="Main navigation">
        {NAV_ITEMS.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => setView(key)}
            title={label}
            aria-label={label}
            aria-current={view === key ? "page" : undefined}
            className={cn(
              "grid h-10 w-10 place-items-center rounded-lg transition-colors",
              view === key
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="h-5 w-5" />
          </button>
        ))}
      </nav>

      <div className="mt-auto flex flex-col items-center gap-4">
        <span
          title={online ? "Backend connected" : "Backend offline"}
          className={cn(
            "h-2.5 w-2.5 rounded-full",
            online ? "bg-[hsl(var(--success))]" : "bg-[hsl(var(--danger))]",
          )}
        />
        <button
          onClick={toggle}
          title="Toggle theme"
          aria-label="Toggle theme"
          className="grid h-10 w-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {theme === "dark" ? <Sun className="h-4.5 w-4.5" /> : <Moon className="h-4.5 w-4.5" />}
        </button>
      </div>
    </aside>
  );
}
