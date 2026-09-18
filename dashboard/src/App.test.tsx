import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App, taskFromHash } from "./App";
import { NEXT, TASK, fakeApi, job, stage } from "./test/fixtures";

beforeEach(() => { window.location.hash = ""; });
afterEach(cleanup);

describe("App", () => {
  it("routes only well-formed task ids", () => {
    expect(taskFromHash(`#/tasks/${TASK}`)).toBe(TASK);
    expect(taskFromHash("#/tasks/../../etc")).toBeNull();
  });

  it("submits a discovery, shows results and the interactive graph", async () => {
    const api = fakeApi();
    const discover = vi.spyOn(api, "discover");
    render(<App api={api} />);
    fireEvent.change(screen.getByLabelText("GitHub Repository"), { target: { value: "https://github.com/acme/shop" } });
    fireEvent.click(screen.getByRole("radio", { name: /Discover Issues/ }));
    fireEvent.click(screen.getByRole("button", { name: "Start Repository Audit" }));
    await waitFor(() => expect(discover).toHaveBeenCalledWith("https://github.com/acme/shop"));
    expect(window.location.hash).toBe(`#/tasks/${TASK}`);
    await screen.findByText("Discovery summary");
    const canvas = await screen.findByRole("img", { name: "Interactive repository knowledge graph" });
    expect(within(canvas).getByRole("button", { name: "class shop.cart.Cart" })).toBeTruthy();
    const card = screen.getByRole("article", { name: "Potential resource leak" });
    fireEvent.click(within(card).getByRole("button", { name: "Show in Graph" }));
    const details = screen.getByLabelText("Node details");
    expect(within(details).getByText("shop/storage.py")).toBeTruthy();
    expect(within(details).getByText("80–90")).toBeTruthy();
    expect(within(details).getByText("Callers")).toBeTruthy();
    fireEvent.click(within(details).getByRole("button", { name: /shop.cart.Cart/ }));
    expect(within(screen.getByLabelText("Node details")).getByText("Cart")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Download graph.json" }).getAttribute("href")).toContain("format=graph.json");
  });

  it("hands a verified finding to RepairGraph and opens the new task", async () => {
    const api = fakeApi();
    const repairFinding = vi.spyOn(api, "repairFinding");
    window.location.hash = `#/tasks/${TASK}`;
    render(<App api={api} />);
    const card = await screen.findByRole("article", { name: "Potential resource leak" });
    fireEvent.click(within(card).getByRole("button", { name: "Attempt Repair" }));
    await waitFor(() => expect(repairFinding).toHaveBeenCalledWith(TASK, "f1", true));
    await waitFor(() => expect(window.location.hash).toBe(`#/tasks/${NEXT}`));
  });

  it("polls live progress until the task finishes", async () => {
    const running = job("running", "discover", [stage("repository", "Repository loaded", "done"), stage("static_detectors", "Static detectors", "running")]);
    const responses = [running, job("failed", "discover", [stage("repository", "Repository loaded", "failed")])];
    const api = fakeApi({ job: async () => responses.shift() ?? responses[0] });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    window.location.hash = `#/tasks/${TASK}`;
    render(<App api={api} />);
    expect(await screen.findByLabelText("Static detectors: in progress")).toBeTruthy();
    vi.advanceTimersByTime(1500);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByLabelText("Repository loaded: failed")).toBeTruthy();
    vi.useRealTimers();
  });

  it("reports submission errors from the server", async () => {
    const api = fakeApi({ repair: async () => { throw new Error("Docker validation is limited to repositories configured by the server operator"); } });
    render(<App api={api} />);
    fireEvent.change(screen.getByLabelText("GitHub Repository"), { target: { value: "https://github.com/acme/shop" } });
    fireEvent.click(screen.getByRole("radio", { name: /Repair Issue/ }));
    fireEvent.change(screen.getByLabelText("Describe the bug/problem"), { target: { value: "Cart totals ignore discounts" } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze & Repair" }));
    expect((await screen.findByRole("alert")).textContent).toContain("server operator");
    expect(window.location.hash).toBe("");
  });
});
