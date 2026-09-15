import { buildTimeline, finalStatus } from "../timeline";
import type { JobRecord, JobResult } from "../types";

const ICON = { done: "✓", failed: "✗", running: "…", pending: "·" } as const;

export function Timeline({ job, result }: { job: JobRecord; result: JobResult | null }) {
  const steps = buildTimeline(job, result);
  return (
    <section className="panel">
      <h2>Progress</h2>
      <ol className="timeline">
        {steps.map((step, index) => (
          <li key={`${step.label}-${index}`} className={step.state}>
            <span className="icon">{ICON[step.state]}</span>
            <span>{step.label}</span>
            {step.detail && <small>{step.detail}</small>}
          </li>
        ))}
      </ol>
      <p className="status">Result: <strong>{finalStatus(job, result)}</strong></p>
    </section>
  );
}
