# Five-minute pitch and demo

Record at 4:30 to 5:00. Use the real Razorpay test flow for the recovery loop and the synthetic mode only for measured evaluation and injected failures. Never describe synthetic outcomes as merchant performance.

## 0:00–0:35 — Problem

“A failed recurring payment is not one problem. Issuer downtime should wait, an expired card needs an update, and a halted mandate may need a recovery link. Blind retries waste trust. PayMender chooses the next best bounded action and proves the rupees it recovers.”

## 0:30-1:10 - Architecture and intake

Show the trust boundary: signed Razorpay webhook -> invoice/payment enrichment -> ML scores -> Gemini typed explanation -> deterministic policy -> human approval -> test-mode execution -> audit.

## 1:10-2:05 - Real halted subscription

Receive a genuine `subscription.halted` test webhook. Show the case first in "Verifying invoice context" and then "Ready for review" with the exact provider amount and failed-payment reason.

## 2:05-3:10 - Approval-gated recovery

Open the expired-card halted case. Show:

- expected-value scores;
- English and Hinglish previews;
- evidence chips;
- operator approval;
- one test-mode Payment Link reference;
- explicit “no notification sent”.

Open the created test link, complete the test payment and show the matching `payment_link.paid` webhook move the amount into confirmed recovered revenue. A normal recurring `subscription.charged` event closes the case but is not credited to PayMender.

## 3:10-4:00 - Measured batch evidence

Run the evaluation. State clearly that it is synthetic. Compare PayMender with all three baselines and point out contacts per recovery and policy overrides, not only gross rupees.

## 4:00-4:35 - Failure handling

Inject the duplicate webhook or Gemini quota scenario. Show the contained failure in the audit trail and explain that the LLM never owns execution authority.

## 4:35-4:55 - Close

“PayMender is not an AI that moves money because it feels confident. It is a measured recovery system where AI proposes, policy bounds, humans approve and every rupee action is explainable.”

Before recording: hide `.env.local`, terminal history and dashboard account identifiers. Verify video sharing access in a private browser window.
