import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message?: string;
}

/**
 * Top-level error boundary.
 *
 * Catches render-time errors anywhere in the tree and shows a recoverable
 * fallback instead of a blank screen — a baseline production requirement.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("UI ErrorBoundary caught:", error, info);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        <AlertTriangle className="h-10 w-10 text-[hsl(var(--danger))]" />
        <div>
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            {this.state.message ?? "An unexpected UI error occurred."}
          </p>
        </div>
        <Button onClick={() => window.location.reload()}>Reload app</Button>
      </div>
    );
  }
}
