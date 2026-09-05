import { AlertTriangle, ChevronRight, RefreshCw } from "lucide-react";
import type { CaseSummary, Proposal } from "../types";
import { actionLabels, cleanLabel, money } from "../format";
import { StatusPill } from "./ui";

export function CaseCard({ item, selected, onClick, proposal, disabled }: {
  item: CaseSummary; selected: boolean; onClick: () => void; proposal?: Proposal; disabled: boolean;
}) {
  return (
    <button className={`case-card ${selected ? "selected" : ""}`} onClick={onClick} aria-pressed={selected} disabled={disabled}>
      <div className="case-card-head">
        <div className="avatar">{item.customer_name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</div>
        <div className="case-identity"><strong>{item.customer_name}</strong><span>{item.subscription_id}</span></div>
        <ChevronRight size={17} />
      </div>
      <div className="case-amount">
        <strong>{item.enrichment_state === "pending" ? "Fetching amount" : item.enrichment_state === "failed" ? "Amount unavailable" : money(item.amount_paise)}</strong>
        <StatusPill value={item.enrichment_state === "failed" ? "needs attention" : item.status} />
      </div>
      <div className="case-signal"><span>{cleanLabel(item.failure_reason)}</span><span>{item.retry_count} retries</span></div>
      {item.enrichment_state === "pending" && <div className="enrichment-line"><RefreshCw className="spin" />Verifying Razorpay invoice</div>}
      {item.enrichment_state === "failed" && <div className="enrichment-line failed"><AlertTriangle />Provider context could not be verified</div>}
      {proposal && (
        <div className="case-action">
          <span>{proposal.state === "proposed" ? "Approval needed" : proposal.state === "retryable_failure" ? "Retry available" : "Current action"}</span>
          <strong>{actionLabels[proposal.recommended_action]}</strong>
        </div>
      )}
    </button>
  );
}
