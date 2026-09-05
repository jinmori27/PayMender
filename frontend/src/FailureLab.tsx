import { AlertTriangle, ArrowRight, Check, History, RefreshCw, Sparkles, X } from "lucide-react";
import type { AuditEvent, FailureScenarioResult } from "./types";
import { cleanLabel } from "./format";
import { AuditTimeline } from "./components/AuditTimeline";

export function FailureLab({ audit, result, running, onInject }: { audit: AuditEvent[]; result: FailureScenarioResult | null; running: boolean; onInject: (scenario: string) => void }) {
  const scenarios = [
    { id: "duplicate", icon: History, title: "Concurrent duplicate", text: "Replay ten identical webhook deliveries and prove exactly-once intake." },
    { id: "gemini-quota", icon: Sparkles, title: "Gemini quota exhausted", text: "Show deterministic explanation fallback without relaxing policy gates." },
    { id: "razorpay-500", icon: AlertTriangle, title: "Razorpay returns 5xx", text: "Mark the external action retryable without recording a false success." },
    { id: "worker-crash", icon: RefreshCw, title: "Worker crashes mid-job", text: "Reclaim an expired lease around the stored, PII-minimized event envelope." },
  ];
  return (
    <main id="main-content" tabIndex={-1} className="view-page">
      <div className="page-intro"><div><h1>Reliability lab</h1><p>Verify how the system contains dependency failures and duplicate delivery.</p></div></div>
      <div className="failure-grid">{scenarios.map(({ id, icon: Icon, title, text }) => <button className="failure-card" key={id} disabled={running} aria-busy={running} onClick={() => onInject(id)}><div className="failure-icon"><Icon /></div><div><h3>{title}</h3><p>{text}</p><span>{running ? "Running contained check" : "Run contained check"} <ArrowRight size={15} /></span></div></button>)}</div>
      {result && <section className="lab-result card-surface" aria-live="polite"><div className="section-title"><span>{cleanLabel(result.scenario)} contained</span><small>{result.evidence_ids.length} evidence IDs</small></div><div className="lab-assertions">{Object.entries(result.assertions).map(([name, passed]) => <div key={name} className={passed ? "passed" : "failed"}>{passed ? <Check size={15} /> : <X size={15} />}<span>{cleanLabel(name)}</span><b>{passed ? "Passed" : "Failed"}</b></div>)}</div><p className="lab-evidence"><b>Evidence:</b> {result.evidence_ids.join(" · ")}</p></section>}
      <section className="card-surface lab-audit"><div className="section-title"><span>Containment evidence</span><small>latest audit events</small></div><AuditTimeline audit={audit.filter((event) => event.category === "failure" || event.category === "safety").slice(0, 12)} /></section>
    </main>
  );
}
