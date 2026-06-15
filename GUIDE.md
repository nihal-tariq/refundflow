# RefundFlow — Demo & Walkthrough Guide

A scripted guide for recording a Loom walkthrough of RefundFlow. It's written for a **senior AI engineer presenting to other engineers and stakeholders**, so it carries two parallel threads throughout:

- **🧠 AI thread** — what the agent is actually doing, why it's architected this way, and where the LLM is (and isn't) in the loop.
- **💼 Business thread** — why each decision path exists, what risk it manages, and what it would mean in a real support org.

Target length: **8–11 minutes**. A tight timing breakdown is at the end.

---

## 0. The one-sentence thesis (say this first)

> "RefundFlow is a refund-support agent where **the LLM never decides the refund** — deterministic tools and a policy engine make the call, the LLM only understands the customer and narrates the verdict — and that same engine powers both a text chat and a real-time voice agent."

Everything else in the demo is evidence for that sentence. Keep coming back to it.

---

## 1. Pre-flight checklist (do this before you hit record)

Have three things running and one thing decided.

```bash
# Terminal 1 — backend API
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev      # http://localhost:5173

# Terminal 3 — voice worker (only if demoing voice)
cd backend && source .venv/bin/activate
python voice_agent.py dev       # wait for "registered worker … agent_name=refundflow-voice"
```

Decide up front **which LLM mode** you're showing and *say it on camera*:

- **No key (template responder)** — fully deterministic, great for proving the decision is code, not vibes.
- **Real key (`LLM_PROVIDER`/`*_API_KEY` in `.env`)** — natural phrasing; better for the voice segment.

Recommended: run with a real key so voice sounds natural, but **explicitly point out** that pulling the key still produces the same *decisions*, only blunter wording.

Open two browser tabs: **chat** (`/`) and **admin** (`/?view=admin`). Have the voice worker terminal visible — you'll reference its logs during the voice segment.

---

## 2. The architecture story (≈90 seconds, before touching the UI)

Pull up the diagram in the README or `docs/ARCHITECTURE.md` and tell the story in one breath:

```
Customer (text OR voice)
        │
        ▼
   ┌─────────────────────────────────────────┐
   │  LangGraph workflow (text)  /  LiveKit    │
   │  voice agent (voice)                      │
   └─────────────────────────────────────────┘
        │  both call the SAME tools
        ▼
   Customer Lookup → Order Lookup → Policy Validation → Fraud Check
        │
        ▼
   DecisionService  →  APPROVE | DENY | ESCALATE   ← the verdict lives here
        │
        ▼
   Phrasing layer (LLM or template) → customer-safe message only
```

**🧠 Talking points:**
- Four deterministic tools gather facts; a fifth **decision node** combines them. The LLM orchestrates *which* tools to call and turns the result into English — it is **never** handed the authority to approve or deny.
- The phrasing layer receives a **pre-computed, customer-safe reason** — never the fraud score, never the rule IDs. Internal signals physically cannot leak into the customer reply because they're never passed to the part of the system that talks to the customer.
- Text and voice are **two front-ends over one decision engine**. That's the headline for the voice bonus: it's not a second implementation, it's the same `DecisionService` reached through a different modality.

**💼 Talking point:** every decision is **reproducible and auditable** — the same inputs always yield the same verdict, with named reason codes. That's what makes an agent shippable in a domain where "the model felt like denying it" is not an acceptable answer.

---

## 3. Demo script

### Act 1 — Text chat, the happy path (≈1 min)

1. In the chat tab, click the **"Happy path"** scenario chip (CUST-001, VIP, clean history).
2. Watch the agent reply: refund **approved**, friendly and short.

**🧠 Say:** "The chip fired a real agent run. Under the hood LangGraph just walked customer → order → policy → fraud → decision. Notice the customer message is one sentence — no mention of *why* internally, just the outcome and next step."

**💼 Say:** "This is the 80% case — in-window, low-risk, known-good customer. The whole point of automating it is that a human never has to touch it."

