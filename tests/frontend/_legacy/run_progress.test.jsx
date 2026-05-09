/**
 * Sprint 16 #78 — useRunEventStream hook + RunProgress component tests.
 *
 * Mocks EventSource (jsdom has no native EventSource) and asserts:
 * - status transitions on each event
 * - terminal statuses close the stream
 * - reconnect with Last-Event-ID after disconnect
 * - exponential backoff + max retry cap
 * - cleanup on unmount
 * - RunProgress renders pills, elapsed time, reconnect notice, error
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let RunProgress;

beforeAll(async () => {
  loadFixture();
  ({ RunProgress } = await import("../../public/app.jsx"));
});

/* ─── EventSource mock ─────────────────────────────────────────────────── */

class MockEventSource {
  constructor(url) {
    this.url = url;
    this.listeners = new Map();
    this.closed = false;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    MockEventSource.instances.push(this);
  }
  addEventListener(name, cb) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(cb);
  }
  close() {
    this.closed = true;
  }
  // Test helpers
  triggerOpen() {
    if (this.onopen && !this.closed) this.onopen({});
  }
  triggerEvent(eventType, data) {
    if (this.closed) return;
    const event = { data: typeof data === "string" ? data : JSON.stringify(data) };
    if (this.onmessage) this.onmessage(event);
    const named = this.listeners.get(eventType);
    if (named) named.forEach((cb) => cb(event));
  }
  triggerError() {
    if (this.onerror && !this.closed) this.onerror({});
  }
}
MockEventSource.instances = [];

beforeEach(() => {
  MockEventSource.instances = [];
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

/* ─── RunProgress component ────────────────────────────────────────────── */

describe("RunProgress component", () => {
  it("renders nothing without runId or streamToken", () => {
    const { container } = render(<RunProgress runId={null} streamToken={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("opens an EventSource against the SSE endpoint with the stream token", () => {
    render(
      <RunProgress
        runId="RUN-1"
        streamToken="tok-abc"
        eventSourceCtor={MockEventSource}
      />,
    );
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain("/api/runs/RUN-1/events");
    expect(MockEventSource.instances[0].url).toContain("stream_token=tok-abc");
  });

  it("renders the queued pill before any event arrives", () => {
    render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );
    expect(screen.getByText(/queued/i)).toBeInTheDocument();
  });

  it("transitions through analyzing -> completed and shows the pill at each step", () => {
    render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );
    const es = MockEventSource.instances[0];
    act(() => es.triggerOpen());

    act(() => {
      es.triggerEvent("analyzing", { status: "analyzing", sequence: 1 });
    });
    expect(screen.getByText(/analyzing/i)).toBeInTheDocument();

    act(() => {
      es.triggerEvent("completed", { status: "completed", sequence: 2 });
    });
    expect(screen.getByText(/completed/i)).toBeInTheDocument();
    expect(es.closed).toBe(true);
  });

  it("renders failed status with err styling", () => {
    const { container } = render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );
    const es = MockEventSource.instances[0];
    act(() => es.triggerOpen());
    act(() => {
      es.triggerEvent("failed", { status: "failed", sequence: 1 });
    });
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
    expect(container.querySelector(".run-progress-err")).toBeInTheDocument();
  });
});

/* ─── Reconnect behaviour ──────────────────────────────────────────────── */

describe("useRunEventStream reconnect", () => {
  it("reconnects with last_event_id after a disconnect", async () => {
    render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );
    const first = MockEventSource.instances[0];
    act(() => first.triggerOpen());
    act(() => first.triggerEvent("analyzing", { status: "analyzing", sequence: 5 }));

    act(() => first.triggerError());

    await act(async () => {
      vi.advanceTimersByTime(600);
    });

    expect(MockEventSource.instances).toHaveLength(2);
    expect(MockEventSource.instances[1].url).toContain("last_event_id=5");
  });

  it("uses exponential backoff between reconnect attempts", async () => {
    render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );

    // Trigger errors with no successful open between them
    act(() => MockEventSource.instances[0].triggerError());
    await act(async () => vi.advanceTimersByTime(500));
    expect(MockEventSource.instances).toHaveLength(2);

    act(() => MockEventSource.instances[1].triggerError());
    await act(async () => vi.advanceTimersByTime(500));
    expect(MockEventSource.instances).toHaveLength(2); // 500ms < 1000ms backoff
    await act(async () => vi.advanceTimersByTime(500));
    expect(MockEventSource.instances).toHaveLength(3);

    act(() => MockEventSource.instances[2].triggerError());
    await act(async () => vi.advanceTimersByTime(2000));
    expect(MockEventSource.instances).toHaveLength(4);
  });

  it("gives up after SSE_MAX_RECONNECTS attempts and shows error", async () => {
    render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );

    // 5 reconnect cycles (attempts 1..5)
    for (let i = 0; i < 5; i++) {
      act(() => MockEventSource.instances[i].triggerError());
      await act(async () => vi.advanceTimersByTime(60_000));
    }

    expect(MockEventSource.instances).toHaveLength(6);

    // 6th error -> attempt counter is now 5 which >= SSE_MAX_RECONNECTS (5),
    // so the hook stops reconnecting and surfaces the error.
    await act(async () => {
      MockEventSource.instances[5].triggerError();
    });
    expect(screen.getByText(/SSE failed after 5/i)).toBeInTheDocument();
  });
});

/* ─── Cleanup ──────────────────────────────────────────────────────────── */

describe("useRunEventStream cleanup", () => {
  it("closes the EventSource on unmount", () => {
    const { unmount } = render(
      <RunProgress runId="RUN-1" streamToken="tok" eventSourceCtor={MockEventSource} />,
    );
    const es = MockEventSource.instances[0];
    expect(es.closed).toBe(false);
    unmount();
    expect(es.closed).toBe(true);
  });

  it("does not open a new stream when runId or token is null", () => {
    const { rerender } = render(
      <RunProgress runId={null} streamToken="tok" eventSourceCtor={MockEventSource} />,
    );
    expect(MockEventSource.instances).toHaveLength(0);
    rerender(<RunProgress runId="RUN-1" streamToken={null} eventSourceCtor={MockEventSource} />);
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
