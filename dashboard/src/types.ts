// Subset of RepoAgent API JSON used by the dashboard (mirrors SDK models).

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface JobEvent { at: string; status: JobStatus; message: string }

export interface JobRecord {
  id: string;
  kind: "investigate" | "repair" | "validated_repair";
  repository: string;
  status: JobStatus;
  events: JobEvent[];
  error: string | null;
}

export interface Evidence {
  evidence_id: string;
  file_path: string;
  qualified_name: string;
  start_line: number;
  end_line: number;
  snippet: string;
  relevance: string | null;
  graph_path: { source_symbol: string; relation: string; target_symbol: string }[];
}

export interface Hypothesis {
  hypothesis_id: string;
  statement: string;
  confidence: number;
  affected_symbols: string[];
  supporting_evidence: string[];
}

export interface Investigation {
  issue: { description: string };
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  primary_hypothesis_id: string | null;
  confidence: number;
  relevant_files: string[];
  relevant_symbols: string[];
  termination_reason: string;
  usage: { llm_calls: number; input_tokens: number; output_tokens: number };
}

export interface Review { decision: string; rationale: string; concerns: string[] }

export interface Proposal { plan: { summary: string; affected_files: string[] }; unified_diff: string }

export interface Attempt {
  number: number;
  proposal: Proposal;
  reviews: Review[];
  validation: { passed: boolean; summary: string };
  failure_analysis: { category: string; likely_reason: string } | null;
}

export interface ValidatedRepair {
  status: string;
  investigation: Investigation | null;
  baseline: { passed: boolean; summary: string } | null;
  attempts: Attempt[];
  final_proposal: Proposal | null;
  reviews: Review[];
  error: string | null;
  metrics: { attempts: number; llm_calls: number; input_tokens: number; output_tokens: number; retrieval_calls: number };
}

export interface StaticRepair {
  status: string;
  investigation: Investigation;
  proposal: Proposal | null;
  reviews: Review[];
}

export type JobResult = Investigation | ValidatedRepair | StaticRepair;
