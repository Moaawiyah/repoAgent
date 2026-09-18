import type { Api } from "../api";
import type { DiscoveryWorkflowResult, GraphView, JobRecord, RepairWorkflowResult, Stage } from "../types";

export const TASK = "a".repeat(32);
export const NEXT = "b".repeat(32);
const URL = "https://github.com/acme/shop";

export function stage(key: string, label: string, status: Stage["status"], detail = "", visits = 1): Stage {
  return { key, label, status, detail, visits };
}

export function job(status: JobRecord["status"], kind: JobRecord["kind"] = "discover", stages: Stage[] = []): JobRecord {
  return { id: TASK, kind, repository: URL, status, events: [{ at: "", status: "running", message: "Discovery workflow started" }], error: status === "failed" ? "Could not fetch the repository" : null, stages };
}

const evidence = { evidence_id: "e1", file_path: "shop/storage.py", qualified_name: "shop.storage.save", start_line: 80, end_line: 90, snippet: "fh = open(path)", relevance: "relevant", graph_path: [] };
const verification = (status: "verified" | "uncertain" | "rejected", confidence: number) => ({ status, reasoning: `Verifier says ${status}.`, supporting_evidence: ["open without close"], contradicting_evidence: [], confidence, recommended_verification: "" });

export const discovery: DiscoveryWorkflowResult = {
  workflow: "discover",
  repository: { source: URL, name: "acme/shop", path: "/w", commit: "c".repeat(40) },
  usage: { llm_calls: 3, tokens: 900 },
  report: {
    files_scanned: 12, symbols_scanned: 80,
    metrics: { candidates_generated: 5, duplicate_findings_removed: 2, verified: 1, uncertain: 1, rejected: 1, verification_llm_calls: 3 },
    candidates: [
      { id: "f1", category: "resource_handling", title: "Potential resource leak", description: "File opened without close.", confidence: 0.7, severity: "high", file: "shop/storage.py", symbol: "shop.storage.save", start_line: 82, end_line: 82, detection_source: "ast_resource", evidence: [evidence], status: "verified", verification: verification("verified", 0.91) },
      { id: "f2", category: "todo_marker", title: "TODO marker", description: "TODO left in code.", confidence: 0.3, severity: "low", file: "shop/cart.py", symbol: null, start_line: 5, end_line: 5, detection_source: "ast_todo", evidence: [], status: "rejected", verification: verification("rejected", 0.8) },
      { id: "f3", category: "coupling", title: "High coupling", description: "Many dependents.", confidence: 0.5, severity: "medium", file: "shop/core.py", symbol: null, start_line: 1, end_line: 1, detection_source: "graph_coupling", evidence: [], status: "uncertain", verification: verification("uncertain", 0.4) },
    ],
  },
};

const tests = (passed: number, failed: number) => ({ parsed: true, passed, failed, skipped: 0, errors: 0, failures: [] });
const investigation = {
  issue: { description: "Totals are wrong" }, issue_summary: "Cart totals ignore discounts", likely_affected_area: "shop.cart",
  evidence: [evidence], hypotheses: [{ hypothesis_id: "h1", statement: "Discount is applied after rounding", confidence: 0.8, affected_symbols: ["shop.cart.total"], supporting_evidence: ["e1"] }],
  primary_hypothesis_id: "h1", confidence: 0.8, relevant_files: ["shop/cart.py"], relevant_symbols: ["shop.cart.total"],
  termination_reason: "confident_root_cause", iterations: 2, usage: { llm_calls: 6, input_tokens: 1000, output_tokens: 200 }, error: null,
};
const proposal = { plan: { summary: "Apply discount before rounding", affected_files: ["shop/cart.py"], affected_symbols: [], risks: [] }, unified_diff: "--- a/shop/cart.py\n+++ b/shop/cart.py\n@@ -1 +1 @@\n-return round(x) - d\n+return round(x - d)" };

export const repair: RepairWorkflowResult = {
  workflow: "repair", repository: discovery.repository, issue: { description: "Totals are wrong" }, sandbox_validation: true, source_finding: null, usage: { llm_calls: 9, tokens: 4000 },
  report: {
    task_id: "t", status: "validated", investigation, final_proposal: proposal, reviews: [], reinvestigations: 0, error: null,
    baseline: { phase: "baseline", passed: false, summary: "1 failed", tests: tests(4, 1), lint: { parsed: true, total: 0, violations: [] }, comparison: null },
    attempts: [{
      number: 1, proposal, static_validation: { valid: true, errors: [] }, reviews: [{ decision: "approve", rationale: "Minimal and correct.", concerns: [] }], failure_analysis: null,
      validation: { phase: "patched", passed: true, summary: "5 passed", tests: tests(5, 0), lint: { parsed: true, total: 0, violations: [] }, comparison: { new_failures: [], fixed_failures: ["tests/test_cart.py::test_discount"], persisting_failures: [], new_lint: [] } },
    }],
    metrics: { attempts: 1, llm_calls: 9, input_tokens: 3000, output_tokens: 1000, retrieval_calls: 4, files_changed: 1, lines_added: 1, lines_removed: 1 },
  },
};

export const graph: GraphView = {
  repository: "acme/shop", total_nodes: 4, total_edges: 3, truncated: false,
  nodes: [
    { id: "shop.storage", kind: "module", name: "storage", file: "shop/storage.py", start_line: 1, end_line: 120, parent: null, module: "shop.storage", focus: true },
    { id: "shop.storage.save", kind: "function", name: "save", file: "shop/storage.py", start_line: 80, end_line: 90, parent: "shop.storage", module: "shop.storage", focus: true },
    { id: "shop.cart", kind: "module", name: "cart", file: "shop/cart.py", start_line: 1, end_line: 40, parent: null, module: "shop.cart", focus: false },
    { id: "shop.cart.Cart", kind: "class", name: "Cart", file: "shop/cart.py", start_line: 3, end_line: 30, parent: "shop.cart", module: "shop.cart", focus: false },
  ],
  edges: [
    { source: "shop.storage", target: "shop.storage.save", edge_type: "defines", line: null, resolved: true },
    { source: "shop.cart", target: "shop.storage", edge_type: "imports", line: 1, resolved: true },
    { source: "shop.cart.Cart", target: "shop.storage.save", edge_type: "calls", line: 12, resolved: false },
  ],
};

export function fakeApi(overrides: Partial<Api> = {}): Api {
  return {
    config: async () => ({ github_enabled: true, github_execution: ["acme/shop"], llm_configured: true }),
    repair: async () => job("queued", "repair"),
    discover: async () => job("queued"),
    repairFinding: async () => ({ ...job("queued", "validated_repair"), id: NEXT }),
    job: async () => job("succeeded"),
    result: async () => ({ job: job("succeeded"), result: discovery }),
    graph: async () => graph,
    graphDownloadUrl: (id: string) => `/api/tasks/${id}/graph?format=graph.json`,
    ...overrides,
  };
}
