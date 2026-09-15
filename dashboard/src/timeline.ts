// Derive a progress timeline from observable job events and the final report.
import type { JobRecord, JobResult, ValidatedRepair } from "./types";

export type StepState = "done" | "failed" | "running" | "pending";
export interface Step { label: string; state: StepState; detail?: string }

function isValidated(result: JobResult | null): result is ValidatedRepair {
  return !!result && "attempts" in result && "metrics" in result;
}

function investigationOf(result: JobResult | null) {
  if (!result) return null;
  return "evidence" in result ? result : result.investigation;
}

export function buildTimeline(job: JobRecord, result: JobResult | null): Step[] {
  const finished = job.status === "succeeded" || job.status === "failed";
  const steps: Step[] = [
    { label: "Repository Analysis", state: job.events.some((e) => e.message.startsWith("Repository")) ? "done" : "pending" },
  ];
  const investigation = investigationOf(result);
  if (investigation) {
    const confident = investigation.termination_reason === "confident_root_cause";
    steps.push({ label: "Retrieval", state: investigation.evidence.length ? "done" : "failed" });
    steps.push({ label: "Investigator", state: confident ? "done" : "failed", detail: investigation.termination_reason });
  }
  if (isValidated(result)) {
    if (result.baseline) steps.push({ label: "Baseline", state: "done", detail: result.baseline.summary });
    for (const attempt of result.attempts) {
      steps.push({ label: `Developer (attempt ${attempt.number})`, state: "done" });
      const review = attempt.reviews[attempt.reviews.length - 1];
      steps.push({ label: "Reviewer", state: review?.decision === "approve" ? "done" : "failed", detail: review?.decision });
      steps.push({ label: `Sandbox Attempt ${attempt.number}`, state: attempt.validation.passed ? "done" : "failed", detail: attempt.validation.summary });
      if (attempt.failure_analysis) {
        steps.push({ label: "Failure Analysis", state: "done", detail: attempt.failure_analysis.likely_reason });
      }
    }
  } else if (result && "proposal" in result) {
    steps.push({ label: "Developer", state: result.proposal ? "done" : "failed" });
    const review = result.reviews[result.reviews.length - 1];
    steps.push({ label: "Reviewer", state: review?.decision === "approve" ? "done" : "failed", detail: review?.decision });
  }
  if (!finished) steps.push({ label: job.events[job.events.length - 1]?.message ?? "Queued", state: "running" });
  if (job.status === "failed") steps.push({ label: "Job failed", state: "failed", detail: job.error ?? undefined });
  return steps;
}

export function finalStatus(job: JobRecord, result: JobResult | null): string {
  if (job.status !== "succeeded") return job.status.toUpperCase();
  if (result && "status" in result) return result.status.toUpperCase();
  const investigation = investigationOf(result);
  return investigation ? investigation.termination_reason.toUpperCase() : "UNKNOWN";
}
