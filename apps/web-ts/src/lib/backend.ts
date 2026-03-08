const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

export interface BackendUserContext {
  employee_id: number;
  name: string;
  email: string;
  role: string;
  direct_reports_count: number;
}

export interface BackendSessionInfo {
  session_id: string;
  user_email: string;
  created_at: string;
  turn_count: number;
  has_pending_confirmation: boolean;
  title?: string | null;
}

export interface BackendEscalation {
  escalation_id: number;
  requester_employee_id: number;
  requester_email: string;
  thread_id: string;
  source_message_excerpt: string;
  status: "PENDING" | "IN_REVIEW" | "RESOLVED";
  created_at: string;
  updated_at: string;
  updated_by_employee_id: number | null;
  resolution_note: string | null;
}

async function apiRequest<T>(
  path: string,
  userEmail: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-User-Email": userEmail,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // ignore parse failures and keep default message
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function fetchCurrentUser(userEmail: string): Promise<BackendUserContext> {
  return apiRequest<BackendUserContext>("/me", userEmail);
}

export async function fetchSessions(userEmail: string): Promise<BackendSessionInfo[]> {
  return apiRequest<BackendSessionInfo[]>("/sessions", userEmail);
}

export async function createSession(userEmail: string): Promise<BackendSessionInfo> {
  return apiRequest<BackendSessionInfo>("/sessions", userEmail, { method: "POST" });
}

export async function deleteSession(
  userEmail: string,
  sessionId: string
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>(`/sessions/${sessionId}`, userEmail, {
    method: "DELETE",
  });
}

export async function sendChat(
  userEmail: string,
  message: string,
  sessionId?: string
): Promise<{ response: string; session_id: string; timestamp: string }> {
  return apiRequest<{ response: string; session_id: string; timestamp: string }>(
    "/chat",
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        message,
        session_id: sessionId ?? null,
      }),
    }
  );
}

export async function fetchEscalations(userEmail: string): Promise<BackendEscalation[]> {
  return apiRequest<BackendEscalation[]>("/escalations", userEmail);
}

export async function createEscalation(
  userEmail: string,
  threadId: string,
  sourceMessageExcerpt: string
): Promise<{ success: boolean; escalation_id?: number; error?: string | null }> {
  return apiRequest<{ success: boolean; escalation_id?: number; error?: string | null }>(
    "/escalations",
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        thread_id: threadId,
        source_message_excerpt: sourceMessageExcerpt,
      }),
    }
  );
}

export async function transitionEscalation(
  userEmail: string,
  escalationId: number,
  nextStatus: "IN_REVIEW" | "RESOLVED",
  resolutionNote?: string
): Promise<{ success: boolean; error?: string | null }> {
  return apiRequest<{ success: boolean; error?: string | null }>(
    `/escalations/${escalationId}/transition`,
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        new_status: nextStatus,
        resolution_note: resolutionNote ?? null,
      }),
    }
  );
}

export { API_BASE_URL };
