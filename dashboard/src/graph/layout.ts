// Deterministic force-directed layout: same graph → same picture on every load.
import type { GraphEdge, GraphNode } from "../types";

export interface Point { x: number; y: number }

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

export function layout(nodes: GraphNode[], edges: GraphEdge[], size = 1000): Map<string, Point> {
  const modules = [...new Set(nodes.map((n) => n.module))].sort();
  const ring = size * 0.35;
  const pos = new Map<string, Point>();
  nodes.forEach((node) => {
    const m = modules.indexOf(node.module);
    const angle = (2 * Math.PI * m) / Math.max(1, modules.length);
    const jitter = 60 + hash(node.id) * 80;
    const spin = hash(`${node.id}#`) * 2 * Math.PI;
    pos.set(node.id, {
      x: size / 2 + ring * Math.cos(angle) + (node.kind === "module" ? 0 : jitter * Math.cos(spin)),
      y: size / 2 + ring * Math.sin(angle) + (node.kind === "module" ? 0 : jitter * Math.sin(spin)),
    });
  });
  const links = edges.filter((e) => pos.has(e.source) && pos.has(e.target) && e.source !== e.target);
  const ids = nodes.map((n) => n.id);
  const iterations = ids.length > 300 ? 60 : 150;
  const area = size * size;
  const k = Math.sqrt(area / Math.max(1, ids.length)) * 0.6;
  for (let step = 0; step < iterations; step += 1) {
    const temperature = (size / 10) * (1 - step / iterations);
    const shift = new Map<string, Point>(ids.map((id) => [id, { x: 0, y: 0 }]));
    for (let i = 0; i < ids.length; i += 1) {
      const a = pos.get(ids[i])!;
      for (let j = i + 1; j < ids.length; j += 1) {
        const b = pos.get(ids[j])!;
        const dx = a.x - b.x || 0.01;
        const dy = a.y - b.y || 0.01;
        const dist2 = dx * dx + dy * dy;
        if (dist2 > 9 * k * k) continue;
        const force = (k * k) / Math.max(dist2, 1);
        const sa = shift.get(ids[i])!;
        const sb = shift.get(ids[j])!;
        sa.x += dx * force; sa.y += dy * force;
        sb.x -= dx * force; sb.y -= dy * force;
      }
    }
    for (const edge of links) {
      const a = pos.get(edge.source)!;
      const b = pos.get(edge.target)!;
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const force = dist / k;
      const sa = shift.get(edge.source)!;
      const sb = shift.get(edge.target)!;
      sa.x -= (dx / dist) * force * 4; sa.y -= (dy / dist) * force * 4;
      sb.x += (dx / dist) * force * 4; sb.y += (dy / dist) * force * 4;
    }
    for (const id of ids) {
      const p = pos.get(id)!;
      const s = shift.get(id)!;
      const length = Math.sqrt(s.x * s.x + s.y * s.y) || 1;
      const move = Math.min(length, temperature);
      p.x += (s.x / length) * move;
      p.y += (s.y / length) * move;
      p.x += (size / 2 - p.x) * 0.005;
      p.y += (size / 2 - p.y) * 0.005;
    }
  }
  return pos;
}

export function bounds(points: Iterable<Point>, pad = 40): { x: number; y: number; w: number; h: number } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    minX = Math.min(minX, p.x); minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y);
  }
  if (!Number.isFinite(minX)) return { x: 0, y: 0, w: 100, h: 100 };
  return { x: minX - pad, y: minY - pad, w: Math.max(maxX - minX + 2 * pad, 100), h: Math.max(maxY - minY + 2 * pad, 100) };
}
