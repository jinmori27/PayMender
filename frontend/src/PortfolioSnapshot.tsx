import type { CSSProperties } from "react";
import type { CaseSummary } from "./types";
import { cleanLabel } from "./format";

// Provider statuses are not proposal states: a halted subscription can still
// have a pending approval, and a charged subscription is not necessarily recovered.
const statusColors: Record<string, string> = {
  halted: "#ba852a",
  pending: "#6860c9",
  active: "#557ab5",
  authenticated: "#45838b",
  charged: "#27936b",
  cancelled: "#8991a3",
  completed: "#b2b8c6",
};

export function PortfolioSnapshot({ cases, loaded }: { cases: CaseSummary[]; loaded: boolean }) {
  const counts = new Map<string, number>();
  for (const item of cases) counts.set(item.status, (counts.get(item.status) ?? 0) + 1);
  const groups = [...counts].sort(([a], [b]) => a.localeCompare(b));
  const segmentStyle = (status: string): CSSProperties =>
    ({ "--segment-color": statusColors[status] ?? "#8991a3" }) as CSSProperties;

  return (
    <section className="portfolio-snapshot card-surface" aria-label="Portfolio snapshot">
      <div className="snapshot-heading">
        <div><h2>Payment status</h2><p>Current case statuses, not a recovery-rate forecast.</p></div>
        <span>{loaded ? `${cases.length} cases in this run` : "Loading case statuses"}</span>
      </div>
      {cases.length > 0 ? <>
        <div className="snapshot-track" aria-hidden="true">
          {groups.map(([status, count]) => <span key={status} style={{ ...segmentStyle(status), flex: count }} />)}
        </div>
        <dl className="snapshot-legend">
          {groups.map(([status, count]) => <div key={status} data-status={status} style={segmentStyle(status)}>
            <dt><span aria-hidden="true" />{cleanLabel(status)}</dt>
            <dd>{count}</dd>
          </div>)}
        </dl>
      </> : loaded && <p className="snapshot-empty">No cases yet. Verified failed-payment events will populate this summary.</p>}
    </section>
  );
}
