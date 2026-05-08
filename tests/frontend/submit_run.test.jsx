/**
 * Sprint 16 #77 — Submit Run form tests.
 *
 * Covers: workflow loading, validation, char counters, mode radio,
 * submit success path, and error handling for 4xx and network failures.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let SubmitRun;

beforeAll(async () => {
  loadFixture();
  ({ SubmitRun } = await import("../../public/app.jsx"));
});

const sampleWorkflows = [
  { workflow_id: "WF-001", name: "Literature Review" },
  { workflow_id: "WF-002", name: "Code Audit" },
];

let fetchMock;
beforeEach(() => {
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock;
});
afterEach(() => {
  vi.restoreAllMocks();
});

function mockWorkflowsLoaded(workflows = sampleWorkflows) {
  fetchMock.mockImplementationOnce(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ workflows }),
    }),
  );
}

function mockSubmitResponse({ ok = true, status = 202, body = { run_id: "RUN-NEW", status: "queued" } } = {}) {
  fetchMock.mockImplementationOnce(() =>
    Promise.resolve({
      ok,
      status,
      statusText: ok ? "Accepted" : "Bad Request",
      json: () => Promise.resolve(body),
    }),
  );
}

describe("SubmitRun — workflow loading", () => {
  it("shows loading state then renders workflow picker on success", async () => {
    mockWorkflowsLoaded();
    render(<SubmitRun setScreen={() => {}} />);

    expect(screen.getByText(/Loading workflows/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByLabelText(/Workflow/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("option", { name: /Literature Review/i })).toBeInTheDocument();
  });

  it("renders error state when /api/workflows fails", async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) }),
    );
    render(<SubmitRun setScreen={() => {}} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/Could not load workflows/i)).toBeInTheDocument();
  });

  it("shows empty state when no workflows are registered", async () => {
    mockWorkflowsLoaded([]);
    render(<SubmitRun setScreen={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/No workflows registered/i)).toBeInTheDocument();
    });
  });
});

describe("SubmitRun — validation", () => {
  it("disables submit button until task and research_question are filled", async () => {
    mockWorkflowsLoaded();
    render(<SubmitRun setScreen={() => {}} />);
    await waitFor(() => screen.getByLabelText(/Workflow/i));

    const submitBtn = screen.getByRole("button", { name: /Submit run/i });
    expect(submitBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "Investigate X" } });
    expect(submitBtn).toBeDisabled(); // research question still empty

    fireEvent.change(screen.getByLabelText(/Research Question/i), {
      target: { value: "What is X?" },
    });
    expect(submitBtn).toBeEnabled();
  });

  it("shows live char counter for task field", async () => {
    mockWorkflowsLoaded();
    render(<SubmitRun setScreen={() => {}} />);
    await waitFor(() => screen.getByLabelText(/Workflow/i));

    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "abc" } });
    expect(screen.getByText("3 / 1000")).toBeInTheDocument();
  });
});

describe("SubmitRun — submission", () => {
  it("posts task_spec payload on submit and calls setScreen('trace')", async () => {
    mockWorkflowsLoaded();
    mockSubmitResponse();

    const setScreen = vi.fn();
    const onRunSubmitted = vi.fn();
    render(<SubmitRun setScreen={setScreen} onRunSubmitted={onRunSubmitted} />);

    await waitFor(() => screen.getByLabelText(/Workflow/i));
    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "Investigate X" } });
    fireEvent.change(screen.getByLabelText(/Research Question/i), {
      target: { value: "What is X?" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Submit run/i }));

    await waitFor(() => {
      expect(setScreen).toHaveBeenCalledWith("trace");
    });
    expect(onRunSubmitted).toHaveBeenCalledWith("RUN-NEW");

    // Validate the POST payload
    const postCall = fetchMock.mock.calls[1];
    expect(postCall[0]).toBe("/api/runs");
    const body = JSON.parse(postCall[1].body);
    expect(body).toEqual({
      workflow_id: "WF-001",
      task_spec: { task: "Investigate X", research_question: "What is X?", mode: "stub" },
    });
  });

  it("sends mode='live' when live radio is selected", async () => {
    mockWorkflowsLoaded();
    mockSubmitResponse();
    render(<SubmitRun setScreen={() => {}} />);

    await waitFor(() => screen.getByLabelText(/Workflow/i));
    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText(/Research Question/i), { target: { value: "rq" } });

    const liveRadio = screen.getByRole("radio", { name: /live/i });
    fireEvent.click(liveRadio);

    fireEvent.click(screen.getByRole("button", { name: /Submit run/i }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls[1];
      const body = JSON.parse(postCall[1].body);
      expect(body.task_spec.mode).toBe("live");
    });
  });

  it("surfaces 422 validation errors inline", async () => {
    mockWorkflowsLoaded();
    mockSubmitResponse({
      ok: false,
      status: 422,
      body: { detail: "task_spec.research_question must be non-empty" },
    });

    render(<SubmitRun setScreen={() => {}} />);
    await waitFor(() => screen.getByLabelText(/Workflow/i));
    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText(/Research Question/i), { target: { value: "rq" } });

    fireEvent.click(screen.getByRole("button", { name: /Submit run/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/task_spec.research_question must be non-empty/i)).toBeInTheDocument();
  });

  it("surfaces 404 unknown-workflow error specifically", async () => {
    mockWorkflowsLoaded();
    mockSubmitResponse({ ok: false, status: 404, body: { detail: "workflow not found" } });

    render(<SubmitRun setScreen={() => {}} />);
    await waitFor(() => screen.getByLabelText(/Workflow/i));
    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText(/Research Question/i), { target: { value: "rq" } });
    fireEvent.click(screen.getByRole("button", { name: /Submit run/i }));

    await waitFor(() => {
      expect(screen.getByText(/Refresh the workflow list/i)).toBeInTheDocument();
    });
  });

  it("surfaces network failures with a retryable message", async () => {
    mockWorkflowsLoaded();
    fetchMock.mockImplementationOnce(() => Promise.reject(new Error("offline")));

    render(<SubmitRun setScreen={() => {}} />);
    await waitFor(() => screen.getByLabelText(/Workflow/i));
    fireEvent.change(screen.getByLabelText(/^Task$/i), { target: { value: "t" } });
    fireEvent.change(screen.getByLabelText(/Research Question/i), { target: { value: "rq" } });
    fireEvent.click(screen.getByRole("button", { name: /Submit run/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });
});
