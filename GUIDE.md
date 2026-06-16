# RefundFlow AI — Demo Guide

This guide is a presenter's companion for walking someone through the repository and live demo. It covers setup, the demo script, what to highlight at each step, and answers to questions an audience typically asks.

---

## Pre-demo checklist

Run through this before anyone joins:

- [ ] `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
- [ ] `cd frontend && npm run dev` (separate terminal)
- [ ] Browser open at **http://localhost:5173** (chat view) and **http://localhost:5173/?view=admin** in another tab
- [ ] `backend/.env` has `GROQ_API_KEY` (or another LLM key) set — confirm with a quick test message
- [ ] (Optional) `python voice_agent.py dev` in a third terminal if demoing voice
- [ ] All three processes healthy — check `http://localhost:8000/health`

**Reset state between demo runs:** SQLite persists sessions. You do not need to clear it — the history list in the dashboard makes prior runs a feature, not a problem. But if you want a clean slate: `rm backend/refundflow.db` and restart uvicorn.

---

## The story in one sentence

> "A customer asks for a refund. A LangGraph agent looks them up, checks the policy, runs a fraud check, and makes a deterministic decision — the LLM never decides, it only phrases the reply. The admin console streams every step in real time."

That one sentence contains the three things worth emphasizing:

1. **Deterministic decision** — the verdict is computed, not generated
2. **LLM as stylist, not judge** — separates safety from capability
3. **Real-time observability** — the admin can see every tool call as it happens

---

## Demo script

### Act 1: the happy path (2 min)

1. Open the chat tab. Select **CUST-001** from the customer selector (or type it in).
2. Click the **"Happy path — CUST-001"** scenario chip.

   > *"This is Sarah Chen, a VIP customer. She's asking for a refund. Let's watch the agent work."*

3. While the response loads, switch to the **admin console** tab in real time to show the timeline lighting up node by node.

   > *"These are SSE events streaming from the server. The browser opened the event stream before firing the HTTP request, so no event is ever missed."*

4. Walk through the **Events** tab:
   - `execution_started` → `node_entered` → `tool_called` (customer_lookup) → `tool_completed`
   - Repeat for order_lookup, policy_validation, fraud_check, decision
   - At the bottom: `execution_completed` and then ✨ **LLM Response** `groq:llama-3.3-70b-versatile`

   > *"The last event — LLM Response — is the phrasing layer. The decision was already made deterministically. The LLM only turns 'APPROVED + reason_code' into a warm sentence the customer actually reads."*

5. Open the **Reasoning** tab:
   > *"This is what the customer never sees. Every tool output, every policy check, the fraud score. Ops can replay any past run from the History tab and see exactly why a decision was made."*

6. Open the **State** tab:
   > *"The agent state after every node — customer profile, order details, policy violations, fraud result."*

### Act 2: a denial and an escalation (2 min)

7. Go back to chat. Try **CUST-004** — "Repeat refund abuser".

   > *"This customer has made 4 refunds in 6 months. Our policy allows 3. It's a HARD violation — the agent denies immediately."*

8. Show the Events tab → policy_validation → `REFUND_LIMIT_EXCEEDED` (HARD).

9. Now try **CUST-007** — "VIP outside refund window".

   > *"VIP customer, but the 30-day window has lapsed. That would normally be a HARD deny — but the policy has an exception: for VIPs, window violations are downgraded to SOFT, so conflicting signals escalate to a human instead of auto-denying. The policy document is the single source of truth; the agent's behavior is just code that reads it."*

### Act 3: the conversational loop (2 min)

10. With CUST-001 after the APPROVED decision, type in the chat: *"wait what? why was this approved?"*

    > *"After a decision, follow-up messages go through a separate conversational LangGraph — the Chat LangGraph — which has full message history via LangGraph's `add_messages` reducer. The bot knows the decision was already made and can respond in context."*

11. Type: *"ok bye"*

    > *"It says goodbye in context. Before we added the chat loop, 'bye' after any decision would re-trigger the canned greeting. Now it's a real back-and-forth."*

### Act 4: no LLM = no problem (1 min)

12. Optionally show `backend/.env` or explain:

    > *"If I remove the API key and restart the server, the app falls back to deterministic template responses. The refund decision is identical — because the LLM never touched it. Only the phrasing changes. The demo always works."*

### Act 5: voice (3 min, if set up)

13. With the voice worker running, select CUST-001 and click the **phone icon**.

    > *"This is a LiveKit Agents voice pipeline: browser mic → WebRTC → Deepgram STT → turn detector → GPT-4o-mini with function tools → Cartesia TTS. Maya greets by name because the LiveKit room name encodes the customer ID — no need to ask them to speak it, which STT would mangle anyway."*

14. Say: *"Hi Maya, I'd like a refund for my headphones."*

    > *"Maya calls `check_refund_eligibility`, which runs the identical fraud + policy + decision chain as the text channel. The LLM in the voice pipeline orchestrates tool calls and narrates the verdict — it never computes it. Text and voice are two front-ends over one decision engine."*

---

## Key talking points

### "Why not just let the LLM decide?"

