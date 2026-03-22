import type { EscalatedRequest } from "@/components/MyRequestsPanel";
import type { BackendHRRequest } from "@/lib/backend";

interface PanelMappingOptions {
  latestUpdateFallback: string;
  hrMessageLabel: string;
  includeRequesterInSummary?: boolean;
}

function normalizeDate(value: string): Date {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function resolveLatestUpdate(
  request: BackendHRRequest,
  fallback: string
): string {
  if (
    typeof request.last_message_to_requester === "string" &&
    request.last_message_to_requester.trim().length > 0
  ) {
    return request.last_message_to_requester;
  }
  if (
    typeof request.resolution_text === "string" &&
    request.resolution_text.trim().length > 0
  ) {
    return request.resolution_text;
  }
  const suggestion = request.captured_fields?.agent_suggestion;
  if (typeof suggestion === "string" && suggestion.trim().length > 0) {
    return suggestion;
  }
  return fallback;
}

function toPanelPriority(priority: BackendHRRequest["priority"]): EscalatedRequest["priority"] {
  if (priority === "P0") return "critical";
  if (priority === "P1") return "high";
  return "medium";
}

export function toPanelRequestStatus(
  status: BackendHRRequest["status"],
  assigneeUserId?: string | null
): EscalatedRequest["status"] {
  if (status === "RESOLVED" || status === "CANCELLED") return "resolved";
  if (status === "NEEDS_INFO") return "in_review";
  if (status === "IN_PROGRESS" || status === "ESCALATED") return "in_progress";
  if (assigneeUserId) return "assigned";
  return "pending";
}

export function mapHRRequestToPanel(
  request: BackendHRRequest,
  options: PanelMappingOptions
): EscalatedRequest {
  const createdAt = normalizeDate(request.created_at);
  const updatedAt = normalizeDate(request.updated_at);
  const lastMessageAt = request.last_message_at
    ? normalizeDate(request.last_message_at)
    : null;
  const latestUpdate = resolveLatestUpdate(request, options.latestUpdateFallback);

  const auditLog: { label: string; timestamp: Date }[] = [
    { label: "Request created", timestamp: createdAt },
  ];
  if (
    typeof request.last_message_to_requester === "string" &&
    request.last_message_to_requester.trim().length > 0 &&
    lastMessageAt
  ) {
    auditLog.push({
      label: options.hrMessageLabel,
      timestamp: lastMessageAt,
    });
  }
  auditLog.push({
    label: request.status === "RESOLVED" ? "Marked resolved by HR" : "Latest status update",
    timestamp: updatedAt,
  });

  const summaryPrefix = request.requester_name || request.requester_user_id;
  const fullSummary =
    options.includeRequesterInSummary && summaryPrefix
      ? `${summaryPrefix}: ${request.description}`
      : request.description;

  return {
    id: String(request.request_id),
    summary:
      request.summary.length > 60
        ? `${request.summary.slice(0, 60)}...`
        : request.summary,
    fullSummary,
    aiResponse: latestUpdate,
    status: toPanelRequestStatus(request.status, request.assignee_user_id),
    priority: toPanelPriority(request.priority),
    category: `${request.type} / ${request.subtype}`,
    timestamp: createdAt,
    lastUpdatedAt: updatedAt,
    auditLog,
  };
}
