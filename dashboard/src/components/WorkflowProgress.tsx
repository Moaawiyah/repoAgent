import type { JobRecord, StageStatus } from "../types";

const ICON: Record<StageStatus, string> = { done: "✓", running: "●", pending: "○", failed: "✗", skipped: "–" };
const TEXT: Record<StageStatus, string> = { done: "done", running: "in progress", pending: "pending", failed: "failed", skipped: "skipped" };

export function WorkflowProgress({ job }: { job: JobRecord }) {
  const latest = job.events[job.events.length - 1]?.message;
  const finished = job.status === "succeeded" || job.status === "failed";
  return (
    <section className="card progress" aria-live="polite">
      <div className="card-head">
        <h2>Workflow progress</h2>
        <span className={`pill ${job.status}`}>{job.status}</span>
      </div>
      <ol className="stages">
        {job.stages.map((stage) => (
          <li key={stage.key} className={`stage ${stage.status}`} aria-label={`${stage.label}: ${TEXT[stage.status]}`}>
            <span className="stage-icon" aria-hidden>{ICON[stage.status]}</span>
            <span className="stage-label">
              {stage.label}
              {stage.visits > 1 && <span className="visits"> ×{stage.visits}</span>}
            </span>
            {stage.detail && <small className="stage-detail">{stage.detail}</small>}
          </li>
        ))}
      </ol>
      {!finished && latest && <p className="hint">{latest}…</p>}
      {job.status === "failed" && <p className="notice error" role="alert">{job.error ?? "The task failed."}</p>}
    </section>
  );
}