### Act 2 — The admin console: where the "why" lives (≈2.5 min)

Switch to the admin tab and replay/inspect the run you just did. Walk the tabs **in this order**:

1. **Timeline** — "Here's the graph executing node by node. Each lit node is a tool call or the decision step." Point out it streams live over **Server-Sent Events**, not polling.
2. **Reasoning** — "This is the agent's step-by-step thinking. Critically, *this* is what the customer never sees. The customer got one sentence; the operator gets the full rationale."
3. **Events** — filter to **tool calls**. "Every tool call with its inputs, outputs, and duration. This is the audit log — for a refund dispute you can show exactly what data drove the decision."
4. **State** — "The agent's full state after each node: the customer record, the order, the policy result, the fraud result. Fully inspectable."

**🧠 Say:** "This separation — slim customer reply, rich operator trace — is the architectural seam. In production you'd split these into a customer endpoint and an authenticated observability stream; here they're two views of one app for demo convenience."

**💼 Say:** "For a support org this is the difference between an agent you can trust and a black box. Every auto-decision is defensible after the fact."

### Act 3 — Denial and escalation (the interesting paths) (≈2 min)

Run two more chips and contrast them:

- **Repeat refund abuser** (CUST-004) → **Denied.** "Hard policy violation — over the refund-frequency cap. A hard violation always denies; there's no LLM discretion here."
- **VIP outside refund window** (CUST-007) → **Escalated.** "This is the most important path. The signals *conflict* — a valuable customer, but outside the 30-day window. Instead of auto-denying a VIP or rubber-stamping it, the decision engine **routes to a human**."

**🧠 Say:** "Escalation is a first-class outcome, not an error state. The rule is: hard violation → deny; clean → approve; **conflicting or low-confidence → escalate**. That's encoded in `DecisionService`, so it's testable and consistent."

**💼 Say:** "This is the business-judgment layer. Auto-approving every VIP is fraud-exposed; auto-denying them is churn-exposed. Escalation buys a human's judgment exactly where it's worth paying for, and nowhere else."

Optionally show **High fraud risk** (CUST-009 → denied on threshold) and **New customer borderline** (CUST-012 → escalated, low confidence) to round out the matrix. Emphasize: **the customer never hears the word "fraud" or sees a score** — pull up that denial's customer message to prove the phrasing is sanitized.

### Act 4 — The voice channel: same brain, different mouth (≈2 min)

This is the bonus and the differentiator. Back in the chat tab:

1. Click the **phone icon** in the composer. Narrate: "I'm not typing my customer ID anywhere."
2. When Maya picks up, she **greets you by name**.
3. Say: *"I'd like a refund for my headphones."* → Maya asks the reason → give one → she states the verdict.
4. Point at the **live transcript panel** (You / Maya) streaming above the button.
5. Glance at **Terminal 3** — show the worker logs: `voice session bound to CUST-001`, the tool calls firing.

**🧠 Say (this is the money explanation):**
- "Identity comes from the **room name** — the token endpoint mints `refundflow-<customer_id>`, and the worker parses it back out and **pre-loads the profile before the call even starts**. So Maya never asks me to read a customer ID aloud — which is good, because STT mangles alphanumeric IDs anyway. This mirrors the text channel's identity model exactly."
- "The pipeline is a classic cascade: Deepgram STT → a turn detector that knows when I've stopped talking → GPT-4o-mini with **function tools** → Cartesia TTS. But the function tool `check_refund_eligibility` calls the **identical** `FraudCheckTool → PolicyValidatorTool → DecisionService` chain the text graph uses."
- "So if I asked for this same refund by text, I'd get the **same verdict**. The LLM here orchestrates and narrates; it does not decide. Same contract as text, including the prompt rule that forbids saying 'fraud' or reading out scores."
- One nerd-credibility aside: "The turn detector is an ONNX model run through onnxruntime — no PyTorch needed; that scary 'PyTorch not found' log is cosmetic, it only wants the tokenizer."

