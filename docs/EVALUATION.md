# Evaluation methodology

## What is measured

PayMender does not claim real-world merchant uplift. The evaluation is a transparent synthetic counterfactual simulation intended to show that the decision pipeline can be measured honestly.

The training set contains 2,000 randomized subscription histories. The held-out suite uses ten independent fixed seeds, with 200 unseen cases per seed. Training and evaluation case identifiers do not overlap.

## Model

One logistic-regression pipeline receives:

- subscription state and failure reason;
- log outstanding amount;
- days overdue and retry count;
- prior successful payments;
- previous interventions and seven-day contact count;
- one candidate action.

The same case is scored once per candidate action. Expected value is:

```text
P(recovery | case, action) × outstanding amount
− action cost
− contact-fatigue penalty
```

The policy engine is applied after model selection, so the evaluation counts unsafe recommendations that were overridden.

## Counterfactual outcomes

The generator defines a documented latent probability for each case/action pair. Held-out success is sampled by hashing the seed, case ID and action. This makes every run reproducible while allowing any policy to be compared against the same case population.

## Baselines

- Always wait for another retry.
- Always attempt a recovery link, subject to the same policy gate.
- Fixed lifecycle and failure-reason rules without ML.

## Reported metrics

Every policy reports mean and population standard deviation across all ten batches for gross recovered rupees, net recovered rupees, recovery rate, contacts per recovery, escalation rate, stopped cases and policy overrides.

Limitations: the simulator encodes assumptions, not observed merchant behavior. Strong synthetic performance is evidence of a working measurement harness, not proof of business impact.
