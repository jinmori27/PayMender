import { CircleDollarSign } from "lucide-react";
import { cleanLabel } from "../format";

export function StatusPill({ value }: { value: string }) {
  const tone = value === "needs attention" || value === "failed" ? "red" : value === "halted" || value === "proposed" ? "amber" : value === "charged" || value === "executed" ? "green" : "slate";
  return <span className={`status-pill ${tone}`}><span />{cleanLabel(value)}</span>;
}

export function KpiCard({ label, value, note, icon: Icon, accent = false }: {
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
