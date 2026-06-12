/**
 * Global UI state (Zustand).
 *
 * Holds cross-component state that is not server cache: the selected customer,
 * the chat transcript, and the *live* execution stream (events + status) for the
 * active session. Server data (customer profiles, traces) lives in React Query,
 * not here — this store is strictly client/session state.
 */

import { create } from "zustand";
import type { AgentEvent, Decision, RefundDecisionResponse } from "@/types";

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  decision?: Decision | null;
  pending?: boolean;
}

export type RunStatus = "idle" | "running" | "completed" | "failed";

export type AppView = "chat" | "admin";

interface AppState {
  // Navigation (sidebar)
  view: AppView;
  setView: (view: AppView) => void;

  // Selection
  customerId: string;
  setCustomerId: (id: string) => void;

  // Chat transcript
  messages: ChatMessage[];
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  resetChat: () => void;

  // Active execution
  sessionId: string | null;
  status: RunStatus;
  events: AgentEvent[];
  decision: RefundDecisionResponse | null;
  startRun: (sessionId: string) => void;
  pushEvent: (event: AgentEvent) => void;
  finishRun: (decision: RefundDecisionResponse | null, status: RunStatus) => void;

  // Replay (viewing a historical session in the dashboard)
  replaySessionId: string | null;
  setReplaySession: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  view: "chat",
  setView: (view) => set({ view }),

  customerId: "CUST-001",
  setCustomerId: (id) => set({ customerId: id }),

  messages: [],
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (id, patch) =>
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),
  resetChat: () => set({ messages: [], decision: null, events: [], sessionId: null, status: "idle" }),

  sessionId: null,
  status: "idle",
  events: [],
  decision: null,
  startRun: (sessionId) =>
    set({ sessionId, status: "running", events: [], decision: null, replaySessionId: null }),
  pushEvent: (event) => set((state) => ({ events: [...state.events, event] })),
  finishRun: (decision, status) => set({ decision, status }),

  replaySessionId: null,
  setReplaySession: (id) => set({ replaySessionId: id }),
}));
