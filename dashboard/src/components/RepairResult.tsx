import { humanize, isValidated, lintSummary, patchedValidation, percent, proposalOf, reviewsOf, testRows, tone } from "../results";
import type { RepairWorkflowResult, ValidatedRepair } from "../types";
import { DiffView, EvidenceList, type Locate } from "./Evidence";

function Chips({ items, onLocate, file }: { items: string[]; onLocate: Locate; file?: boolean }) {
  if (items.length === 0) return <span className="muted">—</span>;
  return (
    <span className="chips">
      {items.map((item) => (
        <button key={item} type="button" className="chip-button" onClick={() => (file ? onLocate(null, item) : onLocate(item))}>{item}</button>
      ))}
    </span>
  );
}

function Validation({ report }: { report: ValidatedRepair }) {
  const patched = patchedValidation(report);
  const comparison = patched?.comparison;
  return (
    <section className="card">
      <h2>Sandbox validation</h2>
      <table className="compare">
        <thead><tr><th>Tests</th><th>Baseline</th><th>Patched</th></tr></thead>
        <tbody>
          {testRows(report).map((row) => (
            <tr key={row.label}><td>{row.label}</td><td>{row.baseline}</td><td>{row.patched}</td></tr>
          ))}
          <tr><td>Ruff</td><td>{lintSummary(report.baseline)}</td><td>{lintSummary(patched)}</td></tr>
        </tbody>
      </table>
      {comparison && (
        <ul className="facts">
          <li>Fixed failures: {comparison.fixed_failures.length ? comparison.fixed_failures.join(", ") : "none"}</li>
          <li>New failures: {comparison.new_failures.length ? comparison.new_failures.join(", ") : "none"}</li>
          <li>New lint findings: {comparison.new_lint.length || "none"}</li>
        </ul>
      )}
      <h3>Repair attempts</h3>
      <table>
        <thead><tr><th>#</th><th>Static check</th><th>Reviewer</th><th>Validation</th><th>Failure analysis</th></tr></thead>
        <tbody>
          {report.attempts.map((attempt) => {
            const review = attempt.reviews[attempt.reviews.length - 1];
            return (
              <tr key={attempt.number}>
                <td>{attempt.number}</td>
                <td className={attempt.static_validation.valid ? "good" : "bad"}>{attempt.static_validation.valid ? "valid" : "invalid"}</td>
                <td>{review ? humanize(review.decision) : "—"}</td>
                <td className={attempt.validation.passed ? "good" : "bad"}>{attempt.validation.summary || (attempt.validation.passed ? "passed" : "failed")}</td>
                <td>{attempt.failure_analysis ? `${humanize(attempt.failure_analysis.category)}: ${attempt.failure_analysis.likely_reason}` : "—"}</td>
              </tr>
            );
          })}
          {report.attempts.length === 0 && <tr><td colSpan={5} className="muted">No patch reached sandbox execution.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}

export function RepairResult({ result, onLocate }: { result: RepairWorkflowResult; onLocate: Locate }) {
  const report = result.report;
  const investigation = report.investigation;
  const primary = investigation?.hypotheses.find((h) => h.hypothesis_id === investigation.primary_hypothesis_id) ?? investigation?.hypotheses[0];
  const proposal = proposalOf(report);
  const reviews = reviewsOf(report);
  const validated = isValidated(report) ? report : null;
  const usage = validated?.metrics;
  return (
    <>
      <section className={`card status-banner ${tone(report.status)}`}>
        <div>
          <small>Final status</small>
          <h2>{humanize(report.status)}</h2>
          {report.error && <p>{report.error}</p>}
        </div>
        <ul className="facts">
          <li>Sandbox validation: {result.sandbox_validation ? "requested" : "not requested (static review only)"}</li>
          {result.source_finding && <li>From discovery finding <code>{result.source_finding}</code></li>}
          <li>LLM calls: {usage?.llm_calls ?? result.usage.llm_calls} · tokens: {usage ? `${usage.input_tokens} in / ${usage.output_tokens} out` : result.usage.tokens || "not reported"}</li>
          {validated && <li>Attempts: {validated.metrics.attempts} · re-investigations: {validated.reinvestigations}</li>}
        </ul>
      </section>
      <section className="card">
        <h2>Issue</h2>
        <p className="prewrap">{result.issue.description}</p>
      </section>
      {investigation && (
        <section className="card">
          <h2>Investigation</h2>
          <p>{investigation.issue_summary}</p>
          {investigation.likely_affected_area && <p className="hint">Likely area: {investigation.likely_affected_area}</p>}
          <h3>Root cause</h3>
          {primary ? (
            <p className="root-cause">{primary.statement} <span className="tag">{percent(primary.confidence)} confidence (uncalibrated)</span></p>
          ) : (
            <p className="muted">No confident root cause ({humanize(investigation.termination_reason)}).</p>
          )}
          <p>Affected files: <Chips items={investigation.relevant_files} onLocate={onLocate} file /></p>
          <p>Affected symbols: <Chips items={investigation.relevant_symbols} onLocate={onLocate} /></p>
          <h3>Evidence</h3>
          <EvidenceList items={investigation.evidence.filter((e) => e.relevance !== "irrelevant")} onLocate={onLocate} />
          <p className="hint">{investigation.iterations} iteration(s) · {investigation.usage.llm_calls} LLM calls</p>
        </section>
      )}
      {proposal && (
        <section className="card">
          <h2>Patch</h2>
          <p>{proposal.plan.summary}</p>
          <DiffView diff={proposal.unified_diff} />
          {proposal.plan.risks.length > 0 && <p className="hint">Risks: {proposal.plan.risks.join("; ")}</p>}
        </section>
      )}
      {reviews.length > 0 && (
        <section className="card">
          <h2>Reviewer decisions</h2>
          <ol className="reviews">
            {reviews.map((review, index) => (
              <li key={index}><span className={`tag ${tone(review.decision === "approve" ? "verified" : review.decision)}`}>{humanize(review.decision)}</span> {review.rationale}
                {review.concerns.length > 0 && <ul>{review.concerns.map((c) => <li key={c}>{c}</li>)}</ul>}
              </li>
            ))}
          </ol>
        </section>
      )}
      {validated ? <Validation report={validated} /> : (
        <section className="card"><h2>Sandbox validation</h2><p className="muted">Not run: this repair was reviewed statically; the patch was never applied or executed.</p></section>
      )}
    </>
  );
}
