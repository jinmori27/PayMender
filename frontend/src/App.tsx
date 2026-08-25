import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  FlaskConical,
  History,
  KeyRound,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserCheck,
  X,
  Zap,
} from "lucide-react";
import { api } from "./api";
import type {
  AuditEvent,
  CaseDetail,
  CaseSummary,
  EvaluationSummary,
  Metrics,
  Proposal,
  RecoveryAction,
} from "./types";

type View = "command" | "evaluation" | "failures";

const actionLabels: Record<RecoveryAction, string> = {
  WAIT_FOR_RETRY: "Wait for Razorpay retry",
  REQUEST_PAYMENT_METHOD_UPDATE: "Request payment update",
  CREATE_RECOVERY_LINK: "Create recovery link",
  ESCALATE_HUMAN: "Escalate to human",
  STOP_CONTACT: "Stop contact",
};

const money = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

const moneyRupees = (rupees: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(rupees);

const cleanLabel = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase());

function StatusPill({ value }: { value: string }) {
  const tone = value === "halted" || value === "proposed" ? "amber" : value === "charged" || value === "executed" ? "green" : "slate";
  return <span className={`status-pill ${tone}`}><span />{cleanLabel(value)}</span>;
}

function KpiCard({ label, value, note, icon: Icon, accent = false }: {
  label: string; value: string; note: string; icon: typeof CircleDollarSign; accent?: boolean;
}) {
  return (
    <article className={`kpi-card ${accent ? "accent" : ""}`}>
      <div className="kpi-top"><span>{label}</span><Icon size={17} /></div>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function CaseCard({ item, selected, onClick, proposal }: {
  item: CaseSummary; selected: boolean; onClick: () => void; proposal?: Proposal;
}) {
  return (
    <button className={`case-card ${selected ? "selected" : ""}`} onClick={onClick}>
      <div className="case-card-head">
        <div className="avatar">{item.customer_name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</div>
        <div className="case-identity"><strong>{item.customer_name}</strong><span>{item.subscription_id}</span></div>
        <ChevronRight size={17} />
      </div>
      <div className="case-amount"><strong>{money(item.amount_paise)}</strong><StatusPill value={item.status} /></div>
      <div className="case-signal"><span>{cleanLabel(item.failure_reason)}</span><span>{item.retry_count} retries</span></div>
      {proposal && (
        <div className="case-action">
          <span>{proposal.state === "proposed" ? "Approval needed" : proposal.state === "retryable_failure" ? "Retry available" : "Current action"}</span>
          <strong>{actionLabels[proposal.recommended_action]}</strong>
        </div>
      )}
    </button>
  );
}

function ScoreBars({ proposal }: { proposal: Proposal }) {
  const max = Math.max(...proposal.action_scores.map((score) => Math.max(score.expected_value_rupees, 0)), 1);
  return (
    <div className="score-list">
      {proposal.action_scores.map((score) => (
        <div className="score-row" key={score.action}>
          <div><span>{actionLabels[score.action]}</span><b>{Math.round(score.recovery_probability * 100)}%</b></div>
          <div className="bar-track"><span style={{ width: `${Math.max(3, (Math.max(score.expected_value_rupees, 0) / max) * 100)}%` }} /></div>
          <small>{moneyRupees(score.expected_value_rupees)} expected</small>
        </div>
      ))}
    </div>
  );
}

function Inspector({ detail, busy, onDecision }: {
  detail: CaseDetail | null; busy: boolean; onDecision: (decision: "approve" | "reject") => void;
}) {
  if (!detail) return <section className="inspector empty-state"><Sparkles /><h2>Select a recovery case</h2><p>Inspect the evidence, model scores, policy override and complete audit context.</p></section>;
  const proposal = detail.proposals[0];
  return (
    <section className="inspector">
      <div className="inspector-head">
        <div><h2>{detail.customer_name}</h2><p>{detail.subscription_id}</p></div>
        <div className="amount-block"><small>Outstanding</small><strong>{money(detail.amount_paise)}</strong></div>
      </div>
      <div className="case-facts">
        <div><span>Status</span><StatusPill value={detail.status} /></div>
        <div><span>Failure</span><b>{cleanLabel(detail.failure_reason)}</b></div>
        <div><span>Attempts</span><b>{detail.retry_count}</b></div>
        <div><span>Contacts · 7d</span><b>{detail.contacts_7d} / 3</b></div>
      </div>
      {proposal ? (
        <>
          <div className="proposal-banner">
            <div className="proposal-icon"><Sparkles size={18} /></div>
            <div><span>Policy-approved recommendation</span><h3>{actionLabels[proposal.recommended_action]}</h3><p>{proposal.policy_reason}</p></div>
            <div className="expected-value"><span>Expected value</span><b>{moneyRupees(proposal.expected_value_rupees)}</b></div>
          </div>
          {proposal.model_recommended_action !== proposal.recommended_action && (
            <div className="override-note"><ShieldCheck size={17} /><span>Safety gate changed the AI proposal from <b>{actionLabels[proposal.model_recommended_action]}</b>.</span></div>
          )}
          <div className="inspector-grid">
            <div className="panel-section">
              <div className="section-title"><span>Agent reasoning</span><small>{proposal.provider}</small></div>
              <p className="reasoning">{proposal.explanation}</p>
              <div className="evidence-row">{proposal.evidence.map((item) => <code key={item}>{item}</code>)}</div>
              <div className="message-preview">
                <div><span>English preview</span><p>{proposal.message_english}</p></div>
                <div><span>Hinglish preview</span><p>{proposal.message_hinglish}</p></div>
                <small>No message is sent by this MVP.</small>
              </div>
            </div>
            <div className="panel-section score-section">
              <div className="section-title"><span>Next-best-action model</span><small>{Math.round(proposal.confidence * 100)}% confidence</small></div>
              <ScoreBars proposal={proposal} />
            </div>
          </div>
          {(proposal.state === "proposed" || proposal.state === "retryable_failure") && (
            <div className="approval-bar">
              <div><ShieldCheck /><span><b>{proposal.state === "retryable_failure" ? "Previous attempt contained" : "Human gate active"}</b><small>{proposal.state === "retryable_failure" ? "Retry reuses the same execution record and remains gated." : "External action cannot execute without approval."}</small></span></div>
              <div className="approval-actions">
                <button className="btn ghost" disabled={busy} onClick={() => onDecision("reject")}><X size={16} />Reject</button>
                <button className="btn primary" disabled={busy} onClick={() => onDecision("approve")}>
                  {busy ? <RefreshCw size={16} className="spin" /> : <Check size={16} />}{proposal.state === "retryable_failure" ? "Retry action" : "Approve action"}
                </button>
              </div>
            </div>
          )}
          {detail.active_recovery_link_id && (
            <div className="link-success"><Check /><div><b>Recovery link created safely</b><span>{detail.active_recovery_link_id} · No notification sent</span></div></div>
          )}
        </>
      ) : <div className="empty-proposal">No recovery proposal has been generated.</div>}
    </section>
  );
}

function EvaluationView({ data, running, onRun }: { data: EvaluationSummary | null; running: boolean; onRun: () => void }) {
  const best = data?.policies.find((policy) => policy.policy === "PayMender");
  const max = Math.max(...(data?.policies.map((policy) => policy.net_recovered_mean) ?? [1]));
  return (
    <main className="view-page">
      <div className="page-intro"><div><h1>Held-out recovery evaluation</h1><p>Compare ten fixed synthetic batches against three non-learning baselines.</p></div><button className="btn primary" onClick={onRun} disabled={running}>{running ? <RefreshCw className="spin" /> : <BarChart3 />}Run evaluation</button></div>
      {!data ? <div className="large-empty"><BarChart3 /><h2>No evaluation run yet</h2><p>Run the deterministic harness to generate transparent, reproducible evidence.</p></div> : (
        <>
          <div className="disclaimer"><FlaskConical /><div><b>Synthetic by design</b><span>{data.synthetic_disclaimer}</span></div><code>{data.train_records.toLocaleString()} train · {data.batches} × {data.cases_per_batch} test</code></div>
          <div className="eval-kpis">
            <KpiCard label="Mean net recovery" value={moneyRupees(best?.net_recovered_mean ?? 0)} note="per 200-case held-out batch" icon={CircleDollarSign} accent />
            <KpiCard label="Recovery rate" value={`${((best?.recovery_rate_mean ?? 0) * 100).toFixed(1)}%`} note="simulated successful interventions" icon={Activity} />
            <KpiCard label="Contacts / recovery" value={(best?.contacts_per_recovery_mean ?? 0).toFixed(2)} note="lower avoids customer fatigue" icon={UserCheck} />
            <KpiCard label="Unsafe actions blocked" value={(best?.unsafe_blocked_mean ?? 0).toFixed(1)} note="mean policy overrides per batch" icon={ShieldCheck} />
          </div>
          <section className="evaluation-chart card-surface">
            <div className="section-title"><span>Net rupees recovered by policy</span><small>mean ± standard deviation</small></div>
            {data.policies.map((policy) => (
              <div className={`eval-row ${policy.policy === "PayMender" ? "winner" : ""}`} key={policy.policy}>
                <div className="eval-name"><b>{policy.policy}</b><span>{(policy.recovery_rate_mean * 100).toFixed(1)}% recovered</span></div>
                <div className="eval-track"><span style={{ width: `${(policy.net_recovered_mean / max) * 100}%` }} /></div>
                <div className="eval-number"><b>{moneyRupees(policy.net_recovered_mean)}</b><span>± {moneyRupees(policy.net_recovered_std)}</span></div>
              </div>
            ))}
          </section>
          <section className="metric-table card-surface">
            <div className="section-title"><span>Full metric disclosure</span><small>no cherry-picked case</small></div>
            <div className="table-scroll"><table><thead><tr><th>Policy</th><th>Gross ₹</th><th>Net ₹</th><th>Recovery</th><th>Contacts / recovery</th><th>Escalation</th><th>Stopped</th></tr></thead><tbody>{data.policies.map((policy) => <tr key={policy.policy}><td><b>{policy.policy}</b></td><td>{moneyRupees(policy.gross_recovered_mean)}</td><td>{moneyRupees(policy.net_recovered_mean)}</td><td>{(policy.recovery_rate_mean * 100).toFixed(1)}%</td><td>{policy.contacts_per_recovery_mean.toFixed(2)}</td><td>{(policy.escalation_rate_mean * 100).toFixed(1)}%</td><td>{policy.stopped_mean.toFixed(1)}</td></tr>)}</tbody></table></div>
          </section>
        </>
      )}
    </main>
  );
}

function FailureLab({ audit, onInject }: { audit: AuditEvent[]; onInject: (scenario: string) => void }) {
  const scenarios = [
    { id: "duplicate", icon: History, title: "Concurrent duplicate", text: "Replay ten identical webhook deliveries and prove exactly-once intake." },
    { id: "gemini-quota", icon: Sparkles, title: "Gemini quota exhausted", text: "Show deterministic explanation fallback without relaxing policy gates." },
    { id: "razorpay-500", icon: AlertTriangle, title: "Razorpay returns 5xx", text: "Mark the external action retryable without recording a false success." },
    { id: "worker-crash", icon: RefreshCw, title: "Worker crashes mid-job", text: "Reclaim the expired lease and preserve the raw event for safe replay." },
  ];
  return (
    <main className="view-page">
      <div className="page-intro"><div><h1>Reliability lab</h1><p>Verify how the system contains dependency failures and duplicate delivery.</p></div></div>
      <div className="failure-grid">{scenarios.map(({ id, icon: Icon, title, text }) => <button className="failure-card" key={id} onClick={() => onInject(id)}><div className="failure-icon"><Icon /></div><div><h3>{title}</h3><p>{text}</p><span>Inject scenario <ArrowRight size={15} /></span></div></button>)}</div>
      <section className="card-surface lab-audit"><div className="section-title"><span>Containment evidence</span><small>latest audit events</small></div><AuditTimeline audit={audit.filter((event) => event.category === "failure" || event.category === "safety").slice(0, 12)} /></section>
    </main>
  );
}

function AuditTimeline({ audit }: { audit: AuditEvent[] }) {
  return <div className="audit-list">{audit.map((event) => <div className={`audit-item ${event.severity}`} key={event.id}><span className="audit-dot" /><div><b>{event.title}</b><p>{event.detail}</p><small>{new Date(event.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · {event.category}</small></div></div>)}</div>;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [operatorToken, setOperatorToken] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [view, setView] = useState<View>("command");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async (preferredId?: string | null) => {
    const [nextCases, nextMetrics, nextAudit, nextEval] = await Promise.all([api.cases(), api.metrics(), api.audit(), api.evaluation()]);
    setCases(nextCases); setMetrics(nextMetrics); setAudit(nextAudit); setEvaluation(nextEval);
    const id = preferredId ?? selectedId ?? nextCases[0]?.id;
    if (id) { setSelectedId(id); setDetail(await api.case(id)); }
  }, [selectedId]);

  useEffect(() => {
    if (authenticated) load().catch((error: Error) => setNotice(error.message));
  }, [authenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  const authenticate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError(null);
    try {
      await api.authenticate(operatorToken.trim());
      setOperatorToken("");
      setAuthenticated(true);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Access could not be verified.");
    } finally {
      setAuthBusy(false);
    }
  };

  const signOut = () => {
    api.signOut();
    setAuthenticated(false);
    setCases([]);
    setDetail(null);
    setSelectedId(null);
  };

  const selectCase = async (id: string) => { setSelectedId(id); setDetail(await api.case(id)); };
  const decide = async (decision: "approve" | "reject") => {
    if (!selectedId) return;
    setBusy(true);
    try { setDetail(await api.approve(selectedId, decision)); await load(selectedId); setNotice(decision === "approve" ? "Action approved and safely executed." : "Proposal rejected; no action was taken."); }
    catch (error) { await load(selectedId); setNotice(error instanceof Error ? error.message : "Action failed safely."); }
    finally { setBusy(false); }
  };
  const runEval = async () => { setBusy(true); try { setEvaluation(await api.runEvaluation()); setNotice("Held-out evaluation completed."); } catch (error) { setNotice(error instanceof Error ? error.message : "Evaluation failed."); } finally { setBusy(false); } };
  const reset = async () => { setBusy(true); try { await api.reset(); setSelectedId(null); await load(null); setNotice("Demo data restored."); } finally { setBusy(false); } };
  const inject = async (scenario: string) => { await api.inject(scenario); await load(selectedId); setNotice("Failure injected and contained. See the audit evidence below."); };

  const latestProposalByCase = useMemo(() => new Map(cases.map((item) => [item.id, detail?.id === item.id ? detail.proposals[0] : undefined])), [cases, detail]);

  if (!authenticated) {
    return (
      <main className="access-shell">
        <section className="access-card">
          <div className="access-brand"><div className="logo-glyph"><Zap fill="currentColor" /></div><div><b>PayMender</b><span>Operator command center</span></div></div>
          <div className="access-icon"><KeyRound /></div>
          <h1>Protected operations</h1>
          <p>Enter the operator token from your local <code>.env.local</code> file. It stays only in this browser tab and is never saved.</p>
          <form onSubmit={authenticate}>
            <label htmlFor="operator-token">Operator token</label>
            <input id="operator-token" type="password" autoComplete="off" value={operatorToken} onChange={(event) => setOperatorToken(event.target.value)} required minLength={24} placeholder="Paste your local token" />
            {authError && <div className="access-error"><AlertTriangle size={15} />{authError}</div>}
            <button className="btn primary" disabled={authBusy || operatorToken.trim().length < 24}>{authBusy ? <RefreshCw className="spin" /> : <KeyRound />}Unlock command center</button>
          </form>
          <small><ShieldCheck size={14} /> Money actions remain separately approval-gated.</small>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark"><div className="logo-glyph"><Zap fill="currentColor" /></div><div><b>{metrics?.display_name ?? "PayMender"}</b><span>Revenue Recovery</span></div></div>
        <nav>
          <button className={view === "command" ? "active" : ""} onClick={() => setView("command")}><Activity />Command center</button>
          <button className={view === "evaluation" ? "active" : ""} onClick={() => setView("evaluation")}><BarChart3 />Evaluation</button>
          <button className={view === "failures" ? "active" : ""} onClick={() => setView("failures")}><FlaskConical />Reliability lab</button>
        </nav>
        <div className="trust-card"><ShieldCheck /><b>Bounded by design</b><p>AI recommends. Policy constrains. You approve every external action.</p><span><i /> TEST ENVIRONMENT</span></div>
      </aside>
      <div className="main-shell">
        <header className="topbar"><div><span className="live-dot" />Operations healthy</div><div className="top-actions"><span className="mode-pill">{metrics?.demo_mode ? "Synthetic demo" : "Razorpay test"}</span><button className="icon-btn" onClick={reset} disabled={busy} title="Reset demo" aria-label="Reset demo data"><RefreshCw size={17} className={busy ? "spin" : ""} /></button><button className="icon-btn" onClick={signOut} title="Lock command center" aria-label="Lock command center"><LogOut size={17} /></button></div></header>
        {view === "command" && <main className="command-view">
          <div className="command-intro"><div><h1>Recover failed subscriptions safely.</h1><p>Prioritize the right intervention, approve money actions, and trace every decision.</p></div><div className="batch-badge"><span>Current portfolio</span><b>{metrics?.total_cases ?? 0} cases processed</b><small><Check size={13} /> All policy gates active</small></div></div>
          <div className="kpi-grid">
            <KpiCard label="Revenue at risk" value={money(metrics?.at_risk_paise ?? 0)} note="active failed subscriptions" icon={AlertTriangle} />
            <KpiCard label="Predicted recoverable" value={money(metrics?.predicted_recoverable_paise ?? 0)} note="policy-adjusted expected value" icon={Sparkles} accent />
            <KpiCard label="Confirmed recovered" value={money(metrics?.recovered_paise ?? 0)} note="webhook-confirmed test revenue" icon={CircleDollarSign} />
            <KpiCard label="Awaiting approval" value={String(metrics?.pending_approvals ?? 0)} note={`${metrics?.blocked_actions ?? 0} risky actions contained`} icon={ShieldCheck} />
          </div>
          <div className="command-grid">
            <section className="case-queue"><div className="queue-head"><div><h2>Recovery queue</h2><span>{cases.length} synthetic cases</span></div><div className="queue-count">{metrics?.pending_approvals ?? 0} gated</div></div><div className="case-list">{cases.map((item) => <CaseCard key={item.id} item={item} selected={selectedId === item.id} proposal={latestProposalByCase.get(item.id)} onClick={() => selectCase(item.id)} />)}</div></section>
            <Inspector detail={detail} busy={busy} onDecision={decide} />
          </div>
          <section className="command-audit card-surface"><div className="section-title"><span>Immutable audit trail</span><small>{audit.length} recent events</small></div><AuditTimeline audit={audit.slice(0, 8)} /></section>
        </main>}
        {view === "evaluation" && <EvaluationView data={evaluation} running={busy} onRun={runEval} />}
        {view === "failures" && <FailureLab audit={audit} onInject={inject} />}
      </div>
      {notice && <button className="toast" onClick={() => setNotice(null)} aria-live="polite"><Check size={17} /><span>{notice}</span><X size={15} /></button>}
    </div>
  );
}
