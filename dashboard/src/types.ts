// Subset of the RepoAgent API JSON used by the web app (mirrors SDK models).

export type JobStatus = "queued" | "running" | "succeeded" | "failed";
export type StageStatus = "pending" | "running" | "done" | "failed" | "skipped";
export type Operation = "repair" | "discover";

export interface Stage { key: string; label: string; status: StageStatus; visits: number; detail: string }
export interface JobEvent { at: string; status: JobStatus; message: string }

export interface JobRecord {
  id: string;
  kind: "investigate" | "repair" | "validated_repair" | "discover";
  repository: string;
  status: JobStatus;
  created_at?: string;
  updated_at?: string;
  events: JobEvent[];
  error: string | null;
  stages: Stage[];
}

export interface GraphHop { source_symbol: string; relation: string; target_symbol: string }

export interface Evidence {
  evidence_id: string;
  file_path: string;
  qualified_name: string;
  start_line: number;
  end_line: number;
  snippet: string;
  relevance: string | null;
  reason?: string | null;
  graph_path: GraphHop[];
}

export interface Hypothesis {
  hypothesis_id: string;
  statement: string;
  confidence: number;
  affected_symbols: string[];
  supporting_evidence: string[];
}

export interface Investigation {
  issue: { description: string; title?: string | null };
  issue_summary: string;
  likely_affected_area: string;
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  primary_hypothesis_id: string | null;
  confidence: number;
  relevant_files: string[];
  relevant_symbols: string[];
  termination_reason: string;
  iterations: number;
  usage: { llm_calls: number; input_tokens: number; output_tokens: number };
  error: string | null;
}

export interface Review { decision: "approve" | "revise" | "reject"; rationale: string; concerns: string[] }
export interface Proposal { plan: { summary: string; affected_files: string[]; affected_symbols: string[]; risks: string[] }; unified_diff: string }
export interface TestSummary { parsed: boolean; passed: number; failed: number; skipped: number; errors: number; failures: { test_id: string; message: string }[] }
export interface LintSummary { parsed: boolean; total: number; violations: { path: string; line: number; code: string; message: string }[] }

export interface Validation {
  phase: "baseline" | "patched";
  passed: boolean;
  summary: string;
  tests: TestSummary | null;
  lint: LintSummary | null;
  comparison: { new_failures: string[]; fixed_failures: string[]; persisting_failures: string[]; new_lint: string[] } | null;
}

export interface Attempt {
  number: number;
  proposal: Proposal;
  static_validation: { valid: boolean; errors: string[] };
  reviews: Review[];
  validation: Validation;
  failure_analysis: { category: string; likely_reason: string; next_action: string } | null;
}

export interface ValidatedRepair {
  task_id: string;
  status: string;
  investigation: Investigation | null;
  baseline: Validation | null;
  attempts: Attempt[];
  final_proposal: Proposal | null;
  reviews: Review[];
  reinvestigations: number;
  error: string | null;
  metrics: { attempts: number; llm_calls: number; input_tokens: number; output_tokens: number; retrieval_calls: number; files_changed: number; lines_added: number; lines_removed: number };
}

export interface StaticRepair {
  status: string;
  investigation: Investigation;
  proposal: Proposal | null;
  validation: { valid: boolean; errors: string[]; changed_files: string[] } | null;
  reviews: Review[];
  revisions: number;
  error: string | null;
}

export interface RepositoryHandle { source: string; name: string; path: string; commit: string | null }
export interface Usage { llm_calls: number; tokens: number }

export interface RepairWorkflowResult {
  workflow: "repair";
  repository: RepositoryHandle;
  issue: { description: string; title?: string | null };
  sandbox_validation: boolean;
  report: ValidatedRepair | StaticRepair;
  source_finding: string | null;
  usage: Usage;
}

export type Verification = "pending" | "verified" | "uncertain" | "rejected";

export interface Finding {
  id: string;
  category: string;
  title: string;
  description: string;
  confidence: number;
  severity: "low" | "medium" | "high";
  file: string;
  symbol: string | null;
  start_line: number;
  end_line: number;
  detection_source: string;
  evidence: Evidence[];
  status: Verification;
  verification: { status: Verification; reasoning: string; supporting_evidence: string[]; contradicting_evidence: string[]; confidence: number; recommended_verification: string } | null;
}

export interface AuditMetrics { candidates_generated: number; duplicate_findings_removed: number; verified: number; uncertain: number; rejected: number; verification_llm_calls: number }

export interface DiscoveryWorkflowResult {
  workflow: "discover";
  repository: RepositoryHandle;
  report: { files_scanned: number; symbols_scanned: number; candidates: Finding[]; metrics: AuditMetrics };
  usage: Usage;
}

export type WorkflowResult = RepairWorkflowResult | DiscoveryWorkflowResult;

export type NodeKind = "module" | "class" | "function" | "method";
export interface GraphNode { id: string; kind: NodeKind; name: string; file: string; start_line: number; end_line: number; parent: string | null; module: string; focus: boolean }
export interface GraphEdge { source: string; target: string; edge_type: "defines" | "contains" | "imports" | "inherits" | "calls"; line: number | null; resolved: boolean }
export interface GraphView { repository: string; nodes: GraphNode[]; edges: GraphEdge[]; total_nodes: number; total_edges: number; truncated: boolean }

export interface ServerConfig { github_enabled: boolean; github_execution: string[]; llm_configured: boolean }