**💼 Say:** "For the business this means voice and chat can't drift apart. There's no second rulebook to keep in sync — one policy engine, two channels. That's a maintenance and compliance win, not just a UX feature."

### Act 5 — History replay (≈30 sec)

Admin tab → **History**. Click an older session and let its full trace replay.

**Say:** "Every run is persisted to SQLite. Any past decision can be pulled up and replayed node-by-node — the audit trail isn't ephemeral."

---

## 4. The AI-engineering deep-dive (for the Q&A or as a closing montage)

Hit these if your audience is technical and you have time:

- **Why the LLM doesn't decide.** Determinism, auditability, and safety. The same inputs always produce the same verdict with named reason codes. The model is a natural-language interface, not a judge.
- **Tool design.** Tools are deterministic, narrowly typed, and **account-scoped** — in voice, `look_up_order` and `check_refund_eligibility` reject any order not on the caller's account, so a caller can't probe someone else's orders by guessing IDs.
- **Leak prevention as an architectural property.** The phrasing layer is only ever given a customer-safe reason. It's not "the prompt politely asks the model not to mention fraud" — the internal signals are never in that context window.
- **Graceful degradation.** No API key → deterministic template responder. The product *works* with zero LLM. The LLM improves wording, never correctness.
- **Provider-agnostic.** Anthropic, OpenAI, Gemini, Groq, Mistral, Ollama — swap via `.env`. (Mention the latest Claude models, e.g. Opus 4.8, are a drop-in for the phrasing/voice LLM.)
- **Voice as a thin adapter.** The hard part of a voice agent is usually keeping business logic in sync; here it's literally the same objects, imported. The voice file is mostly prompt + tool wrappers + pipeline wiring.

---

## 5. The business-layer narrative (for non-engineering stakeholders)

- **Deflection with a safety net.** Clear-cut refunds resolve instantly (approve/deny); ambiguous ones escalate. You automate volume without automating risk.
- **The policy is the product.** 7 rules — refund window, final-sale/digital exclusions, frequency cap, fraud thresholds, evidence requirements — encoded in `refund_policy.md` and enforced in code. Change the policy, change the behavior; no retraining.
- **Auditability = trust.** Every decision has a named reason code and a full trace. Disputes, compliance, and QA all have a paper trail.
- **Channel parity = lower cost.** One decision engine behind both text and voice means one thing to test, secure, and update.

---

## 6. Likely questions (have answers ready)

- *"What if the LLM hallucinates a refund?"* → It can't approve anything; the verdict comes from `DecisionService`. The worst a hallucination does is phrase the **already-decided** outcome awkwardly, and tool outputs constrain even that.
- *"How does voice know who's calling?"* → Room name carries the customer ID; the worker pre-loads the profile. (Demo-scope caveat: it trusts that ID — production would verify token ownership server-side.)
- *"Why not let the model read the policy and decide?"* → Reproducibility and auditability. A policy engine gives identical, explainable results every time; an LLM doesn't, and you can't defend an LLM's judgment in a chargeback dispute.
- *"Is voice a separate codebase?"* → No — same tools, same decision engine, imported into a LiveKit worker. ~300 lines of pipeline + prompt.
- *"Production gaps?"* → Auth (no real authn in the demo), server-side identity verification for voice rooms, splitting the customer vs. admin responses, and secret management (rotate any committed key).

---

## 7. Timing cheat-sheet

| Segment | Time | Don't skip |
|---|---|---|
| Thesis + architecture | 1:30 | "LLM never decides" |
| Act 1 — happy path | 1:00 | sanitized customer reply |
| Act 2 — admin console | 2:30 | Reasoning vs. customer message split |
| Act 3 — deny + escalate | 2:00 | escalation = conflicting signals |
| Act 4 — voice | 2:00 | same engine, identity-from-room |
| Act 5 — history replay | 0:30 | persisted audit trail |
| **Total** | **~9:30** | |

**Closing line:** "One policy engine, deterministic and auditable, reached through both a typed chat and a live voice call — the LLM makes it human, but it never makes the decision."
