import type { AuditEvent } from "../types";

export function AuditTimeline({ audit }: { audit: AuditEvent[] }) {
  return <div className="audit-list">{audit.map((event) => <div className={`audit-item ${event.severity}`} key={event.id}><span className="audit-dot" /><div><b>{event.title}</b><p>{event.detail}</p><small>{new Date(event.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · {event.category}</small><details className="audit-reference"><summary>Evidence references</summary><code>Event: {event.id}{event.case_id ? ` · Case: ${event.case_id}` : " · Run-level event"}</code></details></div></div>)}</div>;
}
