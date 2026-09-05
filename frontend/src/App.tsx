import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Activity, AlertTriangle, ArrowRight, BarChart3, CircleDollarSign, Clock3, FlaskConical, History, HelpCircle, KeyRound, LogOut, RefreshCw, Search, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { api } from "./api";
import { RecoveryGuide } from "./RecoveryWorkflow";
import { PortfolioSnapshot } from "./PortfolioSnapshot";
import { Inspector } from "./CaseInspector";
import { EvaluationView } from "./EvaluationView";
import { FailureLab } from "./FailureLab";
import { CaseCard } from "./components/CaseCard";
import { AuditTimeline } from "./components/AuditTimeline";
import { ConfirmReset, KpiCard, Notification, type Notice } from "./components/ui";
import { cleanLabel, money } from "./format";
import type { AuditEvent, CaseDetail, CaseSummary, EvaluationSummary, FailureScenarioResult, Metrics } from "./types";

type View = "command" | "evaluation" | "failures" | "guide";

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
  const [notice, setNotice] = useState<Notice | null>(null);
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
  const notify = (message: string, tone: Notice["tone"] = "success") => setNotice({ message, tone });
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
    try { setDetail(await api.approve(selectedId, decision)); await load(selectedId); notify(decision === "approve" ? "Action approved and safely executed." : "Proposal rejected; no action was taken."); }
    catch (error) { await load(selectedId); notify(error instanceof Error ? error.message : "Action failed safely.", "error"); }
    finally { setBusy(false); }
  };
  const runEval = async () => { setBusy(true); try { setEvaluation(await api.runEvaluation()); notify("Held-out evaluation completed."); } catch (error) { notify(error instanceof Error ? error.message : "Evaluation failed.", "error"); } finally { setBusy(false); } };
  const reset = async () => { setConfirmReset(false); setBusy(true); try { await api.reset(); setQuery(""); setStatusFilter("all"); setFailureResult(null); await load(null); notify("Demo data restored. A new evidence run has started."); } catch (error) { notify(error instanceof Error ? error.message : "Demo reset failed. Try again.", "error"); } finally { setBusy(false); } };
  const inject = async (scenario: string) => { setBusy(true); try { const result = await api.inject(scenario); setFailureResult(result); await load(selectedId); notify("Contained scenario passed every assertion. Evidence IDs are shown in the Reliability Lab."); } catch (error) { notify(error instanceof Error ? error.message : "Contained scenario failed.", "error"); } finally { setBusy(false); } };
  const copyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      notify("Recovery link copied. No notification was sent.");
    } catch {
      notify("Copy was blocked by the browser. Open the link and copy it from the address bar.", "error");
    }
  };

  const visibleCases = useMemo(() => {
    const search = query.trim().toLowerCase();
    return cases.filter((item) => (statusFilter === "all" || item.status === statusFilter)
      && [item.customer_name, item.subscription_id, item.id, cleanLabel(item.failure_reason)].some((value) => value.toLowerCase().includes(search)))
      .sort((a, b) => sortBy === "amount" ? b.amount_paise - a.amount_paise : sortBy === "overdue" ? b.days_overdue - a.days_overdue : Date.parse(b.updated_at) - Date.parse(a.updated_at));
  }, [cases, query, statusFilter, sortBy]);
  useEffect(() => {
    if (authenticated) document.getElementById("main-content")?.focus({ preventScroll: true });
  }, [view, authenticated]);

  const reviewCase = async (id: string) => {
    await selectCase(id);
    requestAnimationFrame(() => {
      if (selectedCase.current !== id || !window.matchMedia("(max-width: 1000px)").matches) return;
      const inspector = document.querySelector<HTMLElement>(".inspector");
      inspector?.focus({ preventScroll: true });
      inspector?.scrollIntoView({ block: "start" });
    });
  };
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
            <input id="operator-token" type="password" autoComplete="off" value={operatorToken} onChange={(event) => setOperatorToken(event.target.value)} aria-invalid={!!authError} aria-describedby={authError ? "token-error" : undefined} required minLength={24} placeholder="Paste your local token" />
            {authError && <div id="token-error" className="access-error" role="alert"><AlertTriangle size={15} />{authError}</div>}
            <button className="btn primary" disabled={authBusy || operatorToken.trim().length < 24}>{authBusy ? <RefreshCw className="spin" /> : <KeyRound />}Unlock command center</button>
          </form>
          <small><ShieldCheck size={14} /> Money actions remain separately approval-gated.</small>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to workspace</a>
      <aside className="sidebar">
        <div className="brand-mark"><div className="logo-glyph"><Zap fill="currentColor" /></div><div><b>{metrics?.display_name ?? displayName}</b><span>Revenue Recovery</span></div></div>
        <nav aria-label="Main navigation">
          <button className={view === "command" ? "active" : ""} aria-current={view === "command" ? "page" : undefined} onClick={() => setView("command")}><Activity /><span>Command center</span></button>
          <button className={view === "evaluation" ? "active" : ""} aria-current={view === "evaluation" ? "page" : undefined} onClick={() => setView("evaluation")}><BarChart3 /><span>Evaluation</span></button>
          {metrics?.demo_mode && <button className={view === "failures" ? "active" : ""} aria-current={view === "failures" ? "page" : undefined} onClick={() => setView("failures")}><FlaskConical /><span>Reliability lab</span></button>}
          <button className={view === "guide" ? "active" : ""} aria-current={view === "guide" ? "page" : undefined} onClick={() => setView("guide")}><HelpCircle /><span>How it works</span></button>
        </nav>
        <div className="trust-card"><ShieldCheck /><b>Bounded by design</b><p>AI recommends. Policy constrains. You approve every external action.</p><span><i /> TEST ENVIRONMENT</span></div>
      </aside>
      <div className="main-shell">
        <header className="topbar"><div role="status">{loadError ? <AlertTriangle size={15} /> : refreshing ? <RefreshCw size={15} className="spin" /> : <span className="live-dot" />}{loadError ? "Refresh needed" : refreshing ? "Updating portfolio" : lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}` : "Connecting"}</div><div className="top-actions"><span className="mode-pill">{metrics ? metrics.demo_mode ? "Synthetic demo" : "Razorpay test" : "Loading mode"}</span><button className="icon-btn" onClick={() => void load()} disabled={busy || refreshing} title="Refresh portfolio" aria-label="Refresh portfolio"><RefreshCw size={17} /></button>{metrics?.demo_mode && <button className="icon-btn" onClick={() => setConfirmReset(true)} disabled={busy || refreshing} title="Reset demo" aria-label="Reset demo data"><History size={17} /></button>}<button className="icon-btn" onClick={signOut} disabled={busy} title="Lock command center" aria-label="Lock command center"><LogOut size={17} /></button></div></header>
        {loadError && <div className="portfolio-alert" role="alert"><AlertTriangle size={18} /><div><b>Portfolio could not be refreshed</b><p>{loadError} Displayed data may be out of date. Refresh before approving.</p></div><button className="btn ghost" onClick={() => void load()} disabled={refreshing}>Try refresh again</button></div>}
        {confirmReset && <ConfirmReset busy={busy || refreshing} onCancel={() => setConfirmReset(false)} onConfirm={reset} />}
        {view === "command" && <main id="main-content" tabIndex={-1} className="command-view">
          <div className="command-intro"><div><h1>Recover failed subscriptions safely.</h1><p>Prioritize the right intervention, approve money actions, and trace every decision.</p></div><div className="batch-badge"><span>Current portfolio</span><b>{metrics ? `${metrics.total_cases} cases processed` : "Loading portfolio"}</b><small><ShieldCheck size={13} /> Approval-gated actions</small></div></div>
          <div className="workspace-guide"><div><ShieldCheck size={20} /><p><b>You control the next action.</b> Review a case, check the safety decision, then approve if required.</p></div><button className="text-btn" onClick={() => setView("guide")}>Explore the workflow <ArrowRight size={16} /></button></div>
          <div className="kpi-grid" aria-label="Portfolio totals">
            <KpiCard loading={!metrics} label="Revenue at risk" value={money(metrics?.at_risk_paise ?? 0)} note="active failed subscriptions" icon={AlertTriangle} />
            <KpiCard loading={!metrics} label="Predicted recoverable" value={money(metrics?.predicted_recoverable_paise ?? 0)} note="policy-adjusted expected value" icon={Sparkles} accent />
            <KpiCard loading={!metrics} label="Confirmed recovered" value={money(metrics?.recovered_paise ?? 0)} note={metrics?.demo_mode ? "synthetic recovery evidence" : "webhook-confirmed test revenue"} icon={CircleDollarSign} />
            <KpiCard loading={!metrics} label="Awaiting approval" value={String(metrics?.pending_approvals ?? 0)} note={`${metrics?.blocked_actions ?? 0} risky actions contained`} icon={ShieldCheck} />
          </div>
          <PortfolioSnapshot cases={cases} loaded={metrics !== null} />
          <div className="command-grid">
            <section className="case-queue" aria-label="Recovery queue"><div className="queue-head"><div><h2>Recovery queue</h2><span aria-live="polite">{metrics ? `${visibleCases.length} of ${cases.length} cases` : "Loading cases"}</span></div><div className="queue-count">{metrics?.pending_approvals ?? 0} gated</div></div>
              <div className="queue-controls">
                <label className="queue-search"><Search size={16} /><input aria-label="Search recovery cases" type="search" placeholder="Name, subscription or failure" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
                <div className="queue-selects"><label>Status<select aria-label="Status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{[...new Set(cases.map((item) => item.status))].sort().map((status) => <option key={status} value={status}>{cleanLabel(status)}</option>)}</select></label><label>Sort by<select aria-label="Sort by" value={sortBy} onChange={(event) => setSortBy(event.target.value)}><option value="recent">Recently updated</option><option value="amount">Highest amount</option><option value="overdue">Most overdue</option></select></label></div>
              </div>
              <div className="case-list">{visibleCases.map((item) => <CaseCard key={item.id} item={item} selected={selectedId === item.id} proposal={detail?.id === item.id ? detail.proposals[0] : undefined} disabled={busy} onClick={() => void reviewCase(item.id)} />)}{metrics && cases.length === 0 && <div className="queue-empty"><Clock3 /><b>Waiting for a failed subscription</b><span>Signed Razorpay test webhooks will appear here after verification.</span></div>}{cases.length > 0 && visibleCases.length === 0 && <div className="queue-empty"><Search /><b>No matching cases</b><span>Try another name, subscription or status.</span><button className="btn ghost" onClick={() => { setQuery(""); setStatusFilter("all"); }}>Clear filters</button></div>}</div></section>
            <Inspector key={selectedId} detail={detail} busy={busy || refreshing || !!loadError} loading={detailLoading} error={detailError} onRetry={() => { if (selectedId) void selectCase(selectedId); }} displayName={metrics?.display_name ?? displayName} onDecision={decide} onCopyLink={copyLink} />
          </div>
          <section className="command-audit card-surface"><div className="section-title"><span>Audit history</span><select aria-label="Audit scope" value={auditScope} onChange={(event) => setAuditScope(event.target.value)}><option value="run">Entire run</option><option value="case">Selected case</option></select></div><p className="audit-context">{auditScope === "case" ? detail?.subscription_id ?? "Select a case to inspect its history" : "Application-enforced append-only history"} · Showing {Math.min(scopedAudit.length, 8)} of {scopedAudit.length} loaded events (latest 80 in this run)</p>{scopedAudit.length ? <AuditTimeline audit={scopedAudit.slice(0, 8)} /> : <p className="audit-context">No events in this view yet.</p>}</section>
        </main>}
        {view === "evaluation" && <EvaluationView data={evaluation} displayName={metrics?.display_name ?? displayName} running={busy} onRun={runEval} />}
        {view === "failures" && metrics?.demo_mode && <FailureLab audit={audit} result={failureResult} running={busy} onInject={inject} />}
        {view === "guide" && <RecoveryGuide demoMode={metrics?.demo_mode ?? true} onReview={() => setView("command")} />}
      </div>
      {notice && <Notification notice={notice} onDismiss={() => setNotice(null)} />}
    </div>
  );
}
