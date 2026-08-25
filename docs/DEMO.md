# Five-minute pitch and demo

## 0:00–0:35 — Problem

“A failed recurring payment is not one problem. Issuer downtime should wait, an expired card needs an update, and a halted mandate may need a recovery link. Blind retries waste trust. PayMender chooses the next best bounded action and proves the rupees it recovers.”

## 0:35–1:10 — Architecture

Show the trust boundary: Razorpay webhook → ML scores → Gemini typed explanation → deterministic policy → human approval → test-mode execution → audit.

## 1:10–2:15 — Safe internal action

Open the issuer-downtime pending case. Show that the model may value multiple actions, but the policy forces `WAIT_FOR_RETRY` because Razorpay already has a retry scheduled.

## 2:15–3:15 — Approval-gated recovery

Open the expired-card halted case. Show:

- expected-value scores;
- English and Hinglish previews;
- evidence chips;
- operator approval;
- one test-mode Payment Link reference;
- explicit “no notification sent”.

With real sandbox credentials, complete the test Payment Link and show the matching `payment_link.paid` webhook move the amount into confirmed recovered revenue. A normal recurring `subscription.charged` event closes the case but is not credited to PayMender.

## 3:15–4:05 — Measured batch evidence

Run the evaluation. State clearly that it is synthetic. Compare PayMender with all three baselines and point out contacts per recovery and policy overrides, not only gross rupees.

## 4:05–4:40 — Failure handling

Inject the duplicate webhook or Gemini quota scenario. Show the contained failure in the audit trail and explain that the LLM never owns execution authority.

## 4:40–5:00 — Close

“PayMender is not an AI that moves money because it feels confident. It is a measured recovery system where AI proposes, policy bounds, humans approve and every rupee action is explainable.”

Before recording: hide `.env.local`, terminal history and dashboard account identifiers. Verify video sharing access in a private browser window.
