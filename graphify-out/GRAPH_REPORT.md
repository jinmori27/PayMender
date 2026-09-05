# Graph Report - razorpay  (2026-09-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 410 nodes · 1191 edges · 23 communities (11 shown, 5 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 140 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `88027fd9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16

## God Nodes (most connected - your core abstractions)
1. `get_settings()` - 45 edges
2. `Settings` - 44 edges
3. `SubscriptionCaseModel` - 36 edges
4. `process_webhook_event()` - 29 edges
5. `WebhookEventModel` - 27 edges
6. `RecoveryAction` - 25 edges
7. `RazorpayGateway` - 23 edges
8. `accept_webhook()` - 23 edges
9. `approve_proposal()` - 23 edges
10. `JobModel` - 19 edges

## Surprising Connections (you probably didn't know these)
- `_duplicate_scenario()` --uses--> `JobModel`  [INFERRED]
  backend/app/failure_lab.py → backend/app/models.py
- `reset_demo()` --uses--> `JobModel`  [INFERRED]
  backend/app/services.py → backend/app/models.py
- `approve_proposal()` --uses--> `SubscriptionCaseModel`  [INFERRED]
  backend/app/services.py → backend/app/models.py
- `case_as_dict()` --uses--> `SubscriptionCaseModel`  [INFERRED]
  backend/app/services.py → backend/app/models.py
- `create_proposal()` --uses--> `SubscriptionCaseModel`  [INFERRED]
  backend/app/services.py → backend/app/models.py

## Import Cycles
- None detected.

## Communities (23 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.11
Nodes (59): Any, get_settings(), _set_sqlite_pragmas(), JobModel, datetime, SubscriptionCaseModel, utcnow(), WebhookEventModel (+51 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (55): Base, get_db(), init_db(), Session, add_security_headers(), approve(), case_detail(), cases() (+47 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (40): fixed_rules(), _policy_action(), EvaluationSummary, run_evaluation(), fallback_decision(), ActionScore, RecoveryModel, decide_policy() (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (35): api, App(), View, Inspector(), ScoreBars(), AuditTimeline(), CaseCard(), ConfirmReset() (+27 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (35): dependencies, lucide-react, react, react-dom, tailwindcss, @tailwindcss/vite, devDependencies, @playwright/test (+27 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (13): Settings, gemini_case_payload(), GeminiAdvisor, CapturingClient, configured_settings(), FakeClient, MalformedClient, test_gemini_client_bounds_timeout_retries_and_output_tokens() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (17): _bounded_items(), _canonical_failure_reason(), PaymentLinkResult, RazorpayGateway, live_settings(), parametrize, recovery_case(), StubResponse (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (22): _duplicate_scenario(), execute_failure_scenario(), _FailingGateway, _gemini_scenario(), FailureScenarioResult, Session, _razorpay_scenario(), _record_result() (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (21): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+13 more)

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (8): compilerOptions, allowImportingTsExtensions, module, moduleResolution, noEmit, skipLibCheck, include, vite.config.ts

### Community 12 - "Community 12"
Cohesion: 0.83
Nodes (3): Path, main(), tracked_files()

## Knowledge Gaps
- **56 isolated node(s):** `View`, `ActionScore`, `EvaluationPolicy`, `allowImportingTsExtensions`, `module` (+51 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 113 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `RazorpayGateway` connect `Community 6` to `Community 0`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `Settings` (e.g. with `_policy_action()` and `run_evaluation()`) actually correct?**
  _`Settings` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `SubscriptionCaseModel` (e.g. with `approve_proposal()` and `case_as_dict()`) actually correct?**
  _`SubscriptionCaseModel` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `process_webhook_event()` (e.g. with `Settings` and `RecoveryProposalModel`) actually correct?**
  _`process_webhook_event()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `WebhookEventModel` (e.g. with `_duplicate_scenario()` and `mark_webhook_enrichment_failed()`) actually correct?**
  _`WebhookEventModel` has 9 INFERRED edges - model-reasoned connections that need verification._