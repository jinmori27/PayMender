# Razorpay test-mode rehearsal

This is the only external acceptance step. It uses test credentials and test money, but it creates real objects in the connected Razorpay test account. Keep the public endpoint active only for the rehearsal.

## 1. Prepare real mode

1. Keep all credentials in ignored `.env.local`.
2. Set `DEMO_MODE=false` and keep `RAZORPAY_MODE=test`.
3. Confirm `RAZORPAY_KEY_ID` begins with `rzp_test_`.
4. Use a distinct `RAZORPAY_WEBHOOK_SECRET`; it is not the API key secret.
5. Run `frontend\pnpm build` through `scripts\Verify-PayMender.ps1`, then start the app with `scripts\Start-PayMender.ps1`.
6. Open `http://127.0.0.1:8000`. A fresh real-mode queue is empty even if the SQLite file still contains synthetic demo records.

## 2. Expose only the webhook endpoint

Razorpay cannot deliver to localhost. Start a temporary public HTTPS tunnel to `http://localhost:8000`; Razorpay's webhook testing guide recommends zrok. Copy the HTTPS origin and configure this endpoint in the Razorpay test dashboard:

```text
https://YOUR-TEMPORARY-HOST/api/webhooks/razorpay
```

Use the same webhook secret as `.env.local` and subscribe to:

- `subscription.pending`
- `subscription.halted`
- `subscription.charged`
- `subscription.cancelled`
- `subscription.completed`
- `payment_link.paid`

Do not expose API keys in the tunnel command, URL, terminal recording or webhook dashboard screenshots.

## 3. Create the provider-authentic batch

1. In Razorpay test mode, create at least three subscriptions under test plans.
2. Authenticate them using Razorpay's test flow.
3. Produce at least five signed failure events across those subscriptions, including pending and halted states. Razorpay documents that a test subscription reaches halted after four failed attempts.
4. Confirm each provider event ID receives a 2XX response and is correlated to one PayMender webhook record.
5. In the command center, watch each case move from `Fetching amount` to a verified outstanding amount.
6. Verify the audit shows selected invoice and failed-payment context without customer name, email, phone or address.
7. Demonstrate one duplicate event ID being accepted as an idempotent no-op and one policy stop where no external action is possible.

If enrichment fails after three worker attempts, the case must say `Needs attention`, propose no money action and retain only a redacted event envelope.

## 4. Approve and recover

Before approval, verify all of these on screen:

- status is `halted`;
- the amount exactly matches the Razorpay test invoice;
- currency is INR;
- contacts in seven days are below three;
- no active recovery link exists;
- the preview says notifications are disabled and the link expires in 48 hours.

Approve two gated actions, with at least one `CREATE_RECOVERY_LINK`. Use **Open test link** to complete one captured Razorpay test payment. PayMender must then receive a matching `payment_link.paid` event and move exactly that amount into **Confirmed recovered**.

Reject the result if an unrelated payment, mismatched link, mismatched amount, non-captured payment or ordinary `subscription.charged` event is counted as PayMender recovery. A recurring charge is an organic resolution only.

## 5. Evidence to capture

- halted subscription ID with other dashboard identifiers cropped;
- pending and ready enrichment states;
- AI diagnosis, deterministic gate and human approval as three visibly separate layers;
- exact amount and test-mode warning;
- created link reference, never credentials;
- matching captured webhook and recovered rupees;
- a correlation table containing at least five event IDs, three subscription IDs, two proposal/approval IDs, one execution ID and the associated audit IDs;
- audit event for one contained failure;
- synthetic evaluation with its disclaimer visible.

Stop the tunnel after the rehearsal. Keep the real Payment Link count at five or fewer.

## Official references

- [Subscription webhook payloads](https://razorpay.com/docs/webhooks/subscriptions/)
- [Webhook validation and test delivery](https://razorpay.com/docs/webhooks/validate-test/)
- [Fetch subscription invoices](https://razorpay.com/docs/api/payments/subscriptions/fetch-invoices/)
- [Fetch payments for an order](https://razorpay.com/docs/api/orders/fetch-payments/)
- [Test subscriptions](https://razorpay.com/docs/payments/subscriptions/test/)
- [Create a Payment Link](https://razorpay.com/docs/api/payments/payment-links/create-standard/)
- [Payment Link webhooks](https://razorpay.com/docs/webhooks/payment-links/)
