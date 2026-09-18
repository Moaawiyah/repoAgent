import { diffLineClass } from "../results";
import type { Evidence } from "../types";

export type Locate = (symbol: string | null, file?: string) => void;

export function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="diff" aria-label="Unified diff">
      {diff.split("\n").map((line, index) => (
        <span key={index} className={diffLineClass(line)}>{line || " "}{"\n"}</span>
      ))}
    </pre>
  );
}

export function EvidenceList({ items, onLocate }: { items: Evidence[]; onLocate?: Locate }) {
  if (items.length === 0) return <p className="hint">No evidence attached.</p>;
  return (
    <ul className="evidence">
      {items.map((item) => (
        <li key={item.evidence_id}>
          <details>
            <summary>
              <code>{item.file_path}:{item.start_line}–{item.end_line}</code> <span className="muted">{item.qualified_name}</span>
              {item.relevance && <span className={`tag ${item.relevance}`}>{item.relevance}</span>}
            </summary>
            {item.reason && <p className="hint">{item.reason}</p>}
            <pre className="snippet">{item.snippet}</pre>
            {item.graph_path.length > 0 && (
              <p className="hint">Graph path: {item.graph_path.map((hop) => `${hop.source_symbol} —${hop.relation}→ ${hop.target_symbol}`).join(" · ")}</p>
            )}
          </details>
          {onLocate && (
            <button type="button" className="link small" onClick={() => onLocate(item.qualified_name, item.file_path)}>Show in graph</button>
          )}
        </li>
      ))}
    </ul>
  );
}
