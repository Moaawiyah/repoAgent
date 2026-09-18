import { useCallback, useEffect, useState } from "react";
import type { Api } from "../api";
import { findNode } from "../graph/relations";
import type { Finding, GraphView, JobRecord, ServerConfig, WorkflowResult } from "../types";
import { DiscoveryResult } from "./DiscoveryResult";
import { GraphExplorer } from "./GraphExplorer";
import { RepairResult } from "./RepairResult";
import { WorkflowProgress } from "./WorkflowProgress";

export const POLL_MS = 1200;

interface Props { taskId: string; api: Api; config: ServerConfig | null; onOpenTask: (id: string) => void }

const TITLE: Record<JobRecord["kind"], string> = {
  repair: "Repair", validated_repair: "Repair + sandbox validation", discover: "Repository audit", investigate: "Investigation",
};

export function TaskPage({ taskId, api, config, onOpenTask }: Props) {
  const [job, setJob] = useState<JobRecord | null>(null);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [graph, setGraph] = useState<GraphView | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [repairing, setRepairing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    setJob(null); setResult(null); setGraph(null); setSelected(null); setError(null);
    async function poll() {
      try {
        const next = await api.job(taskId);
        if (cancelled) return;
        setJob(next);
        if (next.status === "succeeded") {
          const body = await api.result(taskId);
          if (cancelled) return;
          setResult(body.result);
          if (body.result && "workflow" in body.result) {
            api.graph(taskId).then((view) => !cancelled && setGraph(view)).catch((cause) => setGraphError(String(cause.message ?? cause)));
          }
        } else if (next.status !== "failed") {
          timer = window.setTimeout(poll, POLL_MS);
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      }
    }
    poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [taskId, api]);

  const locate = useCallback((symbol: string | null, file?: string) => {
    if (!graph) return;
    const node = findNode(graph, symbol, file);
    if (!node) return;
    setSelected(node.id);
    document.getElementById("graph")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [graph]);

  async function repairFinding(finding: Finding) {
    if (!result || result.workflow !== "discover") return;
    setRepairing(finding.id);
    setError(null);
    try {
      const slug = result.repository.name.toLowerCase();
      const sandbox = !!config && (config.github_execution.includes("*") || config.github_execution.includes(slug));
      const next = await api.repairFinding(taskId, finding.id, sandbox);
      onOpenTask(next.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setRepairing(null);
    }
  }

  if (error && !job) return <p className="notice error" role="alert">{error}</p>;
  if (!job) return <p className="hint">Loading task…</p>;
  const repository = result && "workflow" in result ? result.repository : null;
  return (
    <div className="task">
      <header className="task-head">
        <h1>{TITLE[job.kind]}</h1>
        <p>
          <a href={job.repository.startsWith("https://github.com/") ? job.repository : undefined} target="_blank" rel="noreferrer noopener">{job.repository}</a>
          {repository?.commit && <span className="muted"> @ <code>{repository.commit.slice(0, 12)}</code></span>}
        </p>
      </header>
      <WorkflowProgress job={job} />
      {error && <p className="notice error" role="alert">{error}</p>}
      {result?.workflow === "repair" && <RepairResult result={result} onLocate={locate} />}
      {result?.workflow === "discover" && <DiscoveryResult result={result} onLocate={locate} onRepair={repairFinding} repairing={repairing} />}
      {graph && <GraphExplorer view={graph} selected={selected} onSelect={setSelected} downloadUrl={api.graphDownloadUrl(taskId)} />}
      {graphError && <p className="notice">Graph unavailable: {graphError}</p>}
    </div>
  );
}
