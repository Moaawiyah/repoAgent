import { useEffect, useState } from "react";
import { getGraph, type GraphInspection } from "../api";

// Neighborhood of one symbol from the existing M4 knowledge graph.
export function GraphPanel({ repository, symbol }: { repository: string; symbol: string }) {
  const [graph, setGraph] = useState<GraphInspection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGraph(repository, symbol).then(setGraph).catch((cause) => setError(String(cause)));
  }, [repository, symbol]);

  if (error) return <p className="muted">Graph unavailable: {error}</p>;
  if (!graph) return <p className="muted">Loading graph…</p>;
  return (
    <div className="graph">
      <h3>Graph relationships: {graph.symbol}</h3>
      <ul>
        {graph.incoming.map((e) => <li key={`in-${e.source}-${e.edge_type}`}>{e.source} → <b>{e.edge_type}</b> → this</li>)}
        {graph.outgoing.map((e) => <li key={`out-${e.target}-${e.edge_type}`}>this → <b>{e.edge_type}</b> → {e.target}</li>)}
      </ul>
    </div>
  );
}
