import type { GraphView, JobRecord, ServerConfig, WorkflowResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : undefined;
    throw new Error(message ?? `Request failed (HTTP ${response.status})`);
  }
  return body as T;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  config: () => request<ServerConfig>("/config"),
  repair: (repository_url: string, issue: string, sandbox_validation: boolean) =>
    post<JobRecord>("/tasks/repair", { repository_url, issue, sandbox_validation }),
  discover: (repository_url: string) => post<JobRecord>("/tasks/discover", { repository_url }),
  repairFinding: (taskId: string, findingId: string, sandbox_validation: boolean) =>
    post<JobRecord>(`/tasks/${taskId}/findings/${findingId}/repair`, { sandbox_validation }),
  job: (id: string) => request<JobRecord>(`/tasks/${id}`),
  result: (id: string) => request<{ job: JobRecord; result: WorkflowResult | null }>(`/tasks/${id}/result`),
  graph: (id: string) => request<GraphView>(`/tasks/${id}/graph`),
  graphDownloadUrl: (id: string) => `/api/tasks/${id}/graph?format=graph.json`,
};

export type Api = typeof api;
