# Reference-led frontend refresh

## Direction

Light recovery-operations workspace with white surfaces, neutral background, indigo actions, compact case rows and labelled semantic status colors. Preserve the existing PayMender identity, navigation, operator unlock, safety decisions and evidence boundaries.

The first desktop viewport introduces the current portfolio and the beginning of the case review workspace. Phone layouts stack the review panes and retain labelled bottom navigation.

## Public references inspected

- [Churnkey payment recovery analytics](https://churnkey.co/blog/launch-payment-recovery-analytics-2-0/): light analytics surfaces, compact totals, payment-status presentation.
- [Churn Buster analytics documentation](https://churnbuster.io/docs/data-testing): explanatory metric context and status breakdowns.
- [Baremetrics overview](https://help.baremetrics.com/en/articles/5883953-reading-the-overview): clear separation of failed and recovered totals.

These are publicly published documentation and product screenshots, including 2024 examples. We did not access their private dashboards or verify their newest logged-in interfaces. No competitor logo, asset, code or performance figure is shipped.

## Data boundaries

- The new Payment status graphic groups the fetched cases by their actual subscription status, with text counts for every segment. It is not a historical chart or a recovery-rate forecast.
- Pending is a subscription status, not an inferred approval count. Approval totals still come from the metrics endpoint.
- Charged does not automatically imply a PayMender-attributed recovery.
- Existing synthetic evaluation, matching-payment confirmation, stopped-contact and human-approval explanations are retained.
- Empty portfolios show an explicit empty state; refresh failures keep their warning and disable approvals.

## Verification

Production build and TypeScript checks passed. All 10 Playwright reviewer flows passed, including populated/empty status summaries, approval and paid-state presentation, stopped cases, stale-response protection, failed-refresh blocking, reset confirmation, evaluation export and all four contained failure scenarios.

Layout screenshots were checked at 1440, 1280 and 390 pixels for the command center, plus desktop/mobile workflow, phone unlock, evaluation and Reliability Lab. Automated overflow assertions pass at the tested command-center and workflow sizes.

This is a frontend refresh, not new proof of provider-authentic test payments or a claim that all hackathon submission blockers are closed.
