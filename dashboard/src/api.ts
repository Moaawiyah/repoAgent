import type { JobRecord, JobResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`);
  }
  return body as T;
}

export interface SubmitOptions { repository: string; issue: string; execute: boolean }

export function submitInvestigation(options: SubmitOptions): Promise<JobRecord> {
  const { repository, issue } = options;
  return request("/investigate", { method: "POST", body: JSON.stringify({ repository, issue }) });
}

export function submitRepair(options: SubmitOptions): Promise<JobRecord> {
  return request("/repair", { method: "POST", body: JSON.stringify(options) });
}

export function getJob(id: string): Promise<JobRecord> {
  return request(`/tasks/${id}`);
}

export function getResult(id: string): Promise<{ job: JobRecord; result: JobResult | null }> {
  return request(`/tasks/${id}/result`);
}

export function getConfig(): Promise<{ execution_repositories: string[] }> {
  return request("/config");
}

export interface GraphInspection {
  symbol: string;
  outgoing: { source: string; target: string; edge_type: string }[];
  incoming: { source: string; target: string; edge_type: string }[];
}

export function getGraph(repository: string, symbol: string): Promise<GraphInspection> {
  const query = new URLSearchParams({ repository, symbol });
  return request(`/graph?${query.toString()}`);
}
