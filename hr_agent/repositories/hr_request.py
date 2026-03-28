"""
HR Request Repository - Unified HR request workflow data access.
"""

from datetime import datetime
import json
from typing import Any

from sqlalchemy import text

from .base import BaseRepository


class HRRequestRepository(BaseRepository):
    """Repository for canonical HR request and event data."""

    @staticmethod
    def _json_dumps(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def _json_loads(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["required_fields"] = self._json_loads(
            result.pop("required_fields_json", None), []
        )
        result["captured_fields"] = self._json_loads(
            result.pop("captured_fields_json", None), {}
        )
        result["missing_fields"] = self._json_loads(
            result.pop("missing_fields_json", None), []
        )
        result["resolution_sources"] = self._json_loads(
            result.pop("resolution_sources_json", None), []
        )
        return result

    def _deserialize_event(self, row: dict) -> dict:
        result = dict(row)
        result["payload"] = self._json_loads(result.pop("payload_json", None), {})
        return result

    def _insert_event_in_connection(
        self,
        con,
        request_id: int,
        tenant_id: str,
        event_type: str,
        actor_user_id: str | None,
        actor_role: str | None,
        event_note: str | None = None,
        payload: dict | None = None,
        created_at: str | None = None,
    ) -> None:
        """Insert one append-only request event in the current transaction."""
        con.execute(
            text(
                """INSERT INTO hr_request_event
                   (
                     request_id,
                     tenant_id,
                     event_type,
                     event_note,
                     actor_user_id,
                     actor_role,
                     payload_json,
                     created_at
                   )
                   VALUES
                   (
                     :request_id,
                     :tenant_id,
                     :event_type,
                     :event_note,
                     :actor_user_id,
                     :actor_role,
                     :payload_json,
                     :created_at
                   )"""
            ),
            {
                "request_id": request_id,
                "tenant_id": tenant_id,
                "event_type": event_type,
                "event_note": event_note,
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "payload_json": self._json_dumps(payload),
                "created_at": created_at or datetime.now().isoformat(),
            },
        )

    def create_with_event(
        self,
        tenant_id: str,
        requester_user_id: str,
        requester_role: str,
        subject_employee_id: int | None,
        request_type: str,
        request_subtype: str,
        summary: str,
        description: str,
        priority: str,
        risk_level: str,
        sla_due_at: str | None,
        status: str,
        assignee_user_id: str | None,
        required_fields: list[str],
        captured_fields: dict[str, Any],
        missing_fields: list[str],
        resolution_text: str | None = None,
        resolution_sources: list[str] | None = None,
        escalation_ticket_id: str | None = None,
        event_type: str = "CREATED",
        event_note: str = "HR request created.",
        actor_user_id: str | None = None,
        actor_role: str | None = None,
        event_payload: dict | None = None,
    ) -> int:
        """Create HR request and initial event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            con.execute(
                text(
                    """INSERT INTO hr_request
                       (
                         tenant_id,
                         requester_user_id,
                         requester_role,
                         subject_employee_id,
                         type,
                         subtype,
                         summary,
                         description,
                         priority,
                         risk_level,
                         sla_due_at,
                         status,
                         assignee_user_id,
                         required_fields_json,
                         captured_fields_json,
                         missing_fields_json,
                         created_at,
                         updated_at,
                         last_action_at,
                         resolution_text,
                         resolution_sources_json,
                         escalation_ticket_id,
                         last_message_to_requester,
                         last_message_at
                       )
                       VALUES
                       (
                         :tenant_id,
                         :requester_user_id,
                         :requester_role,
                         :subject_employee_id,
                         :type,
                         :subtype,
                         :summary,
                         :description,
                         :priority,
                         :risk_level,
                         :sla_due_at,
                         :status,
                         :assignee_user_id,
                         :required_fields_json,
                         :captured_fields_json,
                         :missing_fields_json,
                         :created_at,
                         :updated_at,
                         :last_action_at,
                         :resolution_text,
                         :resolution_sources_json,
                         :escalation_ticket_id,
                         NULL,
                         NULL
                       )"""
                ),
                {
                    "tenant_id": tenant_id,
                    "requester_user_id": requester_user_id,
                    "requester_role": requester_role,
                    "subject_employee_id": subject_employee_id,
                    "type": request_type,
                    "subtype": request_subtype,
                    "summary": summary,
                    "description": description,
                    "priority": priority,
                    "risk_level": risk_level,
                    "sla_due_at": sla_due_at,
                    "status": status,
                    "assignee_user_id": assignee_user_id,
                    "required_fields_json": self._json_dumps(required_fields) or "[]",
                    "captured_fields_json": self._json_dumps(captured_fields) or "{}",
                    "missing_fields_json": self._json_dumps(missing_fields) or "[]",
                    "created_at": now,
                    "updated_at": now,
                    "last_action_at": now,
                    "resolution_text": resolution_text,
                    "resolution_sources_json": self._json_dumps(resolution_sources),
                    "escalation_ticket_id": escalation_ticket_id,
                },
            )
            request_id = con.execute(text("SELECT last_insert_rowid()")).scalar_one()
            self._insert_event_in_connection(
                con=con,
                request_id=int(request_id),
                tenant_id=tenant_id,
                event_type=event_type,
                event_note=event_note,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload=event_payload,
                created_at=now,
            )
            return int(request_id)

    def get_by_id(self, request_id: int) -> dict | None:
        """Fetch one HR request by ID."""
        row = self._execute_query_one(
            """SELECT r.request_id, r.tenant_id, r.requester_user_id, r.requester_role,
                      r.subject_employee_id, r.type, r.subtype, r.summary, r.description,
                      r.priority, r.risk_level, r.sla_due_at, r.status, r.assignee_user_id,
                      r.required_fields_json, r.captured_fields_json, r.missing_fields_json,
                      r.created_at, r.updated_at, r.last_action_at, r.resolution_text,
                      r.resolution_sources_json, r.escalation_ticket_id,
                      r.last_message_to_requester, r.last_message_at,
                      req.preferred_name AS requester_name,
                      req.department AS requester_department,
                      req.title AS requester_title,
                      subject.preferred_name AS subject_employee_name,
                      assignee.preferred_name AS assignee_name
               FROM hr_request r
               LEFT JOIN employee req ON req.email = r.requester_user_id
               LEFT JOIN employee subject ON subject.employee_id = r.subject_employee_id
               LEFT JOIN employee assignee ON assignee.email = r.assignee_user_id
               WHERE r.request_id = :request_id""",
            {"request_id": request_id},
        )
        if row is None:
            return None
        return self._deserialize_row(row)

    def list_for_requester(
        self,
        requester_user_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """List HR requests visible for a requester scope."""
        query = """
            SELECT r.request_id, r.tenant_id, r.requester_user_id, r.requester_role,
                   r.subject_employee_id, r.type, r.subtype, r.summary, r.description,
                   r.priority, r.risk_level, r.sla_due_at, r.status, r.assignee_user_id,
                   r.required_fields_json, r.captured_fields_json, r.missing_fields_json,
                   r.created_at, r.updated_at, r.last_action_at, r.resolution_text,
                   r.resolution_sources_json, r.escalation_ticket_id,
                   r.last_message_to_requester, r.last_message_at,
                   req.preferred_name AS requester_name,
                   req.department AS requester_department,
                   req.title AS requester_title,
                   subject.preferred_name AS subject_employee_name,
                   assignee.preferred_name AS assignee_name
            FROM hr_request r
            LEFT JOIN employee req ON req.email = r.requester_user_id
            LEFT JOIN employee subject ON subject.employee_id = r.subject_employee_id
            LEFT JOIN employee assignee ON assignee.email = r.assignee_user_id
            WHERE 1=1
        """
        params: dict[str, str | int] = {"limit": limit}
        if requester_user_id:
            query += " AND r.requester_user_id = :requester_user_id"
            params["requester_user_id"] = requester_user_id
        if status:
            query += " AND r.status = :status"
            params["status"] = status
        query += """
            ORDER BY
              CASE r.status
                WHEN 'NEW' THEN 0
                WHEN 'NEEDS_INFO' THEN 1
                WHEN 'READY' THEN 2
                WHEN 'IN_PROGRESS' THEN 3
                WHEN 'ESCALATED' THEN 4
                WHEN 'RESOLVED' THEN 5
                WHEN 'CANCELLED' THEN 6
                ELSE 7
              END ASC,
              CASE r.priority
                WHEN 'P0' THEN 0
                WHEN 'P1' THEN 1
                WHEN 'P2' THEN 2
                ELSE 3
              END ASC,
              r.updated_at DESC
            LIMIT :limit
        """
        rows = self._execute_query(query, params)
        return [self._deserialize_row(row) for row in rows]

    def list_counts_for_requester(self, requester_user_id: str | None = None) -> dict:
        """Return aggregate status counts."""
        query = """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status='NEW' THEN 1 ELSE 0 END) AS new,
              SUM(CASE WHEN status='NEEDS_INFO' THEN 1 ELSE 0 END) AS needs_info,
              SUM(CASE WHEN status='READY' THEN 1 ELSE 0 END) AS ready,
              SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress,
              SUM(CASE WHEN status='RESOLVED' THEN 1 ELSE 0 END) AS resolved,
              SUM(CASE WHEN status='ESCALATED' THEN 1 ELSE 0 END) AS escalated,
              SUM(CASE WHEN status='CANCELLED' THEN 1 ELSE 0 END) AS cancelled
            FROM hr_request
            WHERE 1=1
        """
        params: dict[str, str] = {}
        if requester_user_id:
            query += " AND requester_user_id = :requester_user_id"
            params["requester_user_id"] = requester_user_id
        row = self._execute_query_one(query, params)
        if not row:
            return {
                "total": 0,
                "new": 0,
                "needs_info": 0,
                "ready": 0,
                "in_progress": 0,
                "resolved": 0,
                "escalated": 0,
                "cancelled": 0,
            }
        return {
            "total": int(row.get("total") or 0),
            "new": int(row.get("new") or 0),
            "needs_info": int(row.get("needs_info") or 0),
            "ready": int(row.get("ready") or 0),
            "in_progress": int(row.get("in_progress") or 0),
            "resolved": int(row.get("resolved") or 0),
            "escalated": int(row.get("escalated") or 0),
            "cancelled": int(row.get("cancelled") or 0),
        }

    def list_events(self, request_id: int) -> list[dict]:
        """List append-only request events (latest first)."""
        rows = self._execute_query(
            """SELECT e.event_id, e.request_id, e.tenant_id, e.event_type, e.event_note,
                      e.actor_user_id, e.actor_role, e.payload_json, e.created_at,
                      actor.preferred_name AS actor_name
               FROM hr_request_event e
               LEFT JOIN employee actor ON actor.email = e.actor_user_id
               WHERE e.request_id = :request_id
               ORDER BY e.created_at DESC""",
            {"request_id": request_id},
        )
        return [self._deserialize_event(row) for row in rows]

    def update_assignment_with_event(
        self,
        request_id: int,
        assignee_user_id: str | None,
        actor_user_id: str,
        actor_role: str,
    ) -> bool:
        """Assign or unassign request ownership and append event."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            updated = (
                con.execute(
                text(
                    """UPDATE hr_request
                       SET assignee_user_id = :assignee_user_id,
                           updated_at = :updated_at,
                           last_action_at = :last_action_at
                       WHERE request_id = :request_id
                       RETURNING tenant_id"""
                ),
                {
                    "assignee_user_id": assignee_user_id,
                    "updated_at": now,
                    "last_action_at": now,
                    "request_id": request_id,
                },
            )
                .mappings()
                .one_or_none()
            )
            if not updated:
                return False
            event_type = "ASSIGNED" if assignee_user_id else "UNASSIGNED"
            event_note = (
                f"Assigned to {assignee_user_id}."
                if assignee_user_id
                else "Request unassigned."
            )
            self._insert_event_in_connection(
                con=con,
                request_id=request_id,
                tenant_id=updated["tenant_id"],
                event_type=event_type,
                event_note=event_note,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload={"assignee_user_id": assignee_user_id},
                created_at=now,
            )
            return True

    def update_priority_with_event(
        self,
        request_id: int,
        priority: str,
        actor_user_id: str,
        actor_role: str,
    ) -> bool:
        """Update request priority and append event."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            updated = (
                con.execute(
                text(
                    """UPDATE hr_request
                       SET priority = :priority,
                           updated_at = :updated_at,
                           last_action_at = :last_action_at
                       WHERE request_id = :request_id
                       RETURNING tenant_id"""
                ),
                {
                    "priority": priority,
                    "updated_at": now,
                    "last_action_at": now,
                    "request_id": request_id,
                },
            )
                .mappings()
                .one_or_none()
            )
            if not updated:
                return False
            self._insert_event_in_connection(
                con=con,
                request_id=request_id,
                tenant_id=updated["tenant_id"],
                event_type="PRIORITY_CHANGED",
                event_note=f"Priority changed to {priority}.",
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload={"priority": priority},
                created_at=now,
            )
            return True

    def update_status_with_event(
        self,
        request_id: int,
        status: str,
        actor_user_id: str,
        actor_role: str,
        resolution_text: str | None = None,
        resolution_sources: list[str] | None = None,
        escalation_ticket_id: str | None = None,
        event_note: str | None = None,
    ) -> bool:
        """Transition request status and append event."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            updated = (
                con.execute(
                text(
                    """UPDATE hr_request
                       SET status = :status,
                           resolution_text = CASE
                             WHEN :resolution_text IS NULL THEN resolution_text
                             ELSE :resolution_text
                           END,
                           resolution_sources_json = CASE
                             WHEN :resolution_sources_json IS NULL THEN resolution_sources_json
                             ELSE :resolution_sources_json
                           END,
                           escalation_ticket_id = CASE
                             WHEN :escalation_ticket_id IS NULL THEN escalation_ticket_id
                             ELSE :escalation_ticket_id
                           END,
                           updated_at = :updated_at,
                           last_action_at = :last_action_at
                       WHERE request_id = :request_id
                       RETURNING tenant_id"""
                ),
                {
                    "status": status,
                    "resolution_text": resolution_text,
                    "resolution_sources_json": self._json_dumps(resolution_sources),
                    "escalation_ticket_id": escalation_ticket_id,
                    "updated_at": now,
                    "last_action_at": now,
                    "request_id": request_id,
                },
            )
                .mappings()
                .one_or_none()
            )
            if not updated:
                return False
            note = event_note or f"Status changed to {status}."
            self._insert_event_in_connection(
                con=con,
                request_id=request_id,
                tenant_id=updated["tenant_id"],
                event_type="STATUS_CHANGED",
                event_note=note,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload={
                    "status": status,
                    "resolution_text": resolution_text,
                    "escalation_ticket_id": escalation_ticket_id,
                },
                created_at=now,
            )
            return True

    def record_message_to_requester_with_event(
        self,
        request_id: int,
        message: str,
        actor_user_id: str,
        actor_role: str,
        set_status: str = "NEEDS_INFO",
    ) -> bool:
        """Persist latest HR message to requester and append audit event."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            updated = (
                con.execute(
                text(
                    """UPDATE hr_request
                       SET last_message_to_requester = :message,
                           last_message_at = :last_message_at,
                           status = CASE
                             WHEN status IN ('RESOLVED', 'CANCELLED') THEN status
                             ELSE :set_status
                           END,
                           updated_at = :updated_at,
                           last_action_at = :last_action_at
                       WHERE request_id = :request_id
                       RETURNING tenant_id"""
                ),
                {
                    "message": message,
                    "last_message_at": now,
                    "set_status": set_status,
                    "updated_at": now,
                    "last_action_at": now,
                    "request_id": request_id,
                },
            )
                .mappings()
                .one_or_none()
            )
            if not updated:
                return False
            self._insert_event_in_connection(
                con=con,
                request_id=request_id,
                tenant_id=updated["tenant_id"],
                event_type="MESSAGE_REQUESTER",
                event_note=message,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload={"status_after_message": set_status},
                created_at=now,
            )
            return True

    def record_requester_reply_with_event(
        self,
        request_id: int,
        message: str,
        actor_user_id: str,
        actor_role: str,
    ) -> bool:
        """Persist requester reply event and move NEEDS_INFO -> READY."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            updated = (
                con.execute(
                text(
                    """UPDATE hr_request
                       SET status = CASE
                             WHEN status = 'NEEDS_INFO' THEN 'READY'
                             ELSE status
                           END,
                           updated_at = :updated_at,
                           last_action_at = :last_action_at
                       WHERE request_id = :request_id
                       RETURNING tenant_id"""
                ),
                {
                    "updated_at": now,
                    "last_action_at": now,
                    "request_id": request_id,
                },
            )
                .mappings()
                .one_or_none()
            )
            if not updated:
                return False
            self._insert_event_in_connection(
                con=con,
                request_id=request_id,
                tenant_id=updated["tenant_id"],
                event_type="REQUESTER_REPLY",
                event_note=message,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload={},
                created_at=now,
            )
            return True

    def update_field_tracking_with_event(
        self,
        request_id: int,
        captured_fields: dict[str, Any],
        missing_fields: list[str],
        status: str,
        actor_user_id: str,
        actor_role: str,
    ) -> bool:
        """Update captured/missing fields and append audit event."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            updated = (
                con.execute(
                text(
                    """UPDATE hr_request
                       SET captured_fields_json = :captured_fields_json,
                           missing_fields_json = :missing_fields_json,
                           status = :status,
                           updated_at = :updated_at,
                           last_action_at = :last_action_at
                       WHERE request_id = :request_id
                       RETURNING tenant_id"""
                ),
                {
                    "captured_fields_json": self._json_dumps(captured_fields) or "{}",
                    "missing_fields_json": self._json_dumps(missing_fields) or "[]",
                    "status": status,
                    "updated_at": now,
                    "last_action_at": now,
                    "request_id": request_id,
                },
            )
                .mappings()
                .one_or_none()
            )
            if not updated:
                return False
            self._insert_event_in_connection(
                con=con,
                request_id=request_id,
                tenant_id=updated["tenant_id"],
                event_type="FIELDS_UPDATED",
                event_note="Captured fields updated.",
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                payload={"missing_fields": missing_fields, "status": status},
                created_at=now,
            )
            return True
