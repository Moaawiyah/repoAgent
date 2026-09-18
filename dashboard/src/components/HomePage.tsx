import { useState, type FormEvent } from "react";
import type { Operation, ServerConfig } from "../types";
import { checkGithubUrl } from "../validation";

export interface Submission { operation: Operation; url: string; issue: string; sandbox: boolean }

interface Props {
  config: ServerConfig | null;
  busy: boolean;
  error: string | null;
  onSubmit: (submission: Submission) => void;
}

const OPERATIONS: { id: Operation; title: string; blurb: string; icon: string }[] = [
  { id: "repair", title: "Repair Issue", blurb: "Describe a bug; RepoAgent investigates, patches, reviews and validates.", icon: "🛠" },
  { id: "discover", title: "Discover Issues", blurb: "Audit the repository for evidence-backed problems. Nothing is changed.", icon: "🔎" },
];

const MIN_ISSUE = 10;

export function HomePage({ config, busy, error, onSubmit }: Props) {
  const [url, setUrl] = useState("");
  const [touched, setTouched] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [issue, setIssue] = useState("");
  const [sandbox, setSandbox] = useState(false);

  const check = checkGithubUrl(url);
  const sandboxAllowed = check.ok && !!config && (config.github_execution.includes("*") || config.github_execution.includes(check.slug.toLowerCase()));
  const issueOk = issue.trim().length >= MIN_ISSUE;
  const ready = check.ok && operation !== null && (operation === "discover" || issueOk) && !busy;

  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!ready || !check.ok || !operation) return;
    onSubmit({ operation, url: check.url, issue: issue.trim(), sandbox: operation === "repair" && sandbox && sandboxAllowed });
  }

  return (
    <form className="home" onSubmit={submit} noValidate>
      <header className="hero">
        <h1>RepoAgent</h1>
        <p>Evidence-backed repository repair and issue discovery for Python projects.</p>
      </header>

      <section className="card">
        <label htmlFor="repo-url" className="field-label">GitHub Repository</label>
        <input
          id="repo-url"
          className={touched && !check.ok ? "invalid" : ""}
          placeholder="https://github.com/user/repository"
          value={url}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => setUrl(e.target.value)}
          onBlur={() => setTouched(true)}
          aria-invalid={touched && !check.ok}
          aria-describedby="repo-help"
        />
        <p id="repo-help" className={touched && !check.ok ? "hint error-text" : "hint"}>
          {touched && !check.ok ? check.error : "Public repositories are fetched into an isolated workspace; nothing runs on the server host."}
        </p>

        <p className="field-label">Choose operation</p>
        <div className="operations" role="radiogroup" aria-label="Operation">
          {OPERATIONS.map((op) => (
            <button
              key={op.id}
              type="button"
              role="radio"
              aria-checked={operation === op.id}
              className={`operation ${operation === op.id ? "selected" : ""}`}
              onClick={() => setOperation(op.id)}
            >
              <span className="op-icon" aria-hidden>{op.icon}</span>
              <strong>{op.title}</strong>
              <small>{op.blurb}</small>
            </button>
          ))}
        </div>

        {operation === "repair" && (
          <div className="reveal">
            <label htmlFor="issue" className="field-label">Describe the bug/problem</label>
            <textarea
              id="issue"
              rows={6}
              value={issue}
              placeholder="What happens, what should happen, and any error message or failing test…"
              onChange={(e) => setIssue(e.target.value)}
            />
            {touched && !issueOk && <p className="hint error-text">Please describe the problem (at least {MIN_ISSUE} characters).</p>}
            <label className={`checkbox ${sandboxAllowed ? "" : "disabled"}`}>
              <input type="checkbox" checked={sandbox && sandboxAllowed} disabled={!sandboxAllowed} onChange={(e) => setSandbox(e.target.checked)} />
              Validate the patch in the Docker sandbox
              {!sandboxAllowed && <small> — not enabled for this repository by the server operator</small>}
            </label>
          </div>
        )}

        {config && !config.llm_configured && <p className="notice">No LLM provider is configured on the server; workflows will stop at the first LLM step.</p>}
        {error && <p className="notice error" role="alert">{error}</p>}

        {operation && (
          <button type="submit" className="primary" disabled={!ready}>
            {busy ? "Submitting…" : operation === "repair" ? "Analyze & Repair" : "Start Repository Audit"}
          </button>
        )}
      </section>
    </form>
  );
}
