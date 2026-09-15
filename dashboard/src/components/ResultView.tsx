import type { Investigation, JobResult, Proposal, Review, ValidatedRepair } from "../types";
import { GraphPanel } from "./GraphPanel";

function investigationOf(result: JobResult): Investigation | null {
  return "evidence" in result ? result : result.investigation;
}

function Patch({ proposal, review }: { proposal: Proposal | null; review?: Review }) {
  if (!proposal) return null;
  return (
    <section className="panel">
      <h2>Patch</h2>
      <p>{proposal.plan.summary}</p>
      <pre className="diff">{proposal.unified_diff}</pre>
      {review && <p>Reviewer: <strong>{review.decision}</strong> — {review.rationale}</p>}
    </section>
  );
}

function Attempts({ repair }: { repair: ValidatedRepair }) {
  return (
    <section className="panel">
      <h2>Validation</h2>
      {repair.baseline && <p>Baseline: {repair.baseline.summary}</p>}
      <table>
        <thead><tr><th>#</th><th>Validation</th><th>Failure analysis</th></tr></thead>
        <tbody>
          {repair.attempts.map((attempt) => (
            <tr key={attempt.number}>
              <td>{attempt.number}</td>
              <td className={attempt.validation.passed ? "done" : "failed"}>{attempt.validation.summary}</td>
              <td>{attempt.failure_analysis?.likely_reason ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        Tokens in/out: {repair.metrics.input_tokens}/{repair.metrics.output_tokens} · LLM calls:{" "}
        {repair.metrics.llm_calls} · Retrieval calls: {repair.metrics.retrieval_calls}
      </p>
    </section>
  );
}

export function ResultView({ repository, result }: { repository: string; result: JobResult }) {
  const investigation = investigationOf(result);
  const primary = investigation?.hypotheses.find((h) => h.hypothesis_id === investigation.primary_hypothesis_id);
  const validated = "metrics" in result ? result : null;
  const proposal = validated ? validated.final_proposal : "proposal" in result ? result.proposal : null;
  const reviews = "reviews" in result ? result.reviews : [];
  return (
    <>
      {investigation && (
        <section className="panel">
          <h2>Investigation</h2>
          <p><em>{investigation.issue.description}</em></p>
          {primary && (
            <p>Root cause ({Math.round(primary.confidence * 100)}% confidence, uncalibrated): {primary.statement}</p>
          )}
          <p>Affected files: {investigation.relevant_files.join(", ") || "—"}</p>
          <p>Affected symbols: {investigation.relevant_symbols.join(", ") || "—"}</p>
          <h3>Evidence</h3>
          {investigation.evidence.filter((e) => e.relevance).map((item) => (
            <details key={item.evidence_id}>
              <summary>{item.file_path}:{item.start_line}-{item.end_line} · {item.qualified_name} ({item.relevance})</summary>
              <pre>{item.snippet}</pre>
              {item.graph_path.length > 0 && (
                <p>Graph path: {item.graph_path.map((hop) => `${hop.source_symbol} -${hop.relation}→ ${hop.target_symbol}`).join(" · ")}</p>
              )}
            </details>
          ))}
          {primary?.affected_symbols[0] && <GraphPanel repository={repository} symbol={primary.affected_symbols[0]} />}
          <p>LLM calls: {investigation.usage.llm_calls} · tokens {investigation.usage.input_tokens}/{investigation.usage.output_tokens}</p>
        </section>
      )}
      <Patch proposal={proposal} review={reviews[reviews.length - 1]} />
      {validated && <Attempts repair={validated} />}
      {validated?.error && <p className="error">{validated.error}</p>}
    </>
  );
}
