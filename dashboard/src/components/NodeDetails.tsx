import { useMemo } from "react";
import { relationsOf, type Related } from "../graph/relations";
import type { GraphNode, GraphView } from "../types";

interface Props { view: GraphView; nodes: Map<string, GraphNode>; selected: string | null; onSelect: (id: string) => void }

function Group({ title, items, onSelect }: { title: string; items: Related[]; onSelect: (id: string) => void }) {
  if (items.length === 0) return null;
  return (
    <div className="relation">
      <h4>{title} <span className="count">{items.length}</span></h4>
      <ul>
        {items.map(({ node, resolved, line }) => (
          <li key={node.id}>
            <button type="button" className="link" onClick={() => onSelect(node.id)}>
              <span className={`dot kind-${node.kind}`} aria-hidden />
              {node.id}
            </button>
            {line !== null && <small> line {line}</small>}
            {!resolved && <small className="warn"> (ambiguous)</small>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NodeDetails({ view, nodes, selected, onSelect }: Props) {
  const node = selected ? nodes.get(selected) : undefined;
  const relations = useMemo(() => (node ? relationsOf(view, node.id, nodes) : null), [view, node, nodes]);
  if (!node || !relations) {
    return (
      <aside className="node-details empty">
        <p>Select a node to see its source location, callers, callees, imports and inheritance.</p>
        <ul className="legend">
          <li><span className="dot kind-module" /> module</li>
          <li><span className="dot kind-class" /> class</li>
          <li><span className="dot kind-function" /> function</li>
          <li><span className="dot kind-method" /> method</li>
          <li><span className="dot focus-ring" /> referenced by this task</li>
        </ul>
      </aside>
    );
  }
  return (
    <aside className="node-details" aria-label="Node details">
      <span className={`badge kind-${node.kind}`}>{node.kind}</span>
      <h3>{node.name}</h3>
      <code className="qualified">{node.id}</code>
      <dl>
        <dt>Source</dt>
        <dd><code>{node.file}</code></dd>
        <dt>Lines</dt>
        <dd>{node.start_line}–{node.end_line}</dd>
        {relations.parent && (
          <>
            <dt>Defined in</dt>
            <dd><button type="button" className="link" onClick={() => onSelect(relations.parent!.id)}>{relations.parent.id}</button></dd>
          </>
        )}
      </dl>
      <Group title="Callers" items={relations.callers} onSelect={onSelect} />
      <Group title="Callees" items={relations.callees} onSelect={onSelect} />
      <Group title="Imports" items={relations.imports} onSelect={onSelect} />
      <Group title="Imported by" items={relations.importedBy} onSelect={onSelect} />
      <Group title="Inherits from" items={relations.bases} onSelect={onSelect} />
      <Group title="Subclasses" items={relations.subclasses} onSelect={onSelect} />
      <Group title="Contains" items={relations.children} onSelect={onSelect} />
    </aside>
  );
}
