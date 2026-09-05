import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  CircleDollarSign,
  Copy,
  Download,
  Clock3,
  ExternalLink,
  FlaskConical,
  History,
  KeyRound,
  LogOut,
  RefreshCw,
  Search,
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
  FailureScenarioResult,
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
  const tone = value === "needs attention" || value === "failed" ? "red" : value === "halted" || value === "proposed" ? "amber" : value === "charged" || value === "executed" ? "green" : "slate";
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

function CaseCard({ item, selected, onClick, proposal, disabled }: {
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

function Inspector({ detail, busy, loading, error, onRetry, displayName, onDecision, onCopyLink }: {
  detail: CaseDetail | null;
  busy: boolean;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  displayName: string;
  onDecision: (decision: "approve" | "reject") => void;
  onCopyLink: (url: string) => void;
}) {
  if (loading) return <section className="inspector empty-state" role="status"><RefreshCw className="spin" /><h2>Loading case details</h2><p>Checking the latest proposal before enabling decisions.</p></section>;
  if (error) return <section className="inspector empty-state" role="alert"><AlertTriangle /><h2>Case could not be loaded</h2><p>{error}</p><button className="btn ghost" onClick={onRetry}>Retry case</button></section>;
  if (!detail) return <section className="inspector empty-state"><Sparkles /><h2>Select a recovery case</h2><p>Inspect the evidence, model scores, policy override and complete audit context.</p></section>;
  const proposal = detail.proposals[0];
  return (
    <section className="inspector">
      <div className="inspector-head">
        <div><h2>{detail.customer_name}</h2><p>{detail.subscription_id}</p></div>
        <div className="amount-block"><small>Outstanding</small><strong>{detail.enrichment_state === "pending" ? "Verifying" : detail.enrichment_state === "failed" ? "Unavailable" : money(detail.amount_paise)}</strong></div>
      </div>
      <div className="case-facts">
        <div><span>Status</span><StatusPill value={detail.status} /></div>
        <div><span>Failure</span><b>{cleanLabel(detail.failure_reason)}</b></div>
        <div><span>Attempts</span><b>{detail.retry_count}</b></div>
        <div><span>Case source</span><b>{detail.source === "synthetic" ? "Synthetic demo" : "Razorpay test"}</b></div>
      </div>
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
            <>
              {proposal.recommended_action === "CREATE_RECOVERY_LINK" && (
                <div className="execution-preview">
                  <div><span>Exact amount</span><b>{money(detail.amount_paise)}</b></div>
                  <div><span>Link expiry</span><b>48 hours</b></div>
                  <div><span>Notifications</span><b>Disabled</b></div>
                  <small>Test-mode only. Approval creates one Razorpay link and does not send it to the customer.</small>
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
          {detail.active_recovery_link_id && detail.active_recovery_link_url && (
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

function EvaluationView({ data, displayName, running, onRun }: { data: EvaluationSummary | null; displayName: string; running: boolean; onRun: () => void }) {
  const best = data?.policies.find((policy) => policy.policy === "PayMender");
  const max = Math.max(...(data?.policies.map((policy) => policy.net_recovered_mean) ?? [1]));
  const exportEvaluation = () => {
    if (!data) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify({ evidence_source: "synthetic", evaluation: data }, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "paymender-synthetic-evaluation.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <main className="view-page">
      <div className="page-intro"><div><h1>Held-out recovery evaluation</h1><p>Compare ten fixed synthetic batches against three non-learning baselines.</p></div><div className="evaluation-actions">{data && <button className="btn ghost" onClick={exportEvaluation}><Download />Export evaluation</button>}<button className="btn primary" onClick={onRun} disabled={running}>{running ? <RefreshCw className="spin" /> : <BarChart3 />}Run evaluation</button></div></div>
      {!data ? <div className="large-empty"><BarChart3 /><h2>No evaluation run yet</h2><p>Run the deterministic harness to generate transparent, reproducible evidence.</p></div> : (
        <>
          <div className="disclaimer"><FlaskConical /><div><b>Synthetic by design</b><span>{data.synthetic_disclaimer}</span></div><code>{data.train_records.toLocaleString()} train · {data.batches} × {data.cases_per_batch} test</code></div>
          <div className="eval-kpis">
            <KpiCard label="Mean net recovery" value={`${moneyRupees(best?.net_recovered_mean ?? 0)} ± ${moneyRupees(best?.net_recovered_std ?? 0)}`} note={`per ${data.cases_per_batch}-case held-out batch`} icon={CircleDollarSign} accent />
            <KpiCard label="Recovery rate" value={`${((best?.recovery_rate_mean ?? 0) * 100).toFixed(1)}% ± ${((best?.recovery_rate_std ?? 0) * 100).toFixed(1)}%`} note="simulated successful interventions" icon={Activity} />
            <KpiCard label="Contacts / recovery" value={`${(best?.contacts_per_recovery_mean ?? 0).toFixed(2)} ± ${(best?.contacts_per_recovery_std ?? 0).toFixed(2)}`} note="lower avoids customer fatigue" icon={UserCheck} />
            <KpiCard label="Unsafe actions blocked" value={`${(best?.unsafe_blocked_mean ?? 0).toFixed(1)} ± ${(best?.unsafe_blocked_std ?? 0).toFixed(1)}`} note="policy overrides per batch" icon={ShieldCheck} />
          </div>
          <section className="evaluation-chart card-surface">
            <div className="section-title"><span>Net rupees recovered by policy</span><small>mean ± standard deviation</small></div>
            {data.policies.map((policy) => (
              <div className={`eval-row ${policy.policy === "PayMender" ? "winner" : ""}`} key={policy.policy}>
                <div className="eval-name"><b>{policy.policy === "PayMender" ? displayName : policy.policy}</b><span>{(policy.recovery_rate_mean * 100).toFixed(1)}% ± {(policy.recovery_rate_std * 100).toFixed(1)}% recovered</span></div>
                <div className="eval-track"><span style={{ width: `${(policy.net_recovered_mean / max) * 100}%` }} /></div>
                <div className="eval-number"><b>{moneyRupees(policy.net_recovered_mean)}</b><span>± {moneyRupees(policy.net_recovered_std)}</span></div>
              </div>
            ))}
          </section>
          <section className="metric-table card-surface">
            <div className="section-title"><span>Full metric disclosure</span><small>no cherry-picked case</small></div>
            <div className="table-scroll"><table><thead><tr><th>Policy</th><th>Gross ₹</th><th>Net ₹</th><th>Recovery</th><th>Contacts / recovery</th><th>Escalation</th><th>Stopped</th><th>Unsafe blocked</th></tr></thead><tbody>{data.policies.map((policy) => <tr key={policy.policy}><td><b>{policy.policy}</b></td><td>{moneyRupees(policy.gross_recovered_mean)} ± {moneyRupees(policy.gross_recovered_std)}</td><td>{moneyRupees(policy.net_recovered_mean)} ± {moneyRupees(policy.net_recovered_std)}</td><td>{(policy.recovery_rate_mean * 100).toFixed(1)}% ± {(policy.recovery_rate_std * 100).toFixed(1)}%</td><td>{policy.contacts_per_recovery_mean.toFixed(2)} ± {policy.contacts_per_recovery_std.toFixed(2)}</td><td>{(policy.escalation_rate_mean * 100).toFixed(1)}% ± {(policy.escalation_rate_std * 100).toFixed(1)}%</td><td>{policy.stopped_mean.toFixed(1)} ± {policy.stopped_std.toFixed(1)}</td><td>{policy.unsafe_blocked_mean.toFixed(1)} ± {policy.unsafe_blocked_std.toFixed(1)}</td></tr>)}</tbody></table></div>
          </section>
        </>
      )}
    </main>
  );
}

function FailureLab({ audit, result, running, onInject }: { audit: AuditEvent[]; result: FailureScenarioResult | null; running: boolean; onInject: (scenario: string) => void }) {
  const scenarios = [
    { id: "duplicate", icon: History, title: "Concurrent duplicate", text: "Replay ten identical webhook deliveries and prove exactly-once intake." },
    { id: "gemini-quota", icon: Sparkles, title: "Gemini quota exhausted", text: "Show deterministic explanation fallback without relaxing policy gates." },
    { id: "razorpay-500", icon: AlertTriangle, title: "Razorpay returns 5xx", text: "Mark the external action retryable without recording a false success." },
    { id: "worker-crash", icon: RefreshCw, title: "Worker crashes mid-job", text: "Reclaim an expired lease around the stored, PII-minimized event envelope." },
  ];
  return (
    <main className="view-page">
      <div className="page-intro"><div><h1>Reliability lab</h1><p>Verify how the system contains dependency failures and duplicate delivery.</p></div></div>
      <div className="failure-grid">{scenarios.map(({ id, icon: Icon, title, text }) => <button className="failure-card" key={id} disabled={running} onClick={() => onInject(id)}><div className="failure-icon"><Icon /></div><div><h3>{title}</h3><p>{text}</p><span>{running ? "Running contained check" : "Run contained check"} <ArrowRight size={15} /></span></div></button>)}</div>
      {result && <section className="lab-result card-surface" aria-live="polite"><div className="section-title"><span>{cleanLabel(result.scenario)} contained</span><small>{result.evidence_ids.length} evidence IDs</small></div><div className="lab-assertions">{Object.entries(result.assertions).map(([name, passed]) => <div key={name}><Check size={15} /><span>{cleanLabel(name)}</span><b>{passed ? "Passed" : "Failed"}</b></div>)}</div><p className="lab-evidence"><b>Evidence:</b> {result.evidence_ids.join(" · ")}</p></section>}
      <section className="card-surface lab-audit"><div className="section-title"><span>Containment evidence</span><small>latest audit events</small></div><AuditTimeline audit={audit.filter((event) => event.category === "failure" || event.category === "safety").slice(0, 12)} /></section>
    </main>
  );
}

function AuditTimeline({ audit }: { audit: AuditEvent[] }) {
  return <div className="audit-list">{audit.map((event) => <div className={`audit-item ${event.severity}`} key={event.id}><span className="audit-dot" /><div><b>{event.title}</b><p>{event.detail}</p><small>{new Date(event.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · {event.category}</small><details className="audit-reference"><summary>Evidence references</summary><code>Event: {event.id}{event.case_id ? ` · Case: ${event.case_id}` : " · Run-level event"}</code></details></div></div>)}</div>;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [displayName, setDisplayName] = useState("PayMender");
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
  const [failureResult, setFailureResult] = useState<FailureScenarioResult | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("recent");
  const [auditScope, setAuditScope] = useState("run");
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const selectedCase = useRef<string | null>(null);
  const detailRequest = useRef(0);
  const portfolioRequest = useRef(0);

  const selectCase = useCallback(async (id: string) => {
    const requestId = ++detailRequest.current;
    selectedCase.current = id;
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const nextDetail = await api.case(id);
      if (requestId === detailRequest.current) setDetail(nextDetail);
    } catch (error) {
      if (requestId === detailRequest.current) setDetailError(error instanceof Error ? error.message : "Check your connection and retry.");
    } finally {
      if (requestId === detailRequest.current) setDetailLoading(false);
    }
  }, []);

  const load = useCallback(async (preferredId?: string | null) => {
    const requestId = ++portfolioRequest.current;
    setRefreshing(true);
    setLoadError(null);
    try {
      const [nextCases, nextMetrics, nextAudit, nextEval] = await Promise.all([api.cases(), api.metrics(), api.audit(), api.evaluation()]);
      if (requestId !== portfolioRequest.current) return;
      setCases(nextCases); setMetrics(nextMetrics); setAudit(nextAudit); setEvaluation(nextEval);
      setLastUpdated(new Date());
      const candidate = preferredId === undefined ? selectedCase.current : preferredId;
      const id = nextCases.find((item) => item.id === candidate)?.id ?? nextCases[0]?.id;
      if (id) await selectCase(id);
      else {
        ++detailRequest.current;
        selectedCase.current = null;
        setSelectedId(null); setDetail(null); setDetailError(null); setDetailLoading(false);
      }
    } catch (error) {
      if (requestId === portfolioRequest.current) setLoadError(error instanceof Error ? error.message : "Check your connection and refresh.");
    } finally {
      if (requestId === portfolioRequest.current) setRefreshing(false);
    }
  }, [selectCase]);

  useEffect(() => {
    if (authenticated) void load();
  }, [authenticated, load]);

  useEffect(() => {
    api.status().then((status) => {
      setDisplayName(status.display_name);
      document.title = `${status.display_name} - Recovery Command Center`;
    }).catch(() => undefined);
  }, []);

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
    ++portfolioRequest.current;
    ++detailRequest.current;
    selectedCase.current = null;
    api.signOut();
    setAuthenticated(false);
    setCases([]);
    setDetail(null);
    setSelectedId(null);
    setMetrics(null); setAudit([]); setEvaluation(null); setFailureResult(null);
    setNotice(null); setLoadError(null); setDetailError(null); setLastUpdated(null);
    setRefreshing(false); setDetailLoading(false); setConfirmReset(false);
    setQuery(""); setStatusFilter("all"); setSortBy("recent"); setAuditScope("run"); setView("command");
  };

  const decide = async (decision: "approve" | "reject") => {
    if (!selectedId || detail?.id !== selectedId || detailLoading || busy || refreshing || loadError) return;
    setBusy(true);
    try { setDetail(await api.approve(selectedId, decision)); await load(selectedId); setNotice(decision === "approve" ? "Action approved and safely executed." : "Proposal rejected; no action was taken."); }
    catch (error) { await load(selectedId); setNotice(error instanceof Error ? error.message : "Action failed safely."); }
    finally { setBusy(false); }
  };
  const runEval = async () => { setBusy(true); try { setEvaluation(await api.runEvaluation()); setNotice("Held-out evaluation completed."); } catch (error) { setNotice(error instanceof Error ? error.message : "Evaluation failed."); } finally { setBusy(false); } };
  const reset = async () => { setConfirmReset(false); setBusy(true); try { await api.reset(); setQuery(""); setStatusFilter("all"); setFailureResult(null); await load(null); setNotice("Demo data restored. A new evidence run has started."); } catch (error) { setNotice(error instanceof Error ? error.message : "Demo reset failed. Try again."); } finally { setBusy(false); } };
  const inject = async (scenario: string) => { setBusy(true); try { const result = await api.inject(scenario); setFailureResult(result); await load(selectedId); setNotice("Contained scenario passed every assertion. Evidence IDs are shown in the Reliability Lab."); } catch (error) { setNotice(error instanceof Error ? error.message : "Contained scenario failed."); } finally { setBusy(false); } };
  const copyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Recovery link copied. No notification was sent.");
    } catch {
      setNotice("Copy was blocked by the browser. Open the link and copy it from the address bar.");
    }
  };

  const latestProposalByCase = useMemo(() => new Map(cases.map((item) => [item.id, detail?.id === item.id ? detail.proposals[0] : undefined])), [cases, detail]);
  const visibleCases = useMemo(() => {
    const search = query.trim().toLowerCase();
    return cases.filter((item) => (statusFilter === "all" || item.status === statusFilter)
      && [item.customer_name, item.subscription_id, item.id, cleanLabel(item.failure_reason)].some((value) => value.toLowerCase().includes(search)))
      .sort((a, b) => sortBy === "amount" ? b.amount_paise - a.amount_paise : sortBy === "overdue" ? b.days_overdue - a.days_overdue : Date.parse(b.updated_at) - Date.parse(a.updated_at));
  }, [cases, query, statusFilter, sortBy]);
  const scopedAudit = auditScope === "case" ? audit.filter((event) => event.case_id === selectedId) : audit;

  if (!authenticated) {
    return (
      <main className="access-shell">
        <section className="access-card">
          <div className="access-brand"><div className="logo-glyph"><Zap fill="currentColor" /></div><div><b>{displayName}</b><span>Operator command center</span></div></div>
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
        <div className="brand-mark"><div className="logo-glyph"><Zap fill="currentColor" /></div><div><b>{metrics?.display_name ?? displayName}</b><span>Revenue Recovery</span></div></div>
        <nav>
          <button className={view === "command" ? "active" : ""} onClick={() => setView("command")}><Activity />Command center</button>
          <button className={view === "evaluation" ? "active" : ""} onClick={() => setView("evaluation")}><BarChart3 />Evaluation</button>
          {metrics?.demo_mode && <button className={view === "failures" ? "active" : ""} onClick={() => setView("failures")}><FlaskConical />Reliability lab</button>}
        </nav>
        <div className="trust-card"><ShieldCheck /><b>Bounded by design</b><p>AI recommends. Policy constrains. You approve every external action.</p><span><i /> TEST ENVIRONMENT</span></div>
      </aside>
      <div className="main-shell">
        <header className="topbar"><div role="status">{loadError ? <AlertTriangle size={15} /> : refreshing ? <RefreshCw size={15} className="spin" /> : <span className="live-dot" />}{loadError ? "Refresh needed" : refreshing ? "Updating portfolio" : lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}` : "Connecting"}</div><div className="top-actions"><span className="mode-pill">{metrics ? metrics.demo_mode ? "Synthetic demo" : "Razorpay test" : "Loading mode"}</span><button className="icon-btn" onClick={() => void load()} disabled={busy || refreshing} title="Refresh portfolio" aria-label="Refresh portfolio"><RefreshCw size={17} /></button>{metrics?.demo_mode && <button className="icon-btn" onClick={() => setConfirmReset(true)} disabled={busy || refreshing} title="Reset demo" aria-label="Reset demo data"><History size={17} /></button>}<button className="icon-btn" onClick={signOut} disabled={busy} title="Lock command center" aria-label="Lock command center"><LogOut size={17} /></button></div></header>
        {loadError && <div className="portfolio-alert" role="alert"><AlertTriangle size={18} /><div><b>Portfolio could not be refreshed</b><p>{loadError} Displayed data may be out of date. Refresh before approving.</p></div><button className="btn ghost" onClick={() => void load()} disabled={refreshing}>Try refresh again</button></div>}
        {confirmReset && <div className="portfolio-alert" role="alert"><History size={18} /><div><b>Start a new demo run?</b><p>This removes the current synthetic cases, approvals and audit history.</p></div><button className="btn ghost" onClick={() => setConfirmReset(false)}>Keep current run</button><button className="btn primary" onClick={reset} disabled={busy || refreshing}>Start new run</button></div>}
        {view === "command" && <main className="command-view">
          <div className="command-intro"><div><h1>Recover failed subscriptions safely.</h1><p>Prioritize the right intervention, approve money actions, and trace every decision.</p></div><div className="batch-badge"><span>Current portfolio</span><b>{metrics?.total_cases ?? 0} cases processed</b><small><Check size={13} /> All policy gates active</small></div></div>
          <div className="kpi-grid">
            <KpiCard label="Revenue at risk" value={money(metrics?.at_risk_paise ?? 0)} note="active failed subscriptions" icon={AlertTriangle} />
            <KpiCard label="Predicted recoverable" value={money(metrics?.predicted_recoverable_paise ?? 0)} note="policy-adjusted expected value" icon={Sparkles} accent />
            <KpiCard label="Confirmed recovered" value={money(metrics?.recovered_paise ?? 0)} note="webhook-confirmed test revenue" icon={CircleDollarSign} />
            <KpiCard label="Awaiting approval" value={String(metrics?.pending_approvals ?? 0)} note={`${metrics?.blocked_actions ?? 0} risky actions contained`} icon={ShieldCheck} />
          </div>
          <div className="command-grid">
            <section className="case-queue" aria-label="Recovery queue"><div className="queue-head"><div><h2>Recovery queue</h2><span aria-live="polite">{metrics ? `${visibleCases.length} of ${cases.length} cases` : "Loading cases"}</span></div><div className="queue-count">{metrics?.pending_approvals ?? 0} gated</div></div>
              <div className="queue-controls">
                <label className="queue-search"><Search size={16} /><input aria-label="Search recovery cases" type="search" placeholder="Name, subscription or failure" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
                <div className="queue-selects"><label>Status<select aria-label="Status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{[...new Set(cases.map((item) => item.status))].sort().map((status) => <option key={status} value={status}>{cleanLabel(status)}</option>)}</select></label><label>Sort by<select aria-label="Sort by" value={sortBy} onChange={(event) => setSortBy(event.target.value)}><option value="recent">Recently updated</option><option value="amount">Highest amount</option><option value="overdue">Most overdue</option></select></label></div>
              </div>
              <div className="case-list">{visibleCases.map((item) => <CaseCard key={item.id} item={item} selected={selectedId === item.id} proposal={latestProposalByCase.get(item.id)} disabled={busy} onClick={() => void selectCase(item.id)} />)}{metrics && cases.length === 0 && <div className="queue-empty"><Clock3 /><b>Waiting for a failed subscription</b><span>Signed Razorpay test webhooks will appear here after verification.</span></div>}{cases.length > 0 && visibleCases.length === 0 && <div className="queue-empty"><Search /><b>No matching cases</b><span>Try another name, subscription or status.</span><button className="btn ghost" onClick={() => { setQuery(""); setStatusFilter("all"); }}>Clear filters</button></div>}</div></section>
            <Inspector detail={detail} busy={busy || refreshing || !!loadError} loading={detailLoading} error={detailError} onRetry={() => { if (selectedId) void selectCase(selectedId); }} displayName={metrics?.display_name ?? displayName} onDecision={decide} onCopyLink={copyLink} />
          </div>
          <section className="command-audit card-surface"><div className="section-title"><span>Audit history</span><select aria-label="Audit scope" value={auditScope} onChange={(event) => setAuditScope(event.target.value)}><option value="run">Entire run</option><option value="case">Selected case</option></select></div><p className="audit-context">{auditScope === "case" ? detail?.subscription_id ?? "Select a case to inspect its history" : "Application-enforced append-only history"} · Showing {Math.min(scopedAudit.length, 8)} of {scopedAudit.length} loaded events (latest 80 in this run)</p>{scopedAudit.length ? <AuditTimeline audit={scopedAudit.slice(0, 8)} /> : <p className="audit-context">No events in this view yet.</p>}</section>
        </main>}
        {view === "evaluation" && <EvaluationView data={evaluation} displayName={metrics?.display_name ?? displayName} running={busy} onRun={runEval} />}
        {view === "failures" && metrics?.demo_mode && <FailureLab audit={audit} result={failureResult} running={busy} onInject={inject} />}
      </div>
      {notice && <button className="toast" onClick={() => setNotice(null)} aria-live="polite"><Check size={17} /><span>{notice}</span><X size={15} /></button>}
    </div>
  );
}
