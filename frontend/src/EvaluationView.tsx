import { Activity, BarChart3, CircleDollarSign, Download, FlaskConical, RefreshCw, ShieldCheck, UserCheck } from "lucide-react";
import type { EvaluationSummary } from "./types";
import { moneyRupees } from "./format";
import { EmptyState, KpiCard } from "./components/ui";

export function EvaluationView({ data, displayName, running, onRun }: { data: EvaluationSummary | null; displayName: string; running: boolean; onRun: () => void }) {
  const best = data?.policies.find((policy) => policy.policy === "PayMender");
  const max = Math.max(...(data?.policies.map((policy) => Math.abs(policy.net_recovered_mean)) ?? []), 1);
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
    <main id="main-content" tabIndex={-1} className="view-page">
      <div className="page-intro"><div><h1>Held-out recovery evaluation</h1><p>Compare ten fixed synthetic batches against three non-learning baselines.</p></div><div className="evaluation-actions">{data && <button className="btn ghost" onClick={exportEvaluation}><Download />Export evaluation</button>}<button className="btn primary" onClick={onRun} disabled={running}>{running ? <RefreshCw className="spin" /> : <BarChart3 />}Run evaluation</button></div></div>
      {!data ? <EmptyState icon={BarChart3} title={running ? "Running evaluation" : "No evaluation run yet"} loading={running}>Run the deterministic harness to generate transparent, reproducible evidence.</EmptyState> : (
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
                <div className="eval-track" aria-hidden="true"><span style={{ width: `${(Math.abs(policy.net_recovered_mean) / max) * 100}%` }} /></div>
                <div className="eval-number"><b>{moneyRupees(policy.net_recovered_mean)}</b><span>± {moneyRupees(policy.net_recovered_std)}</span></div>
              </div>
            ))}
          </section>
          <section className="metric-table card-surface">
            <div className="section-title"><span>Full metric disclosure</span><small>no cherry-picked case</small></div>
            <p className="table-hint">All values are mean ± standard deviation. Scroll the table horizontally to compare every metric.</p><div className="table-scroll" role="region" aria-label="Evaluation metric comparison" tabIndex={0}><table><caption className="sr-only">Synthetic policy evaluation, mean and standard deviation</caption><thead><tr><th scope="col">Policy</th><th scope="col">Gross ₹</th><th scope="col">Net ₹</th><th scope="col">Recovery</th><th scope="col">Contacts / recovery</th><th scope="col">Escalation</th><th scope="col">Stopped</th><th scope="col">Unsafe blocked</th></tr></thead><tbody>{data.policies.map((policy) => <tr key={policy.policy}><th scope="row">{policy.policy}</th><td>{moneyRupees(policy.gross_recovered_mean)} ± {moneyRupees(policy.gross_recovered_std)}</td><td>{moneyRupees(policy.net_recovered_mean)} ± {moneyRupees(policy.net_recovered_std)}</td><td>{(policy.recovery_rate_mean * 100).toFixed(1)}% ± {(policy.recovery_rate_std * 100).toFixed(1)}%</td><td>{policy.contacts_per_recovery_mean.toFixed(2)} ± {policy.contacts_per_recovery_std.toFixed(2)}</td><td>{(policy.escalation_rate_mean * 100).toFixed(1)}% ± {(policy.escalation_rate_std * 100).toFixed(1)}%</td><td>{policy.stopped_mean.toFixed(1)} ± {policy.stopped_std.toFixed(1)}</td><td>{policy.unsafe_blocked_mean.toFixed(1)} ± {policy.unsafe_blocked_std.toFixed(1)}</td></tr>)}</tbody></table></div>
          </section>
        </>
      )}
    </main>
  );
}
