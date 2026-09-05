import { useState } from "react";
import { ArrowRight, Check, ChevronRight, CircleDollarSign, FileCheck2, ShieldCheck, Sparkles, UserCheck } from "lucide-react";
import type { CaseDetail } from "./types";


const stages = [
  {
    title: "Detect the failed payment", icon: FileCheck2,
    description: "Razorpay sends a subscription event. PayMender checks its signature, suppresses repeat deliveries and verifies the payment amount before proposing a recovery action.",
    evidence: "The case records the subscription and available invoice references. Raw webhook bodies are not stored.",
    responsibility: "Check the subscription, failure reason and amount in the recovery queue.",
  },
  {
    title: "Compare recovery options", icon: Sparkles,
    description: "A small model scores waiting, requesting a payment-method update, creating a recovery link, escalating and stopping contact. Gemini can explain the proposal; deterministic templates provide a fallback.",
    evidence: "Model evidence shows estimated recovery probabilities and net expected value. These estimates come from a synthetic training simulator, not measured merchant results.",
    responsibility: "Read why the action was suggested. A high score is an estimate, not a guarantee.",
  },
  {
    title: "Apply the safety rules", icon: ShieldCheck,
    description: "Deterministic rules check contact limits, minimum amounts, subscription state and scheduled retries. They can change the AI suggestion, stop contact or route an uncertain case to a person.",
    evidence: "The decision view shows the final policy reason and any change to the AI proposal. AI has no execution authority.",
    responsibility: "Check the final recommendation. A stopped case has no approval action.",
  },
  {
    title: "Review and approve", icon: UserCheck,
    description: "Actions that need your approval pause here. Approving a recovery link creates one Razorpay Test Mode link for the verified amount. Message text remains a preview; this app does not send email, SMS or WhatsApp.",
    evidence: "Approvals and execution results are recorded in the audit history. A retryable provider failure is shown as a failure, not a successful recovery.",
    responsibility: "Approve or reject after reviewing the amount and policy reason. The operator token unlocks this local reviewer interface.",
  },
  {
    title: "Confirm what recovered", icon: CircleDollarSign,
    description: "Creating a link does not mean the customer paid. PayMender attributes recovery only after a matching payment_link.paid webhook. A normal recurring subscription charge is recorded as an organic resolution.",
    evidence: "Confirmed recovery and the audit history provide the outcome. A Payment Link does not itself reactivate the original subscription mandate.",
    responsibility: "Refresh the portfolio and correlate the case with Razorpay webhook history before claiming a recovered payment.",
  },
];

export function RecoveryGuide({ demoMode, onReview }: { demoMode: boolean; onReview: () => void }) {
  const [selected, setSelected] = useState(0);
  const stage = stages[selected];
  const Icon = stage.icon;
  return (
    <main id="main-content" tabIndex={-1} className="view-page workflow-page">
      <div className="page-intro"><div><h1>How recovery works</h1><p>From a failed subscription to a verified outcome, with a human decision where it matters.</p></div><button className="btn primary" onClick={onReview}>Review a case <ArrowRight size={16} /></button></div>
      <div className="workflow-layout">
        <nav className="workflow-stages" aria-label="Recovery workflow stages">
          {stages.map(({ title, icon: StageIcon }, index) => <button key={title} aria-pressed={selected === index} onClick={() => setSelected(index)}><StageIcon size={20} /><span>{title}</span><ChevronRight size={16} /></button>)}
        </nav>
        <section className="workflow-detail" aria-live="polite">
          <Icon className="workflow-symbol" size={28} /><h2>{stage.title}</h2><p>{stage.description}</p>
          <div className="workflow-explanation"><h3>What you can verify</h3><p>{stage.evidence}</p></div>
          <div className="workflow-explanation"><h3>Your next step</h3><p>{stage.responsibility}</p></div>
          {selected < stages.length - 1 && <button className="btn ghost" onClick={() => setSelected(selected + 1)}>Next: {stages[selected + 1].title} <ArrowRight size={16} /></button>}
        </section>
      </div>
      <section className="mode-explainer"><div><h2>{demoMode ? "You’re in synthetic demo mode" : "You’re in Razorpay Test Mode"}</h2><p>{demoMode ? "The current demo uses fictional cases and isolated adapters. Approvals create simulated links, and evaluation results are synthetic. No provider network calls are made." : "This workspace uses Razorpay Test Mode. Genuine signed provider events are required to demonstrate payment recovery; synthetic evaluation is separately labelled."}</p></div><div><h2>Try the full story</h2><p>Review a case, inspect the policy decision, then approve an eligible action. Use Evaluation to compare synthetic batches and Reliability Lab in demo mode to test contained failures.</p></div></section>
    </main>
  );
}

export function CaseProgress({ detail }: { detail: CaseDetail }) {
  const proposal = detail.proposals[0];
  const contextReady = !["pending", "failed"].includes(detail.enrichment_state);
  const recovered = detail.recovered_amount_paise > 0;
  const stopped = proposal?.recommended_action === "STOP_CONTACT";
  const organic = detail.status === "charged" && !recovered;
  const needsApproval = proposal && ["proposed", "retryable_failure"].includes(proposal.state);
  const outcome = recovered ? "Payment confirmed" : organic ? "Resolved by recurring charge" : stopped ? "Contact stopped" : proposal?.state === "rejected" ? "Action rejected" : detail.active_recovery_link_id ? "Link ready · payment unconfirmed" : "No recovery confirmed";
  const steps = [
    { title: "Payment context", value: contextReady ? detail.source === "synthetic" ? "Demo fixture loaded" : "Context ready" : detail.enrichment_state === "failed" ? "Verification failed" : "Verification in progress", complete: contextReady },
    { title: "Safety review", value: proposal ? "Policy checked" : "Awaiting proposal", complete: !!proposal },
    { title: "Decision", value: needsApproval ? proposal.state === "retryable_failure" ? "Retry needs approval" : "Your approval needed" : proposal ? "Decision recorded" : "Not ready", complete: !!proposal && !needsApproval },
    { title: "Outcome", value: outcome, complete: recovered || organic || !!stopped || proposal?.state === "rejected" },
  ];
  return <ol className="case-progress" aria-label="Case progress">{steps.map((step) => <li key={step.title} className={step.complete ? "complete" : "pending"}><span className="progress-marker">{step.complete ? <Check size={12} /> : <span />}</span><div><span>{step.title}</span><b>{step.value}</b></div></li>)}</ol>;
}
