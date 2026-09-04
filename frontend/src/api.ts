import type { AuditEvent, CaseDetail, CaseSummary, EvaluationSummary, FailureScenarioResult, Metrics, PublicStatus } from "./types";

let operatorToken = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(operatorToken ? { "X-Operator-Token": operatorToken } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<PublicStatus>("/api/health"),
  authenticate: async (token: string) => {
    operatorToken = token;
    try {
      return await request<{ authenticated: boolean }>("/api/operator/session");
    } catch (error) {
      operatorToken = "";
      throw error;
    }
  },
  signOut: () => { operatorToken = ""; },
  cases: () => request<CaseSummary[]>("/api/cases"),
  case: (id: string) => request<CaseDetail>(`/api/cases/${id}`),
  metrics: () => request<Metrics>("/api/metrics"),
  audit: () => request<AuditEvent[]>("/api/audit?limit=80"),
  evaluation: () => request<EvaluationSummary | null>("/api/evaluations/latest"),
  runEvaluation: () => request<EvaluationSummary>("/api/evaluations", { method: "POST" }),
  approve: (id: string, decision: "approve" | "reject") =>
    request<CaseDetail>(`/api/cases/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ decision, note: decision === "approve" ? "Approved in operator command center." : "Rejected in operator command center." }),
    }),
  reset: () => request<{ reset: boolean }>("/api/demo/reset", { method: "POST" }),
  inject: (scenario: string) => request<FailureScenarioResult>(`/api/demo/failures/${scenario}`, { method: "POST" }),
};
