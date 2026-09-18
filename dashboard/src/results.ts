// Pure helpers that turn workflow reports into display-ready values.
import type { Proposal, RepairWorkflowResult, Review, StaticRepair, ValidatedRepair, Validation } from "./types";

export type Tone = "good" | "bad" | "neutral";

export function isValidated(report: RepairWorkflowResult["report"]): report is ValidatedRepair {
  return "attempts" in report && "metrics" in report;
}

const GOOD = new Set(["validated", "approved_for_runtime_validation", "verified"]);
const NEUTRAL = new Set(["uncertain", "insufficient_evidence", "insufficient_investigation", "validation_unavailable"]);

export function tone(status: string): Tone {
  if (GOOD.has(status)) return "good";
  return NEUTRAL.has(status) ? "neutral" : "bad";
}

export function humanize(value: string): string {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function proposalOf(report: ValidatedRepair | StaticRepair): Proposal | null {
  if (isValidated(report)) return report.final_proposal ?? report.attempts[report.attempts.length - 1]?.proposal ?? null;
  return report.proposal;
}

export function reviewsOf(report: ValidatedRepair | StaticRepair): Review[] {
  if (!isValidated(report)) return report.reviews;
  const attempt = report.attempts.flatMap((a) => a.reviews);
  return attempt.length ? attempt : report.reviews;
}

export function patchedValidation(report: ValidatedRepair): Validation | null {
  return report.attempts[report.attempts.length - 1]?.validation ?? null;
}

export interface TestRow { label: string; baseline: number | string; patched: number | string }

export function testRows(report: ValidatedRepair): TestRow[] {
  const before = report.baseline?.tests;
  const after = patchedValidation(report)?.tests;
  const cell = (summary: typeof before, key: "passed" | "failed" | "errors" | "skipped") =>
    summary && summary.parsed ? summary[key] : "—";
  return (["passed", "failed", "errors", "skipped"] as const).map((key) => ({
    label: humanize(key),
    baseline: cell(before, key),
    patched: cell(after, key),
  }));
}

export function lintSummary(validation: Validation | null | undefined): string {
  const lint = validation?.lint;
  if (!lint) return "not run";
  if (!lint.parsed) return "unavailable";
  return lint.total === 0 ? "clean" : `${lint.total} violation${lint.total === 1 ? "" : "s"}`;
}

export function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "diff-file";
  if (line.startsWith("@@")) return "diff-hunk";
  if (line.startsWith("+")) return "diff-add";
  if (line.startsWith("-")) return "diff-del";
  return "";
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
