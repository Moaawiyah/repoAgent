import { describe, expect, it } from "vitest";
import { graph } from "../test/fixtures";
import { bounds, layout } from "./layout";
import { findNode, neighborhood, relationsOf } from "./relations";

describe("graph relations", () => {
  it("derives callers, callees, imports and containment from native edges", () => {
    const save = relationsOf(graph, "shop.storage.save");
    expect(save.callers.map((r) => r.node.id)).toEqual(["shop.cart.Cart"]);
    expect(save.callers[0].resolved).toBe(false);
    expect(save.parent?.id).toBe("shop.storage");
    const storage = relationsOf(graph, "shop.storage");
    expect(storage.importedBy.map((r) => r.node.id)).toEqual(["shop.cart"]);
    expect(storage.children.map((r) => r.node.id)).toEqual(["shop.storage.save"]);
    expect(relationsOf(graph, "shop.cart").imports[0].line).toBe(1);
  });

  it("resolves result references to nodes and neighborhoods", () => {
    expect(findNode(graph, "shop.storage.save")?.kind).toBe("function");
    expect(findNode(graph, "save")?.id).toBe("shop.storage.save");
    expect(findNode(graph, null, "shop/cart.py")?.id).toBe("shop.cart");
    expect(findNode(graph, "missing")).toBeNull();
    expect([...neighborhood(graph, "shop.storage")].sort()).toEqual(["shop.cart", "shop.storage", "shop.storage.save"]);
  });

  it("lays out deterministically within finite bounds", () => {
    const first = layout(graph.nodes, graph.edges);
    const second = layout(graph.nodes, graph.edges);
    expect([...first.entries()]).toEqual([...second.entries()]);
    const box = bounds(first.values());
    expect(Number.isFinite(box.w) && box.w >= 100).toBe(true);
    expect(bounds([])).toEqual({ x: 0, y: 0, w: 100, h: 100 });
  });
});
