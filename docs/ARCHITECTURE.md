# Architecture and trust boundaries

## Decision pipeline

1. **Intake** verifies `X-Razorpay-Signature` over the untouched request bytes and deduplicates `x-razorpay-event-id`.
2. **Queue** stores the event before returning. Slow model and API calls never block webhook acknowledgement.
3. **Normalizer** validates supported Razorpay payloads and converts subscription events into one bounded case schema. Raw bodies are retained only until processing finishes or retries are exhausted.
4. **Recovery model** scores every candidate action as recovery probability and expected net rupee value.
5. **Gemini advisor** produces a typed diagnosis, explanation, evidence list and English/Hinglish previews.
6. **Policy engine** treats the model output as untrusted advice and enforces lifecycle, amount, contact and idempotency rules.
7. **Operator gate** approves external actions. No customer message is sent by the MVP.
8. **Executor** reconciles the case reference before it creates a Razorpay test-mode Payment Link and stores the external reference exactly once.
9. **Recovery attribution** accepts only a captured `payment_link.paid` event that matches the active link, case, reference and amount.
10. **Audit trail** records both successful behavior and contained failures without retaining customer payloads.

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
- `webhook_events`: unique intake evidence with payloads redacted after processing.
- `jobs`: persistent queue, retry count and expiring lease.
- `recovery_proposals`: model and policy outputs.
- `action_executions`: unique `(case_id, action)` execution reference.
- `audit_events`: append-only human-readable decisions and failures.
- `evaluation_runs`: serialized, reproducible batch results.

## Event ordering

Razorpay webhook delivery is at least once and may be out of order. A duplicate event ID is accepted as a successful no-op. Lifecycle ordering uses Razorpay's provider timestamp rather than local processing time. An older failure does not roll a case backward; a matching successful charge may close it.

## Production evolution

For production, replace SQLite and the in-process worker with managed PostgreSQL and a durable queue, replace the single local operator token with authenticated roles, fetch the authoritative outstanding invoice before link creation, introduce observability and key rotation, and complete compliance review. Those are deliberately outside the buildathon MVP.
