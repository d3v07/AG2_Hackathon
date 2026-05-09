/**
 * Sprint 16 #80 — WorkflowsScreen tests.
 *
 * Covers loading / loaded / error / empty states for both list and detail,
 * pick-workflow callback, and Submit Run button navigation.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let WorkflowsScreen;

beforeAll(async () => {
  loadFixture();
  ({ WorkflowsScreen } = await import("../../public/app.jsx"));
});

let fetchMock;
beforeEach(() => {
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock;
});
afterEach(() => {
  vi.restoreAllMocks();
});

const sampleList = [
  { workflow_id: "WF-001", name: "Literature Review", agents: [{ name: "Researcher" }, { name: "Critic" }], contracts: [{ id: "C-EVD" }], owner: "d3v07" },
  { workflow_id: "WF-002", name: "Code Audit", agents: [{ name: "Auditor" }], contracts: [], owner: "d3v07" },
];
const sampleDetail = {
  workflow_id: "WF-001",
  name: "Literature Review",
  declared_topology: { entry: "Researcher", edges: [["Researcher", "Critic"]] },
  agents: [{ name: "Researcher" }, { name: "Critic" }],
  contracts: [{ id: "C-EVD", type: "evidence", rule: "verified_sources_count > 0" }],
  owner: "d3v07",
};

function mockListLoaded(list = sampleList) {
  fetchMock.mockImplementationOnce(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ workflows: list }) }),
  );
}

function mockDetailLoaded(detail = sampleDetail) {
  fetchMock.mockImplementationOnce(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(detail) }),
  );
}

/* ─── List states ──────────────────────────────────────────────────────── */

describe("WorkflowsScreen — list states", () => {
  it("shows loading state", () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {})); // never resolves
    render(<WorkflowsScreen setScreen={() => {}} />);
    expect(screen.getByText(/Loading workflows/i)).toBeInTheDocument();
  });

  it("renders the list when workflows are loaded", async () => {
    mockListLoaded();
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/Literature Review/i)).toBeInTheDocument();
      expect(screen.getByText(/Code Audit/i)).toBeInTheDocument();
    });
  });

  it("shows agent and contract counts on each row", async () => {
    mockListLoaded();
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => screen.getByText(/Literature Review/i));
    expect(screen.getByText(/2 agents.*1 contract/i)).toBeInTheDocument();
    expect(screen.getByText(/1 agent.*0 contracts/i)).toBeInTheDocument();
  });

  it("shows error state when /api/workflows fails", async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) }),
    );
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/Could not load workflows/i)).toBeInTheDocument();
    });
  });

  it("shows empty state when no workflows are registered", async () => {
    mockListLoaded([]);
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/No workflows registered yet/i)).toBeInTheDocument();
    });
  });
});

/* ─── Detail states ────────────────────────────────────────────────────── */

describe("WorkflowsScreen — detail states", () => {
  it("shows 'Pick a workflow' empty state on initial render", async () => {
    mockListLoaded();
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => screen.getByText(/Literature Review/i));
    expect(screen.getByText(/Pick a workflow on the left/i)).toBeInTheDocument();
  });

  it("loads detail when a row is clicked", async () => {
    mockListLoaded();
    mockDetailLoaded();
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => screen.getByText(/Literature Review/i));

    fireEvent.click(screen.getByText(/Literature Review/i));

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 3, name: /Literature Review/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { level: 4, name: /Topology/i })).toBeInTheDocument();
    expect(screen.getByText(/C-EVD/)).toBeInTheDocument();
    expect(screen.getByText(/verified_sources_count > 0/)).toBeInTheDocument();
  });

  it("shows 404 detail error specifically", async () => {
    mockListLoaded();
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) }),
    );
    render(<WorkflowsScreen setScreen={() => {}} />);
    await waitFor(() => screen.getByText(/Literature Review/i));

    fireEvent.click(screen.getByText(/Literature Review/i));

    await waitFor(() => {
      expect(screen.getByText(/doesn't exist or was deleted/i)).toBeInTheDocument();
    });
  });
});

/* ─── Submit Run navigation ────────────────────────────────────────────── */

describe("WorkflowsScreen — Submit Run flow", () => {
  it("calls onPickWorkflow + setScreen('submit') when SUBMIT RUN is clicked", async () => {
    mockListLoaded();
    mockDetailLoaded();

    const setScreen = vi.fn();
    const onPickWorkflow = vi.fn();
    render(<WorkflowsScreen setScreen={setScreen} onPickWorkflow={onPickWorkflow} />);

    await waitFor(() => screen.getByText(/Literature Review/i));
    fireEvent.click(screen.getByText(/Literature Review/i));

    await waitFor(() =>
      screen.getByRole("button", { name: /SUBMIT RUN AGAINST THIS WORKFLOW/i }),
    );

    fireEvent.click(screen.getByRole("button", { name: /SUBMIT RUN AGAINST THIS WORKFLOW/i }));

    expect(onPickWorkflow).toHaveBeenCalledWith(sampleDetail);
    expect(setScreen).toHaveBeenCalledWith("submit");
  });

  it("empty state offers a link to Submit Run", async () => {
    mockListLoaded([]);
    const setScreen = vi.fn();
    render(<WorkflowsScreen setScreen={setScreen} />);

    await waitFor(() => screen.getByText(/No workflows registered/i));
    fireEvent.click(screen.getByRole("button", { name: /Submit Run/i }));
    expect(setScreen).toHaveBeenCalledWith("submit");
  });
});
