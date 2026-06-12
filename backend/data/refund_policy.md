# RefundFlow — Refund Policy (v2.3)

This document is the single source of truth for refund adjudication. The
`policy_validator` tool encodes these rules; the decision node routes on the
result. Each rule has a **rule id**, a **severity**, and a **reason code** that
appears in the agent reasoning log and the admin dashboard.

> Severity legend:
> - `HARD` — a violation that, on its own, denies the refund.
> - `SOFT` — a signal that, when it conflicts with a strong positive signal,
>   routes to **human escalation** rather than an automatic deny.

---

## R1 — Refund Window  (severity: HARD)
- **Rule:** Refunds are only permitted within **30 days** of the purchase date.
- **Reason code:** `WINDOW_EXCEEDED`
- **Exception:** For **VIP** customers the window violation is downgraded to
  `SOFT` (it conflicts with their standing), so it **escalates** rather than
  auto-denies.

## R2 — Final Sale Items  (severity: HARD)
- **Rule:** Products marked **final sale** are non-refundable.
- **Reason code:** `FINAL_SALE`

## R3 — Digital Goods  (severity: HARD)
- **Rule:** **Digital products** (software licenses, downloads, subscriptions)
  are non-refundable once delivered.
- **Reason code:** `DIGITAL_NON_REFUNDABLE`

## R4 — Refund Frequency  (severity: HARD)
- **Rule:** A maximum of **3 approved refunds** is allowed in any rolling
  **6-month** window. A request that would be the 4th is denied.
- **Reason code:** `REFUND_LIMIT_EXCEEDED`

## R5 — Fraud Risk  (severity: HARD / SOFT)
- **Rule:** A fraud risk score **≥ 0.70** denies the refund (`HARD`).
- **Borderline band:** A score within **0.15** below the threshold
  (i.e. **0.55–0.69**) is `SOFT` — it escalates when the customer otherwise has
  strong positive signals (VIP, high lifetime value, or clean refund history).
- **Reason code:** `FRAUD_THRESHOLD` (hard) / `FRAUD_BORDERLINE` (soft)

## R6 — Damaged / Defective Claims  (severity: SOFT)
- **Rule:** Claims citing **damage or defect** require photographic evidence.
- **Behavior:** When evidence is absent, the claim **escalates** to a human
  agent for evidence collection rather than being denied outright.
- **Reason code:** `EVIDENCE_REQUIRED`

## R7 — Data Completeness  (severity: SOFT)
- **Rule:** Adjudication requires a valid customer, a matching order, and a
  stated reason. Missing or mismatched data **escalates**.
- **Reason code:** `INSUFFICIENT_DATA`

---

## Decision Matrix

| Condition | Outcome |
|---|---|
| No violations and fraud score below borderline band | **APPROVED** |
| Any `HARD` violation present | **DENIED** |
| Only `SOFT` signals present, conflicting with strong positives | **ESCALATED** |
| Required data missing or mismatched | **ESCALATED** |

When a refund is **escalated**, the agent must record *why* the signals
conflicted so a human reviewer has full context.
