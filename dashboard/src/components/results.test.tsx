import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { discovery, repair } from "../test/fixtures";
import type { StaticRepair } from "../types";
import { DiscoveryResult } from "./DiscoveryResult";
import { RepairResult } from "./RepairResult";

afterEach(cleanup);

describe("DiscoveryResult", () => {
  it("summarizes counts and filters finding cards", () => {
    render(<DiscoveryResult result={discovery} onLocate={vi.fn()} onRepair={vi.fn()} repairing={null} />);
    const stats = screen.getByText("Discovery summary").closest("section")!;
    expect(within(stats).getByText("Verified").nextSibling?.textContent).toBe("1");
    expect(screen.getByRole("article", { name: "Potential resource leak" })).toBeTruthy();
    expect(screen.queryByRole("article", { name: "TODO marker" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: /Rejected/ }));
    const rejected = screen.getByRole("article", { name: "TODO marker" });
    expect(within(rejected).queryByRole("button", { name: "Attempt Repair" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: /All/ }));
    expect(screen.getAllByRole("article")).toHaveLength(3);
  });

  it("shows evidence, locates findings in the graph and hands verified ones to repair", () => {
    const onLocate = vi.fn();
    const onRepair = vi.fn();
    render(<DiscoveryResult result={discovery} onLocate={onLocate} onRepair={onRepair} repairing={null} />);
    const card = screen.getByRole("article", { name: "Potential resource leak" });
    expect(within(card).getByText("91%")).toBeTruthy();
    expect(within(card).getByText("shop/storage.py:82")).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: "Evidence" }));
    expect(within(card).getByText("fh = open(path)")).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: "Show in Graph" }));
    expect(onLocate).toHaveBeenCalledWith("shop.storage.save", "shop/storage.py");
    fireEvent.click(within(card).getByRole("button", { name: "Attempt Repair" }));
    expect(onRepair).toHaveBeenCalledWith(discovery.report.candidates[0]);
  });
});

describe("RepairResult", () => {
  it("renders investigation, patch, review, validation comparison and usage", () => {
    const onLocate = vi.fn();
    render(<RepairResult result={repair} onLocate={onLocate} />);
    expect(screen.getByText("Validated")).toBeTruthy();
    expect(screen.getByText(/Discount is applied after rounding/)).toBeTruthy();
    expect(screen.getByLabelText("Unified diff").textContent).toContain("+return round(x - d)");
    expect(screen.getByText("Minimal and correct.")).toBeTruthy();
    const table = screen.getByText("Baseline").closest("table")!;
    expect(within(table).getByText("Failed").parentElement?.textContent).toBe("Failed10");
    expect(within(table).getByText("Ruff").parentElement?.textContent).toBe("Ruffcleanclean");
    expect(screen.getByText(/Fixed failures: tests\/test_cart.py::test_discount/)).toBeTruthy();
    expect(screen.getByText(/LLM calls: 9/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "shop.cart.total" }));
    expect(onLocate).toHaveBeenCalledWith("shop.cart.total");
    fireEvent.click(screen.getByRole("button", { name: "shop/cart.py" }));
    expect(onLocate).toHaveBeenCalledWith(null, "shop/cart.py");
  });

  it("states truthfully when no sandbox validation ran", () => {
    const report = repair.report as { investigation: StaticRepair["investigation"] };
    const staticReport: StaticRepair = {
      status: "review_rejected", investigation: report.investigation, proposal: null, validation: null,
      reviews: [{ decision: "reject", rationale: "Patch changes unrelated code.", concerns: ["scope"] }], revisions: 1, error: null,
    };
    render(<RepairResult result={{ ...repair, sandbox_validation: false, report: staticReport }} onLocate={vi.fn()} />);
    expect(screen.getByText("Review rejected")).toBeTruthy();
    expect(screen.getByText(/never applied or executed/)).toBeTruthy();
    expect(screen.getByText("Patch changes unrelated code.")).toBeTruthy();
  });
});
