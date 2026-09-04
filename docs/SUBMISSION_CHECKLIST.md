# Submission checklist

## Repository

- [ ] Public repository opens in a signed-out browser.
- [ ] Clean clone succeeds using only `.env.example` plus documented local secrets.
- [ ] `scripts\Verify-PayMender.ps1` passes.
- [ ] `.env`, `.env.local`, SQLite files, build output and model artifacts are not tracked.
- [ ] No API key, webhook secret, operator token, personal data or account screenshot is present.
- [ ] Architecture, evaluation, security, rehearsal and limitations documents are current.

## Real test evidence

- [ ] At least five genuine signed failure events entered across at least three Razorpay test subscriptions.
- [ ] Invoice enrichment produced the exact INR amount without custom notes.
- [ ] Two actions were explicitly approved and at least one Payment Link was created only after approval.
- [ ] A matching captured `payment_link.paid` webhook updated recovered rupees.
- [ ] An ordinary `subscription.charged` event was not attributed to PayMender.
- [ ] Real Payment Link count is five or fewer.
- [ ] One policy stop and one duplicate delivery are correlated by provider, case and audit IDs.

## Synthetic evidence

- [ ] Ten fixed 200-case held-out batches completed.
- [ ] PayMender is compared with always-wait, always-link and fixed-rules baselines.
- [ ] Mean and standard deviation are shown for all required metrics.
- [ ] The synthetic disclaimer is visible beside the results.
- [ ] Duplicate delivery, Gemini fallback, Razorpay 5xx and worker recovery are demonstrated.

## Video and form

- [ ] Video duration is 4:30 to 5:00.
- [ ] The live loop, approval, verified recovery, batch evidence, audit and one failure are visible.
- [ ] No `.env.local`, terminal history, key, webhook secret, account identifier or personal information is visible.
- [ ] Video access works in a signed-out browser.
- [ ] Repository URL and final product name are consistent in the form and video.
