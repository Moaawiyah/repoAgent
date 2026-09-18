import { useState } from "react";
import { humanize, percent } from "../results";
import type { DiscoveryWorkflowResult, Finding, Verification } from "../types";
import { EvidenceList, type Locate } from "./Evidence";

type Filter = Exclude<Verification, "pending"> | "all";

interface Props {
  result: DiscoveryWorkflowResult;
  onLocate: Locate;
  onRepair: (finding: Finding) => void;
  repairing: string | null;
}

function FindingCard({ finding, onLocate, onRepair, repairing }: { finding: Finding } & Omit<Props, "result">) {
  const [open, setOpen] = useState(false);
  const confidence = finding.verification?.confidence ?? finding.confidence;
  return (
    <article className={`finding ${finding.status}`} aria-label={finding.title}>
      <header>
        <span className={`severity ${finding.severity}`}>{finding.severity.toUpperCase()}</span>
        <h3>{finding.title}</h3>
        <span className={`tag ${finding.status}`}>{finding.status.toUpperCase()}</span>
      </header>
      <p><code>{finding.file}:{finding.start_line}</code>{finding.symbol && <span className="muted"> · {finding.symbol}</span>}</p>
      <p>Confidence: <strong>{percent(confidence)}</strong> <span className="muted">· {humanize(finding.category)} · {finding.detection_source}</span></p>
      <p>{finding.description}</p>
      {finding.verification && <p className="verdict"><strong>Verifier:</strong> {finding.verification.reasoning}</p>}
      {open && (
        <div className="finding-evidence">
          {finding.verification?.supporting_evidence.length ? <p className="hint">Supporting: {finding.verification.supporting_evidence.join("; ")}</p> : null}
          {finding.verification?.contradicting_evidence.length ? <p className="hint">Contradicting: {finding.verification.contradicting_evidence.join("; ")}</p> : null}
          {finding.verification?.recommended_verification && <p className="hint">Suggested check: {finding.verification.recommended_verification}</p>}
          <EvidenceList items={finding.evidence} />
        </div>
      )}
      <div className="actions">
        <button type="button" className="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide evidence" : "Evidence"}</button>
        <button type="button" className="ghost" onClick={() => onLocate(finding.symbol, finding.file)}>Show in Graph</button>
        {finding.status === "verified" && (
          <button type="button" className="primary small" disabled={repairing !== null} onClick={() => onRepair(finding)}>
            {repairing === finding.id ? "Starting repair…" : "Attempt Repair"}
          </button>
        )}
      </div>
    </article>
  );
}

export function DiscoveryResult({ result, onLocate, onRepair, repairing }: Props) {
  const { report } = result;
  const [filter, setFilter] = useState<Filter>(report.metrics.verified > 0 ? "verified" : "all");
  const counts = { verified: report.metrics.verified, uncertain: report.metrics.uncertain, rejected: report.metrics.rejected };
  const shown = report.candidates.filter((c) => filter === "all" || c.status === filter);
  const tabs: Filter[] = ["verified", "uncertain", "rejected", "all"];
  return (
    <>
      <section className="card summary">
        <h2>Discovery summary</h2>
        <div className="stats">
          {(["verified", "uncertain", "rejected"] as const).map((key) => (
            <div key={key} className={`stat ${key}`}><span>{humanize(key)}</span><strong>{counts[key]}</strong></div>
          ))}
        </div>
        <p className="hint">
          {report.files_scanned} files and {report.symbols_scanned} symbols scanned · {report.metrics.candidates_generated} deterministic candidates,
          {" "}{report.metrics.duplicate_findings_removed} duplicates merged · {report.metrics.verification_llm_calls} verifier calls. Nothing was modified.
        </p>
      </section>
      <section className="card">
        <div className="tabs" role="tablist">
          {tabs.map((tab) => (
            <button key={tab} role="tab" type="button" aria-selected={filter === tab} className={filter === tab ? "active" : ""} onClick={() => setFilter(tab)}>
              {humanize(tab)} {tab !== "all" && <span className="count">{counts[tab]}</span>}
            </button>
          ))}
        </div>
        {shown.length === 0 && <p className="muted">No {filter === "all" ? "" : filter} findings.</p>}
        <div className="findings">
          {shown.map((finding) => (
            <FindingCard key={finding.id} finding={finding} onLocate={onLocate} onRepair={onRepair} repairing={repairing} />
          ))}
        </div>
      </section>
    </>
  );
}
