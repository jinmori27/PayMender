# Architecture and trust boundaries

## Decision pipeline

1. **Intake** verifies `X-Razorpay-Signature` over the untouched request bytes and deduplicates `x-razorpay-event-id`.
2. **Minimizer and queue** discard the raw bytes after HMAC verification and persist only an allowlisted processing envelope before returning. Slow model and API calls never block webhook acknowledgement.
3. **Enrichment** accepts official subscription-only events, then fetches the newest applicable subscription invoice and the latest failed order payment. It keeps only a typed, non-PII context.
4. **Normalizer** converts the minimized event and provider context into one bounded case schema. Subscription notes and demo fields cannot control money or diagnosis in real mode.
5. **Recovery model** scores every candidate action as recovery probability and expected net rupee value.
6. **Gemini advisor** produces a typed diagnosis, explanation, evidence list and English/Hinglish previews.
7. **Policy engine** treats the model output as untrusted advice and enforces lifecycle, amount, contact and idempotency rules.
8. **Operator gate** approves external actions. No customer message is sent by the MVP.
9. **Executor** reconciles the case reference before it creates a Razorpay test-mode Payment Link and stores the external reference exactly once.
10. **Recovery attribution** accepts only a captured `payment_link.paid` event that matches the active link, case, reference and amount.
11. **Audit trail** records both successful behavior and contained failures without retaining customer payloads.

## Trust matrix

| Component | Can propose | Can block | Can execute externally |
| --- | ---: | ---: | ---: |
| Logistic model | Yes | No | No |
| Gemini advisor | Yes | No | No |
| Deterministic policy | No | Yes | No |
| Human operator | Approve/reject | Yes | Indirectly |
| Razorpay executor | No | No | Test-mode link only |

## Persistence

- `subscription_cases`: current lifecycle snapshot.
- `webhook_events`: unique intake evidence containing only a PII-minimized typed envelope.
- `jobs`: persistent queue, retry count and atomic 60-second lease claim.
- `recovery_proposals`: model and policy outputs.
- `action_executions`: unique `(case_id, action)` execution reference.
- `audit_events`: application-enforced append-only human-readable decisions and failures within an evidence run; the explicit demo reset starts a new run, and SQLite is not claimed to be cryptographically immutable.
- `evaluation_runs`: serialized, reproducible batch results.

Every case has a `source` (`synthetic` or `razorpay_test`) and an `enrichment_state` (`pending`, `ready`, `failed` or `not_required`). Mode-scoped API queries prevent an existing synthetic database from leaking demo records into the Razorpay test queue, audit view or KPIs.

## Event ordering

Razorpay webhook delivery is at least once and may be out of order. A duplicate event ID is accepted as a successful no-op. Lifecycle ordering uses Razorpay's provider timestamp rather than local processing time. An older failure does not roll a case backward; a matching successful charge may close it.

## Production evolution

For production, replace SQLite and the in-process worker with managed PostgreSQL and a durable queue, replace the single local operator token with authenticated roles, add provider-backed reconciliation before every external action, introduce observability and key rotation, and complete compliance review. Those are deliberately outside the buildathon MVP.
