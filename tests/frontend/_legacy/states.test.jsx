/**
 * Sprint 18 #88 — reusable state components.
 *
 * LoadingState / EmptyState / ErrorState should be the single source of
 * truth for fallback UI across the dashboard. Specific error copy per
 * HTTP status — never "Something went wrong" (per global taste rules).
 */
import { describe, it, expect, beforeAll, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let LoadingState, EmptyState, ErrorState;

beforeAll(async () => {
  loadFixture();
  ({ LoadingState, EmptyState, ErrorState } = await import("../../public/app.jsx"));
});

describe("LoadingState", () => {
  it("renders default 'Loading…' message", () => {
    render(<LoadingState />);
    expect(screen.getByText(/Loading…/)).toBeInTheDocument();
  });

  it("accepts a custom message", () => {
    render(<LoadingState message="Fetching workflows…" />);
    expect(screen.getByText(/Fetching workflows…/)).toBeInTheDocument();
  });

  it("uses role=status and aria-busy=true for screen readers", () => {
    render(<LoadingState />);
    const region = screen.getByRole("status");
    expect(region.getAttribute("aria-busy")).toBe("true");
    expect(region.getAttribute("aria-live")).toBe("polite");
  });

  it("inline variant adds inline class for compact layout", () => {
    const { container } = render(<LoadingState inline />);
    expect(container.querySelector(".state-loading.inline")).toBeTruthy();
  });
});

describe("EmptyState", () => {
  it("renders title + body", () => {
    render(<EmptyState title="No runs yet" body="Submit one to start." />);
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
    expect(screen.getByText("Submit one to start.")).toBeInTheDocument();
  });

  it("optional action slot renders custom call-to-action", () => {
    render(
      <EmptyState
        title="Empty"
        action={<button>Submit Run</button>}
      />,
    );
    expect(screen.getByRole("button", { name: /Submit Run/i })).toBeInTheDocument();
  });

  it("uses role=status (informational, not interruptive)", () => {
    render(<EmptyState title="x" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("ErrorState — specific copy per HTTP status", () => {
  it("returns null when no error", () => {
    const { container } = render(<ErrorState error={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("401 → 'Session expired' (not retryable)", () => {
    const onRetry = vi.fn();
    render(<ErrorState error={{ status: 401 }} onRetry={onRetry} />);
    expect(screen.getByText(/Session expired/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retry/i })).toBeNull();
  });

  it("403 → 'Session expired' (auth class)", () => {
    render(<ErrorState error={{ status: 403 }} />);
    expect(screen.getByText(/Session expired/i)).toBeInTheDocument();
  });

  it("404 → 'Not found' with body (not retryable)", () => {
    render(<ErrorState error={{ status: 404, message: "Workflow X doesn't exist." }} />);
    expect(screen.getByText(/Not found/i)).toBeInTheDocument();
    expect(screen.getByText(/Workflow X doesn't exist/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retry/i })).toBeNull();
  });

  it("409 → 'Conflict' with backend detail", () => {
    render(<ErrorState error={{ status: 409, message: "Run must be completed first." }} />);
    expect(screen.getByText(/Conflict/i)).toBeInTheDocument();
    expect(screen.getByText(/Run must be completed first/i)).toBeInTheDocument();
  });

  it("5xx → retryable with retry button", () => {
    const onRetry = vi.fn();
    render(<ErrorState error={{ status: 503 }} onRetry={onRetry} />);
    expect(screen.getByText(/Server error 503/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("network error (TypeError or fetch failure) → 'Network error' with retry", () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new TypeError("Failed to fetch")} onRetry={onRetry} />);
    expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });

  it("uses role=alert for assistive interruption on errors", () => {
    render(<ErrorState error={{ status: 500 }} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("No generic 'Something went wrong' copy anywhere", () => {
  it("error copy is always specific (status code or category)", () => {
    // Sample 5 error shapes; none should produce the banned generic copy
    const samples = [
      { status: 401 },
      { status: 404 },
      { status: 500 },
      new TypeError("offline"),
      { status: 418 },  // teapot — falls back to generic "Error" but still has body
    ];
    for (const err of samples) {
      const { container } = render(<ErrorState error={err} />);
      expect(container.textContent).not.toMatch(/Something went wrong/i);
    }
  });
});
