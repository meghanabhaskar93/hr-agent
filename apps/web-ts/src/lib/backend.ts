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
  requester_name?: string | null;
  requester_department?: string | null;
  requester_title?: string | null;
  thread_id: string;
  source_message_excerpt: string;
  status: "PENDING" | "IN_REVIEW" | "RESOLVED";
  created_at: string;
  updated_at: string;
  updated_by_employee_id: number | null;
  resolution_note: string | null;
  priority?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | null;
  category?: string | null;
  assigned_to_employee_id?: number | null;
  assigned_to_email?: string | null;
  assigned_to_name?: string | null;
  agent_suggestion?: string | null;
  last_message_to_requester?: string | null;
  last_message_at?: string | null;
  escalation_level?: number | null;
}

export interface BackendEscalationTimelineEvent {
  event_id: number;
  escalation_id: number;
  event_type: string;
  event_note: string | null;
  actor_employee_id: number | null;
  actor_email: string | null;
  actor_name: string | null;
  metadata_json: string | null;
  created_at: string;
}

export interface BackendEscalationDetail {
  request: BackendEscalation;
  timeline: BackendEscalationTimelineEvent[];
  missing_fields: string[];
  completeness_percent: number;
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
  sourceMessageExcerpt: string,
  options?: {
    priority?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
    category?: string;
    agentSuggestion?: string;
  }
): Promise<{ success: boolean; escalation_id?: number; error?: string | null }> {
  return apiRequest<{ success: boolean; escalation_id?: number; error?: string | null }>(
    "/escalations",
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        thread_id: threadId,
        source_message_excerpt: sourceMessageExcerpt,
        priority: options?.priority ?? "MEDIUM",
        category: options?.category ?? null,
        agent_suggestion: options?.agentSuggestion ?? null,
      }),
    }
  );
}

export async function fetchEscalationDetail(
  userEmail: string,
  escalationId: number
): Promise<BackendEscalationDetail> {
  return apiRequest<BackendEscalationDetail>(
    `/escalations/${escalationId}/detail`,
    userEmail
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

export async function assignEscalation(
  userEmail: string,
  escalationId: number,
  assigneeEmail?: string | null
): Promise<{ success: boolean; error?: string | null }> {
  return apiRequest<{ success: boolean; error?: string | null }>(
    `/escalations/${escalationId}/assign`,
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        assignee_email: assigneeEmail ?? null,
      }),
    }
  );
}

export async function changeEscalationPriority(
  userEmail: string,
  escalationId: number,
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
): Promise<{ success: boolean; error?: string | null }> {
  return apiRequest<{ success: boolean; error?: string | null }>(
    `/escalations/${escalationId}/priority`,
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        priority,
      }),
    }
  );
}

export async function messageEscalationRequester(
  userEmail: string,
  escalationId: number,
  message: string
): Promise<{ success: boolean; error?: string | null }> {
  return apiRequest<{ success: boolean; error?: string | null }>(
    `/escalations/${escalationId}/message`,
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        message,
      }),
    }
  );
}

export async function replyToEscalationAsRequester(
  userEmail: string,
  escalationId: number,
  message: string
): Promise<{ success: boolean; error?: string | null }> {
  return apiRequest<{ success: boolean; error?: string | null }>(
    `/escalations/${escalationId}/requester-reply`,
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        message,
      }),
    }
  );
}

export async function escalateEscalationCase(
  userEmail: string,
  escalationId: number,
  note?: string
): Promise<{ success: boolean; error?: string | null }> {
  return apiRequest<{ success: boolean; error?: string | null }>(
    `/escalations/${escalationId}/escalate`,
    userEmail,
    {
      method: "POST",
      body: JSON.stringify({
        note: note ?? null,
      }),
    }
  );
}

export { API_BASE_URL };
