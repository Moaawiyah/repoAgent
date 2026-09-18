import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { job, stage } from "../test/fixtures";
import { WorkflowProgress } from "./WorkflowProgress";

afterEach(cleanup);

describe("WorkflowProgress", () => {
  it("renders each backend stage with its status, loop count and detail", () => {
    const stages = [
      stage("repository", "Repository loaded", "done", "acme/shop @ cccccccccccc"),
      stage("analysis", "Static analysis", "done"),
      stage("investigator", "Investigator", "running", "", 2),
      stage("developer", "Developer", "pending", "", 0),
      stage("docker_validation", "Docker validation", "skipped", "", 0),
    ];
    render(<WorkflowProgress job={job("running", "repair", stages)} />);
    expect(screen.getByLabelText("Repository loaded: done")).toBeTruthy();
    expect(screen.getByLabelText("Investigator: in progress").textContent).toContain("●");
    expect(screen.getByLabelText("Investigator: in progress").textContent).toContain("×2");
    expect(screen.getByLabelText("Developer: pending").textContent).toContain("○");
    expect(screen.getByLabelText("Docker validation: skipped")).toBeTruthy();
    expect(screen.getByText("acme/shop @ cccccccccccc")).toBeTruthy();
    expect(screen.getByText("Discovery workflow started…")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows failures without pretending the workflow succeeded", () => {
    render(<WorkflowProgress job={job("failed", "discover", [stage("repository", "Repository loaded", "failed")])} />);
    expect(screen.getByLabelText("Repository loaded: failed").textContent).toContain("✗");
    expect(screen.getByRole("alert").textContent).toContain("Could not fetch the repository");
  });
});