> "Two reasons. First, reproducibility: LLM outputs are non-deterministic — the same input can produce different verdicts on different runs, which is unacceptable for a financial decision. Second, auditability: when a customer disputes a denial, you need to show exactly which policy rule triggered it, not ask the LLM to explain itself. Deterministic tools give you that."

### "The LLM knows the fraud score, right?"

> "No — that's the key. The LLM phrasing prompt only receives a customer-safe reason string like 'the request could not be verified by our automated checks'. The raw fraud score (0.86), the policy rule ID (FRAUD_THRESHOLD), and the internal rationale are deliberately kept out of the LLM prompt. They live in the admin dashboard, never in the chat."

### "What if the LLM API is down?"

> "The app degrades to deterministic template responses. The refund decision is unaffected because the LLM never touched it. Only the phrasing becomes more templated. The fallback is tested alongside the main path."

### "How does the voice channel know who the customer is?"

> "The backend mints a LiveKit room named `refundflow-<customer_id>`. The voice worker parses the customer ID out of the room name and pre-loads the profile before the call starts. The customer never says their ID aloud — which STT would mangle anyway."

### "What's MemorySaver doing?"

> "LangGraph's MemorySaver is a checkpointer. The refund graph checkpoints after every node so the state can be inspected or resumed. The chat graph uses a second MemorySaver keyed by conversation_id — every turn appends to the persisted message history via the `add_messages` reducer, so the LLM always sees the full thread."

### "How would this scale beyond one process?"

> "The EventBus is the one seam. Right now it's an in-process `asyncio.Queue`. To scale horizontally, you swap it for Redis pub/sub — one line of code in `events.py`. The rest of the stack (FastAPI, SQLAlchemy, LangGraph) is already stateless per request."

---

## Architecture in 30 seconds

Point at the code and say:

> *"The flow is: `ChatService` does slot-filling and intent classification, then calls `RefundService`, which runs the LangGraph. The five nodes call deterministic tools; tool outputs flow into `DecisionService`, which is a pure function — no LLM, no network. The LLM only touches `LLMService.phrase_decision()` at the very end. The graph emits SSE events to the `EventBus`; the browser reads them via `EventSource`. All events are also persisted to SQLite for the History tab."*

Files to point at:
- [backend/app/agents/graph.py](backend/app/agents/graph.py) — 5-node linear graph definition
- [backend/app/services/decision_service.py](backend/app/services/decision_service.py) — pure decision logic
- [backend/app/services/llm_service.py](backend/app/services/llm_service.py) — phrasing layer, never adjudicates
- [backend/app/agents/chat_graph.py](backend/app/agents/chat_graph.py) — conversational loop with memory
- [backend/app/observability/events.py](backend/app/observability/events.py) — EventBus pub/sub
- [frontend/src/hooks/useAgentRun.ts](frontend/src/hooks/useAgentRun.ts) — SSE + POST orchestration

---

## Things NOT to do during a demo

- **Don't ask for a refund before selecting a customer.** The system will ask for an unknown customer ID.
- **Don't type the order ID as just numbers** (e.g., "1001"). The LLM resolver handles it, but if LLM is down it may not match. Use "ORD-1001" or the product name.
- **Don't hit refresh mid-run.** The SSE stream is keyed to the session ID generated client-side. A refresh loses it and the run completes silently.
- **Don't demo voice without running `voice_agent.py download-files` first.** The ONNX model is not in the repo; the first run fetches it and hangs if it hasn't been downloaded.
- **Don't set `GROQ_BASE_URL` or `LLM_BASE_URL` for standard Groq.** The Groq SDK adds its own path; setting the base URL creates a doubled-path 404 that silently falls back to templates.

---

## Folder tour (5-min code walk)

Start at the backend:

```
backend/app/
├── agents/
│   ├── graph.py          ← Show: 5 add_edge calls. "This IS the architecture."
│   └── chat_graph.py     ← Show: add_messages reducer + MemorySaver
├── tools/
│   └── policy_validator.py ← Show: 7 rule checks, returns PolicyResult
├── services/
│   ├── decision_service.py ← Show: pure function, no LLM, exhaustively tested
│   └── llm_service.py      ← Show: phrase_decision — internal rationale param is intentionally unused
├── observability/
│   └── events.py           ← Show: EventBus — the Redis seam
└── config/settings.py      ← Show: all defaults safe, app boots with zero config
```

Then frontend:

```
frontend/src/
├── hooks/useAgentRun.ts    ← Show: subscribeToEvents → fireOnce pattern (stream first)
├── store/useAppStore.ts    ← Show: Zustand — messages, events, run status
└── lib/timeline.ts         ← Show: pure functions, no React — derives node status from events
```

---

## Quick reference: env vars

| Variable | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | `groq`, `anthropic`, `openai`, `google_genai`, `mistral`, `ollama` | `anthropic` |
| `LLM_MODEL` | Model ID for the selected provider | `claude-opus-4-8` |
| `GROQ_API_KEY` | Groq API key | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL | — |
| `LIVEKIT_API_KEY` | LiveKit API key | — |
| `LIVEKIT_API_SECRET` | LiveKit API secret | — |
| `NODE_DELAY_SECONDS` | Per-node SSE animation delay (0 to disable) | `0.35` |

All settings have safe defaults. The app boots and runs the full demo with zero env vars set.
