# Product
<!-- impeccable:product-schema 1 -->

## Platform

Web application, locally hosted reviewer UI.

## Users

Hackathon reviewers and a trusted local operator reviewing failed subscription payments.

## Product Purpose

PayMender recommends recovery actions, applies deterministic safety rules, requires human approval where applicable, and correlates outcomes with evidence.

## Capabilities and Constraints

- SQLite and one background worker remain the supported submission configuration.
- Authentication is a high-entropy shared local operator token, not multi-user production identity.
- Synthetic demo adapters are isolated from payment-provider networks. Razorpay activity is Test Mode only.
- A created payment link is not proof of recovery. Message previews do not send messages.
- Model estimates and synthetic evaluation are labelled separately from confirmed payment evidence.
- Audit history is application-enforced append-only SQLite history, not cryptographically immutable.

## Brand Commitments

Retain PayMender's identity. The user requested researching comparable products before upgrading the frontend. The current direction adapts public Churnkey, Churn Buster and Baremetrics product-interface references; their branding, proprietary assets and sample performance claims are not copied.

## Evidence on Hand

Existing backend and browser tests, synthetic demo fixtures, and the locally running app. Provider-authentic submission evidence is a separate requirement and must not be implied by the interface redesign.
