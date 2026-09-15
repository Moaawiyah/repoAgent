import { describe, expect, it } from "vitest";
import { buildTimeline, finalStatus } from "./timeline";
import type { JobRecord, ValidatedRepair } from "./types";

const job = (status: JobRecord["status"], messages: string[] = []): JobRecord => ({
  id: "a".repeat(32),
  kind: "validated_repair",
  repository: "/repo",
  status,
  error: status === "failed" ? "Docker unavailable" : null,
  events: messages.map((message) => ({ at: "", status: "running", message })),
});

const investigation = {
  issue: { description: "bug" }, evidence: [{ evidence_id: "e", file_path: "a.py", qualified_name: "a.f", start_line: 1, end_line: 2, snippet: "", relevance: "relevant", graph_path: [] }],
  hypotheses: [], primary_hypothesis_id: null, confidence: 0.8, relevant_files: ["a.py"], relevant_symbols: ["a.f"],
  termination_reason: "confident_root_cause", usage: { llm_calls: 5, input_tokens: 0, output_tokens: 0 },
};

const repair: ValidatedRepair = {
  status: "validated", investigation, baseline: { passed: true, summary: "completed" }, final_proposal: null, reviews: [], error: null,
  metrics: { attempts: 2, llm_calls: 9, input_tokens: 0, output_tokens: 0, retrieval_calls: 3 },
  attempts: [
    { number: 1, proposal: { plan: { summary: "", affected_files: [] }, unified_diff: "" }, reviews: [{ decision: "approve", rationale: "", concerns: [] }], validation: { passed: false, summary: "2 failed" }, failure_analysis: { category: "test_failure", likely_reason: "missed secondary lookup" } },
    { number: 2, proposal: { plan: { summary: "", affected_files: [] }, unified_diff: "" }, reviews: [{ decision: "approve", rationale: "", concerns: [] }], validation: { passed: true, summary: "passed" }, failure_analysis: null },
  ],
};

describe("buildTimeline", () => {
  it("shows running progress before a result exists", () => {
    const steps = buildTimeline(job("running", ["Repository analysis and indexing"]), null);
    expect(steps.map((s) => s.state)).toEqual(["done", "running"]);
  });

  it("derives attempts, failure analysis and final status from the report", () => {
    const steps = buildTimeline(job("succeeded", ["Repository analysis and indexing"]), repair);
    const labels = steps.map((s) => `${s.label}:${s.state}`);
    expect(labels).toContain("Sandbox Attempt 1:failed");
    expect(labels).toContain("Failure Analysis:done");
    expect(labels).toContain("Sandbox Attempt 2:done");
    expect(finalStatus(job("succeeded"), repair)).toBe("VALIDATED");
  });

  it("reports job failures without a result", () => {
    const steps = buildTimeline(job("failed"), null);
    expect(steps[steps.length - 1]).toMatchObject({ label: "Job failed", detail: "Docker unavailable" });
    expect(finalStatus(job("failed"), null)).toBe("FAILED");
    expect(finalStatus(job("succeeded"), investigation)).toBe("CONFIDENT_ROOT_CAUSE");
  });
});
