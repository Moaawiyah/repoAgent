import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

const config = { github_enabled: true, github_execution: ["acme/shop"], llm_configured: true };
afterEach(cleanup);

function setup(props = {}) {
  const onSubmit = vi.fn();
  render(<HomePage config={config} busy={false} error={null} onSubmit={onSubmit} {...props} />);
  const url = screen.getByLabelText("GitHub Repository");
  return { onSubmit, url };
}

describe("HomePage", () => {
  it("offers both operations and hides the issue field until Repair is chosen", () => {
    setup();
    expect(screen.getByRole("radio", { name: /Repair Issue/ })).toBeTruthy();
    expect(screen.getByRole("radio", { name: /Discover Issues/ })).toBeTruthy();
    expect(screen.queryByLabelText("Describe the bug/problem")).toBeNull();
    expect(screen.queryByRole("button", { name: /Analyze|Audit/ })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /Repair Issue/ }));
    expect(screen.getByLabelText("Describe the bug/problem")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Analyze & Repair" })).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: /Discover Issues/ }));
    expect(screen.queryByLabelText("Describe the bug/problem")).toBeNull();
    expect(screen.getByRole("radio", { name: /Discover Issues/ }).getAttribute("aria-checked")).toBe("true");
  });

  it("validates the repository URL before submission", () => {
    const { onSubmit, url } = setup();
    fireEvent.change(url, { target: { value: "https://gitlab.com/o/r" } });
    fireEvent.blur(url);
    expect(screen.getByText("Only https://github.com repositories are supported")).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: /Discover Issues/ }));
    const start = screen.getByRole("button", { name: "Start Repository Audit" }) as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    fireEvent.submit(start.closest("form")!);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a discovery audit without an issue description", () => {
    const { onSubmit, url } = setup();
    fireEvent.change(url, { target: { value: "github.com/acme/shop" } });
    fireEvent.click(screen.getByRole("radio", { name: /Discover Issues/ }));
    fireEvent.click(screen.getByRole("button", { name: "Start Repository Audit" }));
    expect(onSubmit).toHaveBeenCalledWith({ operation: "discover", url: "https://github.com/acme/shop", issue: "", sandbox: false });
  });

  it("requires an issue for repair and only enables the sandbox for allowed repositories", () => {
    const { onSubmit, url } = setup();
    fireEvent.change(url, { target: { value: "https://github.com/other/repo" } });
    fireEvent.click(screen.getByRole("radio", { name: /Repair Issue/ }));
    const sandbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(sandbox.disabled).toBe(true);
    const repair = screen.getByRole("button", { name: "Analyze & Repair" }) as HTMLButtonElement;
    expect(repair.disabled).toBe(true);
    fireEvent.change(url, { target: { value: "https://github.com/acme/shop" } });
    fireEvent.change(screen.getByLabelText("Describe the bug/problem"), { target: { value: "Cart totals ignore discounts" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(repair);
    expect(onSubmit).toHaveBeenCalledWith({ operation: "repair", url: "https://github.com/acme/shop", issue: "Cart totals ignore discounts", sandbox: true });
  });

  it("shows server errors and missing LLM configuration", () => {
    setup({ error: "Docker validation is limited", config: { ...config, llm_configured: false } });
    expect(screen.getByRole("alert").textContent).toContain("Docker validation is limited");
    expect(screen.getByText(/No LLM provider is configured/)).toBeTruthy();
  });
});
