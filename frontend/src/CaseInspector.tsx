import { useState } from "react";
import { AlertTriangle, Check, Copy, ExternalLink, RefreshCw, ShieldCheck, Sparkles, X } from "lucide-react";
import type { CaseDetail, Proposal } from "./types";
import { actionLabels, cleanLabel, money, moneyRupees } from "./format";
import { EmptyState, StatusPill } from "./components/ui";
import { CaseProgress } from "./RecoveryWorkflow";

function ScoreBars({ proposal }: { proposal: Proposal }) {
  const max = Math.max(...proposal.action_scores.map((score) => Math.max(score.expected_value_rupees, 0)), 1);
  return (
    <div className="score-list">
      {proposal.action_scores.map((score) => (
        <div className="score-row" key={score.action}>
          <div><span>{actionLabels[score.action]}</span><b>{Math.round(score.recovery_probability * 100)}%</b></div>
          <div className="bar-track" aria-hidden="true"><span style={{ width: `${(Math.max(score.expected_value_rupees, 0) / max) * 100}%` }} /></div>
          <small>{moneyRupees(score.expected_value_rupees)} expected</small>
        </div>
      ))}
    </div>
  );
}

export function Inspector({ detail, busy, loading, error, onRetry, displayName, onDecision, onCopyLink }: {
  detail: CaseDetail | null;
  busy: boolean;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  displayName: string;
  onDecision: (decision: "approve" | "reject") => void;
  onCopyLink: (url: string) => void;
}) {
  const [inspectorView, setInspectorView] = useState<"decision" | "model" | "messages">("decision");
  if (loading) return <EmptyState className="inspector" title="Loading case details" icon={RefreshCw} loading>Checking the latest proposal before enabling decisions.</EmptyState>;
  if (error) return <EmptyState className="inspector" title="Case could not be loaded" icon={AlertTriangle} error action={<button className="btn ghost" onClick={onRetry}>Retry case</button>}>{error}</EmptyState>;
  if (!detail) return <EmptyState className="inspector" title="Select a recovery case" icon={Sparkles}>Inspect the evidence, model scores, policy override and complete audit context.</EmptyState>;
  const proposal = detail.proposals[0];
  return (
    <section className="inspector" tabIndex={-1} aria-label="Selected recovery case">
      <div className="inspector-head">
        <div><h2>{detail.customer_name}</h2><p>{detail.subscription_id}</p></div>
        <div className="amount-block"><small>Case amount</small><strong>{detail.enrichment_state === "pending" ? "Verifying" : detail.enrichment_state === "failed" ? "Unavailable" : money(detail.amount_paise)}</strong></div>
      </div>
      <div className="case-facts">
        <div><span>Status</span><StatusPill value={detail.status} /></div>
        <div><span>Failure</span><b>{cleanLabel(detail.failure_reason)}</b></div>
        <div><span>Attempts</span><b>{detail.retry_count}</b></div>
        <div><span>Case source</span><b>{detail.source === "synthetic" ? "Synthetic demo" : "Razorpay test"}</b></div>
      </div>
      <CaseProgress detail={detail} />
      {detail.enrichment_state === "pending" && (
        <div className="provider-state"><RefreshCw className="spin" /><div><b>Verifying invoice context</b><span>{displayName} is fetching the authoritative amount and latest failed payment from Razorpay.</span></div></div>
      )}
      {detail.enrichment_state === "failed" && (
        <div className="provider-state failed"><AlertTriangle /><div><b>Provider context needs attention</b><span>Invoice details could not be verified after three attempts. No recovery action was proposed.</span></div></div>
      )}
      {proposal ? (
        <>
          <div className="proposal-banner">
            <div className="proposal-icon"><Sparkles size={18} /></div>
            <div><h3>{actionLabels[proposal.recommended_action]}</h3><p>{["proposed", "retryable_failure"].includes(proposal.state) ? "Review the evidence before approving this action." : `Recorded decision · ${cleanLabel(proposal.state)}`}</p></div>
            <div className="expected-value"><span>Estimated net value</span><b>{moneyRupees(proposal.expected_value_rupees)}</b></div>
          </div>
          {proposal.model_recommended_action !== proposal.recommended_action && (
            <div className="override-note"><ShieldCheck size={17} /><span>Safety gate changed the AI proposal from <b>{actionLabels[proposal.model_recommended_action]}</b>.</span></div>
          )}
          <div className="inspector-switcher" role="group" aria-label="Case information">
            <button aria-pressed={inspectorView === "decision"} onClick={() => setInspectorView("decision")}>Decision</button>
            <button aria-pressed={inspectorView === "model"} onClick={() => setInspectorView("model")}>Model evidence</button>
            <button aria-pressed={inspectorView === "messages"} onClick={() => setInspectorView("messages")}>Message previews</button>
          </div>
          <div className="inspector-content">
            {inspectorView === "decision" && <section className="panel-section" aria-label="Decision explanation">
              <div className="section-title"><span>Why this action?</span><small>Deterministic safety policy</small></div>
              <p className="reasoning">{proposal.policy_reason}</p>
              <dl className="decision-context"><div><dt>Days overdue</dt><dd>{detail.days_overdue}</dd></div><div><dt>Contacts in 7 days</dt><dd>{detail.contacts_7d}</dd></div><div><dt>Previous interventions</dt><dd>{detail.previous_interventions}</dd></div></dl>
              <p className="inspector-note">{proposal.recommended_action === "STOP_CONTACT" ? "Contact is stopped by policy. There is no customer action to approve." : proposal.recommended_action === "WAIT_FOR_RETRY" ? "PayMender records the decision to wait. Razorpay manages its own scheduled retry." : proposal.recommended_action === "ESCALATE_HUMAN" ? "This case needs a person to review it. No payment link or message is sent automatically." : "Review the policy reason and amount before deciding. Message previews never send a notification."}</p>
            </section>}
            {inspectorView === "messages" && <section className="panel-section" aria-label="Customer message previews">
              <div className="section-title"><span>Drafts only</span><small>Nothing is sent</small></div>
              {proposal.recommended_action === "STOP_CONTACT" ? <p className="inspector-note">Contact is stopped for this case. No outreach preview is actionable.</p> : <>
              <div className="message-preview">
                <div><span>English preview</span><p>{proposal.message_english}</p></div>
                <div><span>Hinglish preview</span><p>{proposal.message_hinglish}</p></div>
                <small>No message is sent by this app. Approval does not send these drafts.</small>
              </div>
              </>}
            </section>}
            {inspectorView === "model" && <section className="panel-section score-section" aria-label="Model evidence">
              <div className="section-title"><span>Compare the possible actions</span><small>{Math.round(proposal.confidence * 100)}% proposal confidence</small></div>
              <p className="inspector-note">Simulator-trained estimates, not guaranteed recovery. Bars compare net expected value; percentages show estimated recovery probability. The safety policy determines which action is allowed.</p>
              <p className="reasoning">{proposal.explanation}</p>
              <ScoreBars proposal={proposal} />
              <div className="model-evidence"><h4>Inputs cited by the proposal</h4><div className="evidence-row">{proposal.evidence.map((item) => <code key={item}>{item}</code>)}</div><small>Explanation source: {proposal.provider}</small></div>
            </section>}
          </div>
          {(proposal.state === "proposed" || proposal.state === "retryable_failure") && (
            <>
              {proposal.recommended_action === "CREATE_RECOVERY_LINK" && (
                <div className="execution-preview">
                  <div><span>Exact amount</span><b>{money(detail.amount_paise)}</b></div>
                  <div><span>Link expiry</span><b>48 hours</b></div>
                  <div><span>Notifications</span><b>Disabled</b></div>
                  <small>{detail.source === "synthetic" ? "Demo only. Approval creates a simulated link without contacting Razorpay." : "Test-mode only. Approval creates one Razorpay link and does not send it to the customer."}</small>
                </div>
              )}
              <div className="approval-bar">
                <div><ShieldCheck /><span><b>{proposal.state === "retryable_failure" ? "Previous attempt contained" : "Human gate active"}</b><small>{proposal.state === "retryable_failure" ? "Retry reuses the same execution record and remains gated." : "External action cannot execute without approval."}</small></span></div>
                <div className="approval-actions">
                  <button className="btn ghost" disabled={busy} onClick={() => onDecision("reject")}><X size={16} />Reject</button>
                  <button className="btn primary" disabled={busy} onClick={() => onDecision("approve")}>
                    {busy ? <RefreshCw size={16} className="spin" /> : <Check size={16} />}{proposal.state === "retryable_failure" ? "Retry action" : "Approve action"}
                  </button>
                </div>
              </div>
            </>
          )}
          {detail.active_recovery_link_id && detail.active_recovery_link_url && detail.recovered_amount_paise === 0 && detail.status !== "charged" && (
            <div className="link-success">
              <Check />
              <div><b>Recovery link ready</b><span>{detail.active_recovery_link_id}. No notification sent.</span></div>
              <div className="link-actions">
                <button className="btn ghost" onClick={() => onCopyLink(detail.active_recovery_link_url!)}><Copy />Copy</button>
                <a className="btn primary" href={detail.active_recovery_link_url} target="_blank" rel="noreferrer"><ExternalLink />Open test link</a>
              </div>
            </div>
          )}
        </>
      ) : <div className="empty-proposal">No recovery proposal has been generated.</div>}
    </section>
  );
}
