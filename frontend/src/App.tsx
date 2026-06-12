import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { Toaster } from "@/components/ui/toast";
import { WorkspacePage } from "@/pages/WorkspacePage";

/** Process-wide React Query client with sensible demo defaults. */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, staleTime: 10_000 },
  },
});

/**
 * Application root: wires the query client, the global error boundary, the
 * toaster, and the single workspace page.
 */
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <WorkspacePage />
        <Toaster />
      </ErrorBoundary>
    </QueryClientProvider>
  );
}
