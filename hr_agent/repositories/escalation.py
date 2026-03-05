"""
Escalation Repository - Human-in-the-loop HR escalation requests.
"""

from datetime import datetime

from .base import BaseRepository


class EscalationRepository(BaseRepository):
    """Repository for HR escalation request data."""

    def create(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source_message_excerpt: str,
        status: str = "PENDING",
        resolution_note: str | None = None,
    ) -> int:
        """Create a new escalation request and return its ID."""
        now = datetime.now().isoformat()
        return self._execute_insert(
            """INSERT INTO hr_escalation_request
               (
                 requester_employee_id,
                 requester_email,
                 thread_id,
                 source_message_excerpt,
                 status,
                 created_at,
                 updated_at,
                 updated_by_employee_id,
                 resolution_note
               )
               VALUES
               (
                 :requester_employee_id,
                 :requester_email,
                 :thread_id,
                 :source_message_excerpt,
                 :status,
                 :created_at,
                 :updated_at,
                 NULL,
                 :resolution_note
               )""",
            {
                "requester_employee_id": requester_employee_id,
                "requester_email": requester_email,
                "thread_id": thread_id,
                "source_message_excerpt": source_message_excerpt,
                "status": status,
                "created_at": now,
                "updated_at": now,
                "resolution_note": resolution_note,
            },
        )

    def get_by_id(self, escalation_id: int) -> dict | None:
        """Fetch a single escalation request."""
        return self._execute_query_one(
            """SELECT escalation_id, requester_employee_id, requester_email, thread_id,
                      source_message_excerpt, status, created_at, updated_at,
                      updated_by_employee_id, resolution_note
               FROM hr_escalation_request
               WHERE escalation_id = :escalation_id""",
            {"escalation_id": escalation_id},
        )

    def list_for_requester(
        self,
        requester_email: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        List escalation requests.

        When requester_email is None, returns requests across users (for HR/Managers).
        """
        query = """
            SELECT escalation_id, requester_employee_id, requester_email, thread_id,
                   source_message_excerpt, status, created_at, updated_at,
                   updated_by_employee_id, resolution_note
            FROM hr_escalation_request
            WHERE 1=1
        """
        params: dict[str, str | int] = {"limit": limit}

        if requester_email:
            query += " AND requester_email = :requester_email"
            params["requester_email"] = requester_email

        if status:
            query += " AND status = :status"
            params["status"] = status

        query += " ORDER BY updated_at DESC LIMIT :limit"
        return self._execute_query(query, params)

    def list_counts_for_requester(self, requester_email: str | None = None) -> dict:
        """Return aggregate counts by status and total."""
        query = """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN status='IN_REVIEW' THEN 1 ELSE 0 END) AS in_review,
              SUM(CASE WHEN status='RESOLVED' THEN 1 ELSE 0 END) AS resolved
            FROM hr_escalation_request
            WHERE 1=1
        """
        params: dict[str, str] = {}

        if requester_email:
            query += " AND requester_email = :requester_email"
            params["requester_email"] = requester_email

        row = self._execute_query_one(query, params)
        if not row:
            return {"total": 0, "pending": 0, "in_review": 0, "resolved": 0}

        return {
            "total": int(row.get("total") or 0),
            "pending": int(row.get("pending") or 0),
            "in_review": int(row.get("in_review") or 0),
            "resolved": int(row.get("resolved") or 0),
        }

    def transition_status(
        self,
        escalation_id: int,
        status: str,
        updated_by_employee_id: int,
        resolution_note: str | None = None,
    ) -> bool:
        """Update escalation status and reviewer metadata."""
        rows = self._execute_update(
            """UPDATE hr_escalation_request
               SET status = :status,
                   updated_at = :updated_at,
                   updated_by_employee_id = :updated_by_employee_id,
                   resolution_note = :resolution_note
               WHERE escalation_id = :escalation_id""",
            {
                "status": status,
                "updated_at": datetime.now().isoformat(),
                "updated_by_employee_id": updated_by_employee_id,
                "resolution_note": resolution_note,
                "escalation_id": escalation_id,
            },
        )
        return rows > 0
