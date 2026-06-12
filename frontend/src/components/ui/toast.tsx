/**
 * Minimal toast system (store + renderer).
 *
 * A tiny Zustand store holds active toasts; `useToast().toast(...)` pushes one
 * and it auto-dismisses. `<Toaster />` renders them with Framer Motion. Avoids a
 * heavyweight dependency while matching the SaaS look the brief asks for.
 */

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import { create } from "zustand";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";

interface Toast {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastStore {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

let counter = 0;

const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = ++counter;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

/** Hook exposing an imperative `toast` function. */
export function useToast() {
  const push = useToastStore((s) => s.push);
  return {
    toast: (title: string, opts?: { description?: string; tone?: ToastTone }) =>
      push({ title, description: opts?.description, tone: opts?.tone ?? "info" }),
  };
}

const ICONS = {
  success: <CheckCircle2 className="h-4 w-4 text-[hsl(var(--success))]" />,
  error: <XCircle className="h-4 w-4 text-[hsl(var(--danger))]" />,
  info: <Info className="h-4 w-4 text-primary" />,
};

/** Fixed-position renderer for active toasts. */
export function Toaster() {
  const { toasts, dismiss } = useToastStore();
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            onClick={() => dismiss(toast.id)}
            className={cn(
              "pointer-events-auto cursor-pointer rounded-lg border border-border bg-card p-3 shadow-lg",
            )}
          >
            <div className="flex items-start gap-2">
              {ICONS[toast.tone]}
              <div>
                <p className="text-sm font-medium">{toast.title}</p>
                {toast.description && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {toast.description}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
