export type RecoveryAction =
  | "WAIT_FOR_RETRY"
  | "REQUEST_PAYMENT_METHOD_UPDATE"
  | "CREATE_RECOVERY_LINK"
  | "ESCALATE_HUMAN"
  | "STOP_CONTACT";

export interface CaseSummary {
  id: string;
  subscription_id: string;
  source: "synthetic" | "razorpay_test";
  enrichment_state: "pending" | "ready" | "failed" | "not_required";
  provider_invoice_id: string | null;
  provider_order_id: string | null;
  customer_name: string;
  status: string;
  failure_reason: string;
  amount_paise: number;
  days_overdue: number;
  retry_count: number;
  prior_successes: number;
  previous_interventions: number;
  contacts_7d: number;
  next_retry_at: string | null;
  recovered_amount_paise: number;
  active_recovery_link_id: string | null;
  active_recovery_link_url: string | null;
  created_at: string;
  updated_at: string;
}
export interface ActionScore {
  action: RecoveryAction;
  recovery_probability: number;
  expected_value_rupees: number;
}

export interface Proposal {
  id: string;
  case_id: string;
  recommended_action: RecoveryAction;
  model_recommended_action: RecoveryAction;
  confidence: number;
  explanation: string;
  evidence: string[];
  message_english: string;
  message_hinglish: string;
  expected_value_rupees: number;
  action_scores: ActionScore[];
  requires_approval: boolean;
  state: string;
  policy_reason: string;
  provider: string;
  created_at: string;
}

export interface CaseDetail extends CaseSummary {
  proposals: Proposal[];
}

export interface Metrics {
  display_name: string;
  demo_mode: boolean;
  total_cases: number;
  at_risk_paise: number;
  predicted_recoverable_paise: number;
  recovered_paise: number;
  pending_approvals: number;
  stopped_cases: number;
  escalated_cases: number;
  blocked_actions: number;
}

export interface PublicStatus {
  status: string;
  display_name: string;
  demo_mode: boolean;
  gemini: string;
  razorpay: string;
  operator_auth: string;
}

export interface AuditEvent {
  id: string;
  case_id: string | null;
  category: string;
  title: string;
  detail: string;
  severity: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface EvaluationPolicy {
  policy: string;
  gross_recovered_mean: number;
  gross_recovered_std: number;
  net_recovered_mean: number;
  net_recovered_std: number;
  recovery_rate_mean: number;
  contacts_per_recovery_mean: number;
  escalation_rate_mean: number;
  stopped_mean: number;
  unsafe_blocked_mean: number;
}

export interface EvaluationSummary {
  id: string;
  label: string;
  synthetic_disclaimer: string;
  train_records: number;
  batches: number;
  cases_per_batch: number;
  policies: EvaluationPolicy[];
  created_at: string;
}
