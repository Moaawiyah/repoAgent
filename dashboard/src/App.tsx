import { useEffect, useState } from "react";
import { api as defaultApi, type Api } from "./api";
import { HomePage, type Submission } from "./components/HomePage";
import { TaskPage } from "./components/TaskPage";
import type { ServerConfig } from "./types";

// Hash routes keep results linkable and refresh-safe without a router dependency.
export function taskFromHash(hash: string): string | null {
  const match = /^#\/tasks\/([0-9a-f]{32})$/.exec(hash);
  return match ? match[1] : null;
}

export function App({ api = defaultApi }: { api?: Api }) {
  const [taskId, setTaskId] = useState<string | null>(() => taskFromHash(window.location.hash));
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then(setConfig).catch(() => setConfig(null));
    const onHash = () => setTaskId(taskFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [api]);

  function open(id: string | null) {
    window.location.hash = id ? `#/tasks/${id}` : "#/";
    setTaskId(id);
  }

  async function submit(submission: Submission) {
    setBusy(true);
    setError(null);
    try {
      const job = submission.operation === "repair"
        ? await api.repair(submission.url, submission.issue, submission.sandbox)
        : await api.discover(submission.url);
      open(job.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <nav className="topbar">
        <button type="button" className="brand" onClick={() => open(null)}>RepoAgent</button>
        {taskId && <button type="button" className="ghost" onClick={() => open(null)}>New task</button>}
      </nav>
      <main>
        {taskId
          ? <TaskPage taskId={taskId} api={api} config={config} onOpenTask={open} />
          : <HomePage config={config} busy={busy} error={error} onSubmit={submit} />}
      </main>
    </>
  );
}
