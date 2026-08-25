# Security and safety notes

- Only `RAZORPAY_MODE=test` is accepted. A non-test key ID fails configuration validation.
- Webhook signatures use HMAC-SHA256 over the untouched body.
- Duplicate events are identified by `x-razorpay-event-id` and stored once.
- Webhook bodies are capped at 256 KiB. Supported event schemas, identifiers, counters and amounts are validated before storage.
- Secrets are read from ignored `.env.local`; logs and audit messages contain exception classes, never credentials or raw secrets.
- Operator APIs require a constant-time checked `X-Operator-Token`; the frontend holds this token only in memory.
- Gemini receives an allowlist of non-identifying case features and action scores, never names, URLs, external IDs or Razorpay credentials.
- Gemini cannot call tools, change state, send messages or create links.
- Payment Link amount comes from the normalized outstanding amount and cannot be edited in the approval UI.
- Recovery links are restricted to halted subscriptions and one active link per case.
- Link creation first reconciles the unique case reference with Razorpay, so an ambiguous timeout cannot silently create a duplicate.
- Recovered rupees require a captured `payment_link.paid` event matching the active link, case reference, INR amount and internal case note.
- Customer contact stops at three interventions in seven days.
- The test executor caps real Payment Links at five for the submission demo.
- Generated English/Hinglish text remains a preview; there is no delivery integration.
- Processed webhook bodies are reduced to event metadata; permanently failed jobs are also redacted after the final retry.
- Security headers prevent framing, MIME sniffing and permissive referrer leakage. The production SPA is served from its fixed static root.

All bundled demo customers are fictional. Do not add real customer payloads to fixtures, screenshots or the public repository.
