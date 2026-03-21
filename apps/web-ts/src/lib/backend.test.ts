import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

type BackendModule = typeof import("@/lib/backend");

const fetchMock = vi.hoisted(() => vi.fn());

vi.stubGlobal("fetch", fetchMock);

async function loadBackend() {
  vi.resetModules();
  return (await import("@/lib/backend")) as BackendModule;
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.unstubAllEnvs();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("backend client", () => {
  it("sends JSON bodies and required headers for chat requests", async () => {
    const backend = await loadBackend();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        response: "Hello there",
        session_id: "session-1",
        timestamp: "2026-03-21T12:00:00Z",
      }),
    });

    const result = await backend.sendChat("alex.kim@acme.com", "What is my PTO?", "session-1");

    expect(result.response).toBe("Hello there");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Email": "alex.kim@acme.com",
        },
        body: JSON.stringify({
          message: "What is my PTO?",
          session_id: "session-1",
        }),
      })
    );
  });

  it("reads payload.detail on non-ok responses and falls back to status text", async () => {
    const backend = await loadBackend();

    fetchMock
      .mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Permission denied" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("bad json");
        },
      });

    await expect(backend.fetchCurrentUser("alex.kim@acme.com")).rejects.toThrow(
      "Permission denied"
    );
    await expect(backend.fetchSessions("alex.kim@acme.com")).rejects.toThrow(
      "Request failed (500)"
    );
  });

  it("uses the configured base URL and strips trailing slashes", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com///");
    const backend = await loadBackend();

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        employee_id: 7,
        name: "Jordan Lee",
        email: "jordan.lee@acme.com",
        role: "HR",
        direct_reports_count: 4,
      }),
    });

    const result = await backend.fetchCurrentUser("jordan.lee@acme.com");

    expect(result.role).toBe("HR");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/me",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-User-Email": "jordan.lee@acme.com",
        }),
      })
    );
  });

  it("passes through method-specific requests without a body for GETs", async () => {
    const backend = await loadBackend();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    await backend.fetchSessions("alex.kim@acme.com");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/sessions",
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          "X-User-Email": "alex.kim@acme.com",
        },
      })
    );
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty("body");
  });

  it("fills in createEscalation defaults when options are omitted", async () => {
    const backend = await loadBackend();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, escalation_id: 42, error: null }),
    });

    await backend.createEscalation("alex.kim@acme.com", "thread-1", "excerpt");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/escalations",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-User-Email": "alex.kim@acme.com",
        }),
        body: JSON.stringify({
          thread_id: "thread-1",
          source_message_excerpt: "excerpt",
          priority: "MEDIUM",
          category: null,
          agent_suggestion: null,
        }),
      })
    );
  });
});
