import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { bounds, layout } from "../graph/layout";
import { indexNodes, neighborhood } from "../graph/relations";
import type { GraphEdge, GraphNode, GraphView, NodeKind } from "../types";
import { NodeDetails } from "./NodeDetails";

const KINDS: NodeKind[] = ["module", "class", "function", "method"];
const EDGE_TYPES: GraphEdge["edge_type"][] = ["calls", "imports", "inherits", "defines", "contains"];
const DEFAULT_EDGES = new Set<GraphEdge["edge_type"]>(["calls", "imports", "inherits", "defines"]);

interface Props { view: GraphView; selected: string | null; onSelect: (id: string | null) => void; downloadUrl: string }
interface Camera { x: number; y: number; k: number }

function NodeShape({ node }: { node: GraphNode }) {
  if (node.kind === "module") return <rect x={-14} y={-9} width={28} height={18} rx={5} />;
  if (node.kind === "class") return <polygon points="0,-12 12,0 0,12 -12,0" />;
  return <circle r={node.kind === "function" ? 7 : 5} />;
}

export function GraphExplorer({ view, selected, onSelect, downloadUrl }: Props) {
  const positions = useMemo(() => layout(view.nodes, view.edges), [view]);
  const nodes = useMemo(() => indexNodes(view), [view]);
  const box = useMemo(() => bounds(positions.values()), [positions]);
  const [camera, setCamera] = useState<Camera>({ x: 0, y: 0, k: 1 });
  const [kinds, setKinds] = useState(new Set<NodeKind>(KINDS));
  const [edgeTypes, setEdgeTypes] = useState(DEFAULT_EDGES);
  const [localOnly, setLocalOnly] = useState(false);
  const [query, setQuery] = useState("");
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);

  const near = useMemo(() => (selected ? neighborhood(view, selected) : null), [view, selected]);
  const visible = view.nodes.filter((n) => kinds.has(n.kind) && (!localOnly || !near || near.has(n.id)));
  const shown = new Set(visible.map((n) => n.id));
  const edges = view.edges.filter((e) => edgeTypes.has(e.edge_type) && shown.has(e.source) && shown.has(e.target));

  useEffect(() => {
    const point = selected ? positions.get(selected) : undefined;
    if (!point) return;
    setCamera((c) => ({ k: Math.max(c.k, 1.4), x: box.x + box.w / 2 - point.x, y: box.y + box.h / 2 - point.y }));
  }, [selected, positions, box]);

  const toSvg = (dx: number) => (svg.current ? (dx * box.w) / svg.current.clientWidth : dx);

  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    // Native non-passive listener so zooming does not also scroll the page.
    const wheel = (event: globalThis.WheelEvent) => {
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
      setCamera((c) => ({ ...c, k: Math.min(8, Math.max(0.2, c.k * factor)) }));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);
  function down(event: PointerEvent) { drag.current = { x: event.clientX, y: event.clientY, moved: false }; }
  function move(event: PointerEvent) {
    const start = drag.current;
    if (!start) return;
    const dx = event.clientX - start.x, dy = event.clientY - start.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) start.moved = true;
    start.x = event.clientX; start.y = event.clientY;
    setCamera((c) => ({ ...c, x: c.x + toSvg(dx) / c.k, y: c.y + toSvg(dy) / c.k }));
  }
  function up() { window.setTimeout(() => { drag.current = null; }, 0); }
  function toggle<T>(set: Set<T>, value: T, update: (next: Set<T>) => void) {
    const next = new Set(set);
    if (next.has(value)) next.delete(value); else next.add(value);
    update(next);
  }
  function search() {
    const term = query.trim().toLowerCase();
    const hit = view.nodes.find((n) => n.id.toLowerCase() === term) ?? view.nodes.find((n) => n.id.toLowerCase().includes(term));
    if (hit) onSelect(hit.id);
  }

  const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
  const transform = `translate(${cx} ${cy}) scale(${camera.k}) translate(${-cx + camera.x} ${-cy + camera.y})`;
  const label = (n: GraphNode) => n.id === selected || n.focus || n.kind === "module" || n.kind === "class" || camera.k > 1.8;

  return (
    <section className="card graph-card" id="graph">
      <div className="card-head">
        <h2>Repository graph</h2>
        <a className="button ghost" href={downloadUrl} download="graph.json">Download graph.json</a>
      </div>
      <p className="hint">
        {view.nodes.length} of {view.total_nodes} nodes · {view.edges.length} of {view.total_edges} edges
        {view.truncated && " (large graph: nodes related to this task and higher-level symbols shown first)"}. Scroll to zoom, drag to pan, click a node to inspect.
      </p>
      <div className="graph-toolbar">
        <form onSubmit={(e) => { e.preventDefault(); search(); }} className="graph-search">
          <input aria-label="Find symbol" placeholder="Find symbol…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </form>
        {KINDS.map((kind) => (
          <label key={kind} className={`chip kind-${kind}`}>
            <input type="checkbox" checked={kinds.has(kind)} onChange={() => toggle(kinds, kind, setKinds)} /> {kind}
          </label>
        ))}
        <span className="divider" />
        {EDGE_TYPES.map((type) => (
          <label key={type} className={`chip edge-${type}`}>
            <input type="checkbox" checked={edgeTypes.has(type)} onChange={() => toggle(edgeTypes, type, setEdgeTypes)} /> {type}
          </label>
        ))}
        <label className="chip"><input type="checkbox" checked={localOnly} disabled={!selected} onChange={(e) => setLocalOnly(e.target.checked)} /> neighbors only</label>
        <div className="zoom">
          <button type="button" aria-label="Zoom in" onClick={() => setCamera((c) => ({ ...c, k: Math.min(8, c.k * 1.3) }))}>+</button>
          <button type="button" aria-label="Zoom out" onClick={() => setCamera((c) => ({ ...c, k: Math.max(0.2, c.k / 1.3) }))}>−</button>
          <button type="button" onClick={() => setCamera({ x: 0, y: 0, k: 1 })}>Reset</button>
        </div>
      </div>
      <div className="graph-body">
        <svg
          ref={svg}
          className="graph-canvas"
          viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`}
          role="img"
          aria-label="Interactive repository knowledge graph"
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerLeave={() => { drag.current = null; }}
          onClick={() => { if (!drag.current?.moved) onSelect(null); }}
        >
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="16" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className="arrowhead" />
            </marker>
          </defs>
          <g transform={transform}>
            {edges.map((edge) => {
              const a = positions.get(edge.source)!, b = positions.get(edge.target)!;
              const lit = selected !== null && (edge.source === selected || edge.target === selected);
              return (
                <line
                  key={`${edge.source}>${edge.target}>${edge.edge_type}`}
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  className={`edge edge-${edge.edge_type} ${edge.resolved ? "" : "unresolved"} ${lit ? "lit" : selected ? "dim" : ""}`}
                  markerEnd="url(#arrow)"
                />
              );
            })}
            {visible.map((node) => {
              const p = positions.get(node.id)!;
              const state = node.id === selected ? "selected" : near && !near.has(node.id) ? "dim" : "";
              return (
                <g
                  key={node.id}
                  transform={`translate(${p.x} ${p.y})`}
                  className={`node kind-${node.kind} ${node.focus ? "focus" : ""} ${state}`}
                  onClick={(e) => { e.stopPropagation(); if (!drag.current?.moved) onSelect(node.id); }}
                  role="button"
                  aria-label={`${node.kind} ${node.id}`}
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter") onSelect(node.id); }}
                >
                  <title>{`${node.id}\n${node.file}:${node.start_line}-${node.end_line}`}</title>
                  <NodeShape node={node} />
                  {label(node) && <text y={node.kind === "module" ? 22 : 18}>{node.name}</text>}
                </g>
              );
            })}
          </g>
        </svg>
        <NodeDetails view={view} nodes={nodes} selected={selected} onSelect={onSelect} />
      </div>
    </section>
  );
}
