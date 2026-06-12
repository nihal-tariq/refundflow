import { useEffect } from "react";
import { CustomerExperience } from "@/components/chat/CustomerExperience";
import { AdminConsole } from "@/components/dashboard/AdminConsole";
import { Sidebar } from "@/layouts/Sidebar";
import { useAppStore } from "@/store/useAppStore";

/**
 * The single application page: a sidebar rail plus the active view.
 *
 * The customer chat is the default, primary experience; the admin console is
 * reachable via the sidebar (or deep-linked with `?view=admin`). Pages contain
 * no business logic — only composition.
 */
export function WorkspacePage() {
  const { view, setView } = useAppStore();

  // Deep-link support: /?view=admin opens the console directly (useful for
  // demos and for operators bookmarking the observability surface).
  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("view");
    if (param === "admin" || param === "chat") setView(param);
  }, [setView]);

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <main className="min-h-0 min-w-0 flex-1">
        {view === "chat" ? <CustomerExperience /> : <AdminConsole />}
      </main>
    </div>
  );
}
