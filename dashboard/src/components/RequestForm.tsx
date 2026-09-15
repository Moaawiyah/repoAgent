import { useState } from "react";

export interface FormValues { repository: string; issue: string; execute: boolean }

interface Props {
  executionRepos: string[];
  busy: boolean;
  onSubmit: (values: FormValues, action: "investigate" | "repair") => void;
}

export function RequestForm({ executionRepos, busy, onSubmit }: Props) {
  const [values, setValues] = useState<FormValues>({ repository: "", issue: "", execute: false });
  const canExecute = executionRepos.includes(values.repository);
  const ready = values.repository.trim() !== "" && values.issue.trim() !== "" && !busy;

  return (
    <form className="panel" onSubmit={(event) => event.preventDefault()}>
      <label>
        Repository (local path under an allowed root)
        <input
          list="demo-repos"
          value={values.repository}
          onChange={(e) => setValues({ ...values, repository: e.target.value })}
        />
        <datalist id="demo-repos">
          {executionRepos.map((repo) => <option key={repo} value={repo} />)}
        </datalist>
      </label>
      <label>
        Issue
        <textarea rows={3} value={values.issue} onChange={(e) => setValues({ ...values, issue: e.target.value })} />
      </label>
      <label className="inline">
        <input
          type="checkbox"
          checked={values.execute && canExecute}
          disabled={!canExecute}
          onChange={(e) => setValues({ ...values, execute: e.target.checked })}
        />
        Validate in Docker sandbox (demo repositories only)
      </label>
      <div className="actions">
        <button type="button" disabled={!ready} onClick={() => onSubmit(values, "investigate")}>Investigate</button>
        <button type="button" disabled={!ready} onClick={() => onSubmit({ ...values, execute: values.execute && canExecute }, "repair")}>Repair</button>
      </div>
    </form>
  );
}
