import { useEffect, useRef, type ReactNode } from "react";
import { AlertTriangle, Check, CircleDollarSign, RefreshCw, X, type LucideIcon } from "lucide-react";
import { cleanLabel } from "../format";

export function StatusPill({ value }: { value: string }) {
  const tone = value === "needs attention" || value === "failed" ? "red" : value === "halted" || value === "proposed" ? "amber" : value === "charged" || value === "executed" ? "green" : "slate";
  return <span className={`status-pill ${tone}`}><span />{cleanLabel(value)}</span>;
}

export function KpiCard({ label, value, note, icon: Icon, accent = false, loading = false }: {
  label: string; value: string; note: string; icon: typeof CircleDollarSign; accent?: boolean; loading?: boolean;
}) {
  return (
    <article className={`kpi-card ${accent ? "accent" : ""}`} aria-busy={loading}>
      <div className="kpi-top"><span>{label}</span><Icon size={17} /></div>
      <strong>{loading ? <span className="metric-placeholder">Loading</span> : value}</strong>
      <small>{loading ? "Waiting for portfolio data" : note}</small>
    </article>
  );
}

export function EmptyState({ title, children, icon: Icon, loading = false, error = false, action, className = "" }: {
  title: string; children: ReactNode; icon: LucideIcon; loading?: boolean; error?: boolean; action?: ReactNode; className?: string;
}) {
  return <section className={`empty-state ${className}`} role={error ? "alert" : loading ? "status" : undefined}>
    {loading ? <RefreshCw className="spin" aria-hidden="true" /> : <Icon aria-hidden="true" />}
    <h2>{title}</h2><p>{children}</p>{action}
  </section>;
}

export interface Notice { message: string; tone: "success" | "error" }

export function Notification({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  const Icon = notice.tone === "error" ? AlertTriangle : Check;
  return <div className={`toast ${notice.tone}`} role={notice.tone === "error" ? "alert" : "status"}>
    <Icon size={18} aria-hidden="true" /><span>{notice.message}</span>
    <button className="icon-btn" onClick={onDismiss} aria-label="Dismiss notification"><X size={16} /></button>
  </div>;
}

export function ConfirmReset({ busy, onCancel, onConfirm }: {
  busy: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current!;
    element.showModal();
    return () => { element.close(); previous?.focus(); };
  }, []);
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="reset-title" aria-describedby="reset-description" onCancel={onCancel}>
    <h2 id="reset-title">Start a new demo run?</h2>
    <p id="reset-description">This removes the current synthetic cases, approvals and audit history.</p>
    <div className="dialog-actions">
      <button className="btn ghost" autoFocus onClick={onCancel}>Keep current run</button>
      <button className="btn primary" disabled={busy} onClick={onConfirm}>Start new run</button>
    </div>
  </dialog>;
}
