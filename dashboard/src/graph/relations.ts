// Relationship lookups over the native RepositoryGraph view (no new graph model).
import type { GraphEdge, GraphNode, GraphView } from "../types";

export interface Related { node: GraphNode; resolved: boolean; line: number | null }

export interface Relations {
  parent: GraphNode | null;
  children: Related[];
  callers: Related[];
  callees: Related[];
  imports: Related[];
  importedBy: Related[];
  bases: Related[];
  subclasses: Related[];
}

export function indexNodes(view: GraphView): Map<string, GraphNode> {
  return new Map(view.nodes.map((node) => [node.id, node]));
}

export function relationsOf(view: GraphView, id: string, nodes = indexNodes(view)): Relations {
  const pick = (edges: GraphEdge[], end: "source" | "target"): Related[] =>
    edges
      .map((edge) => ({ node: nodes.get(edge[end]), resolved: edge.resolved, line: edge.line }))
      .filter((item): item is Related => !!item.node)
      .sort((a, b) => a.node.id.localeCompare(b.node.id));
  const out = (type: GraphEdge["edge_type"]) => view.edges.filter((e) => e.source === id && e.edge_type === type);
  const inn = (type: GraphEdge["edge_type"]) => view.edges.filter((e) => e.target === id && e.edge_type === type);
  const node = nodes.get(id);
  return {
    parent: node?.parent ? nodes.get(node.parent) ?? null : null,
    children: pick([...out("defines"), ...out("contains")], "target"),
    callers: pick(inn("calls"), "source"),
    callees: pick(out("calls"), "target"),
    imports: pick(out("imports"), "target"),
    importedBy: pick(inn("imports"), "source"),
    bases: pick(out("inherits"), "target"),
    subclasses: pick(inn("inherits"), "source"),
  };
}

/** Resolve a result reference (qualified symbol or file path) to a graph node. */
export function findNode(view: GraphView, symbol: string | null, file?: string): GraphNode | null {
  if (symbol) {
    const exact = view.nodes.find((n) => n.id === symbol);
    if (exact) return exact;
    const suffix = view.nodes.find((n) => n.id.endsWith(`.${symbol}`));
    if (suffix) return suffix;
  }
  if (file) return view.nodes.find((n) => n.kind === "module" && n.file === file) ?? view.nodes.find((n) => n.file === file) ?? null;
  return null;
}

/** Node ids within one hop of ``id`` (used for the neighborhood filter). */
export function neighborhood(view: GraphView, id: string): Set<string> {
  const ids = new Set([id]);
  for (const edge of view.edges) {
    if (edge.source === id) ids.add(edge.target);
    if (edge.target === id) ids.add(edge.source);
  }
  return ids;
}
