# Security and safety notes

- Only `RAZORPAY_MODE=test` is accepted. A non-test key ID fails configuration validation.
- Webhook signatures use HMAC-SHA256 over the untouched body.
- Duplicate events are identified by `x-razorpay-event-id` and stored once.
- Webhook bodies are capped at 256 KiB. HMAC is verified in memory, then only an allowlisted PII-minimized envelope is stored; raw request bytes are discarded.
- Secrets are read from ignored `.env.local`; logs and audit messages contain exception classes, never credentials or raw secrets.
- Operator APIs require a constant-time checked `X-Operator-Token`; the frontend holds this token only in memory.
- Session attempts are limited to 10 per 15 minutes per client, webhooks to 60 per minute and evaluations to two per minute; `429` responses include `Retry-After`.
- Gemini receives an allowlist of non-identifying case features and action scores, never names, URLs, external IDs or Razorpay credentials.
- Invoice enrichment accepts only exact subscription matches, INR currency and positive bounded amounts. Customer name, email, phone, address and other provider PII are discarded before persistence or Gemini use.
- Gemini cannot call tools, change state, send messages or create links.
- Gemini requests allow one total attempt, a 15-second timeout and at most 512 output tokens. Returned evidence strings are length-bounded and schema-validated.
- Payment Link amount comes from the normalized outstanding amount and cannot be edited in the approval UI.
- Recovery links are restricted to halted subscriptions and one active link per case.
- Link creation first reconciles the unique case reference with Razorpay, so an ambiguous timeout cannot silently create a duplicate.
- Returned links require HTTPS, an exact configured hostname, no embedded credentials, and exact ID, amount, currency, reference and note matches.
- Recovered rupees require a captured `payment_link.paid` event matching the active link, case reference, INR amount and internal case note.
- Customer contact stops at three interventions in seven days.
- The test executor caps real Payment Links at five for the submission demo.
- Generated English/Hinglish text remains a preview; there is no delivery integration.
- Demo mode cannot call Razorpay even when credentials are configured. The Reliability Lab uses injected local fakes and real internal containment paths.
- Runtime model startup trains deterministic in-memory state and never deserializes a replaceable model artifact.
- Synthetic and Razorpay test cases are source-tagged and mode-filtered across queue, case detail, approvals, audit views and KPIs.
- Security headers prevent framing, MIME sniffing and permissive referrer leakage. The production SPA is served from its fixed static root.
- Public health reveals only liveness and display name; configuration diagnostics require operator authentication.

The audit history is append-only through normal application operations within an evidence run. The explicit demo reset clears the synthetic run. It is not a cryptographic ledger, and SQLite administrators can still alter the file.

All bundled demo customers are fictional. Do not add real customer payloads to fixtures, screenshots or the public repository.
