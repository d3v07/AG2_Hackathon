/**
 * Sprint 16 #79 — ApprovalPanel + Report screen tests.
 *
 * Covers each approval state (pending / approved / rejected),
 * approve & reject POST flows, and error paths (404, 409, network).
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let ApprovalPanel, Report;

beforeAll(async () => {
  loadFixture();
  ({ ApprovalPanel, Report } = await import("../../public/app.jsx"));
});

let fetchMock;
beforeEach(() => {
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock;
});
afterEach(() => {
  vi.restoreAllMocks();
});

const pendingApproval = {
  status: "PENDING_OPERATOR",
  operator: "j.kowalski",
  requested_at: "2026-05-08T17:00:00Z",
  sla: "4h",
};
const approvedApproval = {
  status: "APPROVED",
  operator: "j.kowalski",
  requested_at: "2026-05-08T17:00:00Z",
  sla: "4h",
  comments: "All verified.",
};
const rejectedApproval = {
  status: "REJECTED",
  operator: "j.kowalski",
  requested_at: "2026-05-08T17:00:00Z",
  sla: "4h",
  comments: "Sources insufficient.",
};

/* ─── Render states ────────────────────────────────────────────────────── */

describe("ApprovalPanel — render states", () => {
  it("PENDING shows approve/reject form", () => {
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} />);
    expect(screen.getByText(/PENDING OPERATOR/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /APPROVE/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /REJECT/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Operator/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Comments/i)).toBeInTheDocument();
  });

  it("APPROVED hides the form and shows comments", () => {
    render(<ApprovalPanel runId="RUN-1" approval={approvedApproval} />);
    expect(screen.getByText(/^APPROVED$/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /APPROVE/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /REJECT/i })).toBeNull();
    expect(screen.getByText(/All verified/i)).toBeInTheDocument();
  });

  it("REJECTED hides the form and shows rejection comments", () => {
    render(<ApprovalPanel runId="RUN-1" approval={rejectedApproval} />);
    expect(screen.getByText(/^REJECTED$/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /APPROVE/i })).toBeNull();
    expect(screen.getByText(/Sources insufficient/i)).toBeInTheDocument();
  });

  it("operator field defaults to j.kowalski but is editable", () => {
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} />);
    const op = screen.getByLabelText(/Operator/i);
    expect(op.value).toBe("j.kowalski");
    fireEvent.change(op, { target: { value: "alice" } });
    expect(op.value).toBe("alice");
  });
});

/* ─── Approve POST flow ────────────────────────────────────────────────── */

describe("ApprovalPanel — approve flow", () => {
  it("posts decision=approved with operator and comments", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ run_id: "RUN-1", approval: { ...pendingApproval, status: "APPROVED" } }),
    });

    const onUpdated = vi.fn();
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} onUpdated={onUpdated} />);

    fireEvent.change(screen.getByLabelText(/Comments/i), { target: { value: "Looks good" } });
    fireEvent.click(screen.getByRole("button", { name: /APPROVE/i }));

    await waitFor(() => {
      expect(onUpdated).toHaveBeenCalled();
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/runs/RUN-1/approval");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body).toEqual({ decision: "approved", operator: "j.kowalski", comments: "Looks good" });
  });

  it("posts decision=rejected when reject is clicked", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ run_id: "RUN-1", approval: { ...pendingApproval, status: "REJECTED" } }),
    });

    const onUpdated = vi.fn();
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} onUpdated={onUpdated} />);

    fireEvent.click(screen.getByRole("button", { name: /REJECT/i }));

    await waitFor(() => expect(onUpdated).toHaveBeenCalled());
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.decision).toBe("rejected");
  });

  it("disables both buttons while submitting", async () => {
    let resolvePost;
    fetchMock.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolvePost = () => resolve({
          ok: true, status: 200, json: () => Promise.resolve({ approval: pendingApproval }),
        });
      }),
    );
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} />);

    const approveBtn = screen.getByRole("button", { name: /APPROVE/i });
    const rejectBtn = screen.getByRole("button", { name: /REJECT/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(approveBtn).toBeDisabled();
      expect(rejectBtn).toBeDisabled();
    });
    expect(approveBtn.getAttribute("aria-busy")).toBe("true");
    resolvePost();
  });
});

/* ─── Error paths ──────────────────────────────────────────────────────── */

describe("ApprovalPanel — error states", () => {
  it("shows 404 with specific message", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false, status: 404, json: () => Promise.resolve({ detail: "run not found" }),
    });
    render(<ApprovalPanel runId="MISSING" approval={pendingApproval} />);
    fireEvent.click(screen.getByRole("button", { name: /APPROVE/i }));

    await waitFor(() => {
      expect(screen.getByText(/Run MISSING not found/i)).toBeInTheDocument();
    });
  });

  it("shows 409 with backend detail", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      statusText: "Conflict",
      json: () => Promise.resolve({ detail: "run must be completed before approval" }),
    });
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} />);
    fireEvent.click(screen.getByRole("button", { name: /APPROVE/i }));

    await waitFor(() => {
      expect(screen.getByText(/run must be completed before approval/i)).toBeInTheDocument();
    });
  });

  it("shows network error with retry button", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    render(<ApprovalPanel runId="RUN-1" approval={pendingApproval} />);
    fireEvent.click(screen.getByRole("button", { name: /APPROVE/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
    const dismiss = screen.getByRole("button", { name: /dismiss/i });
    fireEvent.click(dismiss);
    await waitFor(() => {
      expect(screen.queryByText(/Network error/i)).toBeNull();
    });
  });

  it("blocks submission when no runId is set", async () => {
    render(<ApprovalPanel runId={null} approval={pendingApproval} />);
    fireEvent.click(screen.getByRole("button", { name: /APPROVE/i }));
    await waitFor(() => {
      expect(screen.getByText(/No run_id available/i)).toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

/* ─── Report screen integration ────────────────────────────────────────── */

describe("Report screen with ApprovalPanel", () => {
  it("renders approval panel inside the Report screen", () => {
    render(<Report setScreen={() => {}} runId="RUN-1" />);
    // Default fixture approval is PENDING_OPERATOR — multiple status nodes
    // may exist (pill + KV row), so accept any match.
    expect(screen.getAllByText(/PENDING OPERATOR/i).length).toBeGreaterThan(0);
  });

  it("refreshes approval state after a successful approve", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        run_id: "RUN-1",
        approval: { status: "APPROVED", operator: "j.kowalski", comments: "ok" },
      }),
    });
    render(<Report setScreen={() => {}} runId="RUN-1" />);

    fireEvent.click(screen.getByRole("button", { name: /APPROVE/i }));

    await waitFor(() => {
      expect(screen.getByText(/^APPROVED$/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /APPROVE/i })).toBeNull();
  });
});
