import { useEffect, useState } from "react";
import { getConfig, getJob, getResult, submitInvestigation, submitRepair } from "./api";
import { RequestForm, type FormValues } from "./components/RequestForm";
import { ResultView } from "./components/ResultView";
import { Timeline } from "./components/Timeline";
import type { JobRecord, JobResult } from "./types";

const POLL_MS = 1500;

export function App() {
  const [executionRepos, setExecutionRepos] = useState<string[]>([]);
  const [job, setJob] = useState<JobRecord | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getConfig().then((c) => setExecutionRepos(c.execution_repositories)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!job || job.status === "succeeded" || job.status === "failed") return;
    const timer = setTimeout(async () => {
      try {
        const next = await getJob(job.id);
        if (next.status === "succeeded" || next.status === "failed") {
          setResult((await getResult(next.id)).result);
        }
        setJob(next);
      } catch (cause) {
        setError(String(cause));
      }
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [job]);

  async function submit(values: FormValues, action: "investigate" | "repair") {
    setError(null);
    setResult(null);
    try {
      const options = { repository: values.repository, issue: values.issue, execute: values.execute };
      setJob(action === "investigate" ? await submitInvestigation(options) : await submitRepair(options));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <main>
      <h1>RepoAgent</h1>
      <RequestForm executionRepos={executionRepos} busy={!!job && !result && job.status !== "failed"} onSubmit={submit} />
      {error && <p className="error">{error}</p>}
      {job && <Timeline job={job} result={result} />}
      {job && result && <ResultView repository={job.repository} result={result} />}
    </main>
  );
}
