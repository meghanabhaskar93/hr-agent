"""
Escalation Repository - Human-in-the-loop HR escalation requests.
"""

from datetime import datetime
import json

from sqlalchemy import text

from .base import BaseRepository


class EscalationRepository(BaseRepository):
    """Repository for HR escalation request data."""

    def _insert_event_in_connection(
        self,
        con,
        escalation_id: int,
        event_type: str,
        actor_employee_id: int | None,
        actor_email: str | None,
        event_note: str | None = None,
        metadata: dict | None = None,
        created_at: str | None = None,
    ) -> None:
        """Insert a timeline event using an existing transaction connection."""
        con.execute(
            text(
                """INSERT INTO hr_escalation_event
                   (
                     escalation_id,
                     event_type,
                     event_note,
                     actor_employee_id,
                     actor_email,
                     metadata_json,
                     created_at
                   )
                   VALUES
                   (
                     :escalation_id,
                     :event_type,
                     :event_note,
                     :actor_employee_id,
                     :actor_email,
                     :metadata_json,
                     :created_at
                   )"""
            ),
            {
                "escalation_id": escalation_id,
                "event_type": event_type,
                "event_note": event_note,
                "actor_employee_id": actor_employee_id,
                "actor_email": actor_email,
                "metadata_json": json.dumps(metadata) if metadata else None,
                "created_at": created_at or datetime.now().isoformat(),
            },
        )

    def create(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source_message_excerpt: str,
        status: str = "PENDING",
        resolution_note: str | None = None,
        priority: str = "MEDIUM",
        category: str | None = None,
        assigned_to_employee_id: int | None = None,
        assigned_to_email: str | None = None,
        agent_suggestion: str | None = None,
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
                 resolution_note,
                 priority,
                 category,
                 assigned_to_employee_id,
                 assigned_to_email,
                 agent_suggestion,
                 last_message_to_requester,
                 last_message_at,
                 escalation_level
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
                 :resolution_note,
                 :priority,
                 :category,
                 :assigned_to_employee_id,
                 :assigned_to_email,
                 :agent_suggestion,
                 NULL,
                 NULL,
                 1
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
                "priority": priority,
                "category": category,
                "assigned_to_employee_id": assigned_to_employee_id,
                "assigned_to_email": assigned_to_email,
                "agent_suggestion": agent_suggestion,
            },
        )

    def get_by_id(self, escalation_id: int) -> dict | None:
        """Fetch a single escalation request."""
        return self._execute_query_one(
            """SELECT r.escalation_id, r.requester_employee_id, r.requester_email, r.thread_id,
                      r.source_message_excerpt, r.status, r.created_at, r.updated_at,
                      r.updated_by_employee_id, r.resolution_note, r.priority, r.category,
                      r.assigned_to_employee_id, r.assigned_to_email, r.agent_suggestion,
                      r.last_message_to_requester, r.last_message_at, r.escalation_level,
                      req.preferred_name AS requester_name,
                      req.department AS requester_department,
                      req.title AS requester_title,
                      assignee.preferred_name AS assigned_to_name
               FROM hr_escalation_request r
               LEFT JOIN employee req ON req.employee_id = r.requester_employee_id
               LEFT JOIN employee assignee ON assignee.employee_id = r.assigned_to_employee_id
               WHERE r.escalation_id = :escalation_id""",
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
            SELECT r.escalation_id, r.requester_employee_id, r.requester_email, r.thread_id,
                   r.source_message_excerpt, r.status, r.created_at, r.updated_at,
                   r.updated_by_employee_id, r.resolution_note, r.priority, r.category,
                   r.assigned_to_employee_id, r.assigned_to_email, r.agent_suggestion,
                   r.last_message_to_requester, r.last_message_at, r.escalation_level,
                   req.preferred_name AS requester_name,
                   req.department AS requester_department,
                   req.title AS requester_title,
                   assignee.preferred_name AS assigned_to_name
            FROM hr_escalation_request r
            LEFT JOIN employee req ON req.employee_id = r.requester_employee_id
            LEFT JOIN employee assignee ON assignee.employee_id = r.assigned_to_employee_id
            WHERE 1=1
        """
        params: dict[str, str | int] = {"limit": limit}

        if requester_email:
            query += " AND r.requester_email = :requester_email"
            params["requester_email"] = requester_email

        if status:
            query += " AND r.status = :status"
            params["status"] = status

        query += """
            ORDER BY
              CASE r.status
                WHEN 'PENDING' THEN 0
                WHEN 'IN_REVIEW' THEN 1
                WHEN 'RESOLVED' THEN 2
                ELSE 3
              END ASC,
              CASE r.priority
                WHEN 'CRITICAL' THEN 0
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
                ELSE 4
              END ASC,
              r.updated_at DESC
            LIMIT :limit
        """
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

    def list_category_counts_for_month(
        self,
        month: str,
        requester_email: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Return top escalation categories for a YYYY-MM month window."""
        query = """
            SELECT
              COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized') AS category,
              COUNT(*) AS count
            FROM hr_escalation_request
            WHERE substr(created_at, 1, 7) = :month
        """
        params: dict[str, str | int] = {"month": month, "limit": limit}

        if requester_email:
            query += " AND requester_email = :requester_email"
            params["requester_email"] = requester_email

        query += """
            GROUP BY COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized')
            ORDER BY count DESC, category ASC
            LIMIT :limit
        """
        rows = self._execute_query(query, params)
        return [
            {
                "category": str(row.get("category") or "Uncategorized"),
                "count": int(row.get("count") or 0),
            }
            for row in rows
        ]

    def count_for_month(
        self,
        month: str,
        requester_email: str | None = None,
    ) -> int:
        """Return total escalations for a YYYY-MM month window."""
        query = """
            SELECT COUNT(*) AS total
            FROM hr_escalation_request
            WHERE substr(created_at, 1, 7) = :month
        """
        params: dict[str, str] = {"month": month}
        if requester_email:
            query += " AND requester_email = :requester_email"
            params["requester_email"] = requester_email
        row = self._execute_query_one(query, params)
        return int((row or {}).get("total") or 0)

    def list_status_counts_for_month(
        self,
        month: str,
        requester_email: str | None = None,
    ) -> dict:
        """Return month-level status counts for escalations."""
        query = """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN status='IN_REVIEW' THEN 1 ELSE 0 END) AS in_review,
              SUM(CASE WHEN status='RESOLVED' THEN 1 ELSE 0 END) AS resolved
            FROM hr_escalation_request
            WHERE substr(created_at, 1, 7) = :month
        """
        params: dict[str, str] = {"month": month}
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

    def list_category_status_counts_for_month(
        self,
        month: str,
        requester_email: str | None = None,
    ) -> list[dict]:
        """Return per-category status counts for a YYYY-MM month window."""
        query = """
            SELECT
              COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized') AS category,
              status,
              COUNT(*) AS count
            FROM hr_escalation_request
            WHERE substr(created_at, 1, 7) = :month
        """
        params: dict[str, str] = {"month": month}
        if requester_email:
            query += " AND requester_email = :requester_email"
            params["requester_email"] = requester_email
        query += """
            GROUP BY COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized'), status
        """
        rows = self._execute_query(query, params)
        return [
            {
                "category": str(row.get("category") or "Uncategorized"),
                "status": str(row.get("status") or "PENDING"),
                "count": int(row.get("count") or 0),
            }
            for row in rows
        ]

    def create_with_event(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source_message_excerpt: str,
        status: str = "PENDING",
        resolution_note: str | None = None,
        priority: str = "MEDIUM",
        category: str | None = None,
        assigned_to_employee_id: int | None = None,
        assigned_to_email: str | None = None,
        agent_suggestion: str | None = None,
        event_type: str = "CREATED",
        event_note: str = "Escalation request created.",
    ) -> int:
        """Create escalation and timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            con.execute(
                text(
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
                         resolution_note,
                         priority,
                         category,
                         assigned_to_employee_id,
                         assigned_to_email,
                         agent_suggestion,
                         last_message_to_requester,
                         last_message_at,
                         escalation_level
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
                         :resolution_note,
                         :priority,
                         :category,
                         :assigned_to_employee_id,
                         :assigned_to_email,
                         :agent_suggestion,
                         NULL,
                         NULL,
                         1
                       )"""
                ),
                {
                    "requester_employee_id": requester_employee_id,
                    "requester_email": requester_email,
                    "thread_id": thread_id,
                    "source_message_excerpt": source_message_excerpt,
                    "status": status,
                    "created_at": now,
                    "updated_at": now,
                    "resolution_note": resolution_note,
                    "priority": priority,
                    "category": category,
                    "assigned_to_employee_id": assigned_to_employee_id,
                    "assigned_to_email": assigned_to_email,
                    "agent_suggestion": agent_suggestion,
                },
            )
            escalation_id = con.execute(text("SELECT last_insert_rowid()")).scalar_one()
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type=event_type,
                actor_employee_id=requester_employee_id,
                actor_email=requester_email,
                event_note=event_note,
                created_at=now,
            )
            return int(escalation_id)

    def add_event(
        self,
        escalation_id: int,
        event_type: str,
        actor_employee_id: int | None,
        actor_email: str | None,
        event_note: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Persist an escalation timeline event."""
        return self._execute_insert(
            """INSERT INTO hr_escalation_event
               (
                 escalation_id,
                 event_type,
                 event_note,
                 actor_employee_id,
                 actor_email,
                 metadata_json,
                 created_at
               )
               VALUES
               (
                 :escalation_id,
                 :event_type,
                 :event_note,
                 :actor_employee_id,
                 :actor_email,
                 :metadata_json,
                 :created_at
               )""",
            {
                "escalation_id": escalation_id,
                "event_type": event_type,
                "event_note": event_note,
                "actor_employee_id": actor_employee_id,
                "actor_email": actor_email,
                "metadata_json": json.dumps(metadata) if metadata else None,
                "created_at": datetime.now().isoformat(),
            },
        )

    def list_events(self, escalation_id: int) -> list[dict]:
        """List escalation timeline events (latest first)."""
        return self._execute_query(
            """
            SELECT e.event_id, e.escalation_id, e.event_type, e.event_note,
                   e.actor_employee_id, e.actor_email, e.metadata_json, e.created_at,
                   actor.preferred_name AS actor_name
            FROM hr_escalation_event e
            LEFT JOIN employee actor ON actor.employee_id = e.actor_employee_id
            WHERE e.escalation_id = :escalation_id
            ORDER BY e.created_at DESC
            """,
            {"escalation_id": escalation_id},
        )

    def update_assignment(
        self,
        escalation_id: int,
        updated_by_employee_id: int,
        assigned_to_employee_id: int | None,
        assigned_to_email: str | None,
    ) -> bool:
        """Assign or unassign an escalation request."""
        rows = self._execute_update(
            """UPDATE hr_escalation_request
               SET assigned_to_employee_id = :assigned_to_employee_id,
                   assigned_to_email = :assigned_to_email,
                   updated_by_employee_id = :updated_by_employee_id,
                   updated_at = :updated_at
               WHERE escalation_id = :escalation_id""",
            {
                "assigned_to_employee_id": assigned_to_employee_id,
                "assigned_to_email": assigned_to_email,
                "updated_by_employee_id": updated_by_employee_id,
                "updated_at": datetime.now().isoformat(),
                "escalation_id": escalation_id,
            },
        )
        return rows > 0

    def update_assignment_with_event(
        self,
        escalation_id: int,
        updated_by_employee_id: int,
        assigned_to_employee_id: int | None,
        assigned_to_email: str | None,
        actor_email: str,
        event_type: str,
        event_note: str,
    ) -> bool:
        """Assign/unassign and append timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(
                text(
                    """UPDATE hr_escalation_request
                       SET assigned_to_employee_id = :assigned_to_employee_id,
                           assigned_to_email = :assigned_to_email,
                           updated_by_employee_id = :updated_by_employee_id,
                           updated_at = :updated_at
                       WHERE escalation_id = :escalation_id"""
                ),
                {
                    "assigned_to_employee_id": assigned_to_employee_id,
                    "assigned_to_email": assigned_to_email,
                    "updated_by_employee_id": updated_by_employee_id,
                    "updated_at": now,
                    "escalation_id": escalation_id,
                },
            )
            if result.rowcount <= 0:
                return False
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type=event_type,
                actor_employee_id=updated_by_employee_id,
                actor_email=actor_email,
                event_note=event_note,
                created_at=now,
            )
            return True

    def update_priority(
        self,
        escalation_id: int,
        priority: str,
        updated_by_employee_id: int,
    ) -> bool:
        """Update escalation priority."""
        rows = self._execute_update(
            """UPDATE hr_escalation_request
               SET priority = :priority,
                   updated_by_employee_id = :updated_by_employee_id,
                   updated_at = :updated_at
               WHERE escalation_id = :escalation_id""",
            {
                "priority": priority,
                "updated_by_employee_id": updated_by_employee_id,
                "updated_at": datetime.now().isoformat(),
                "escalation_id": escalation_id,
            },
        )
        return rows > 0

    def update_priority_with_event(
        self,
        escalation_id: int,
        priority: str,
        updated_by_employee_id: int,
        actor_email: str,
    ) -> bool:
        """Update priority and append timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(
                text(
                    """UPDATE hr_escalation_request
                       SET priority = :priority,
                           updated_by_employee_id = :updated_by_employee_id,
                           updated_at = :updated_at
                       WHERE escalation_id = :escalation_id"""
                ),
                {
                    "priority": priority,
                    "updated_by_employee_id": updated_by_employee_id,
                    "updated_at": now,
                    "escalation_id": escalation_id,
                },
            )
            if result.rowcount <= 0:
                return False
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type="PRIORITY_CHANGED",
                actor_employee_id=updated_by_employee_id,
                actor_email=actor_email,
                event_note=f"Priority changed to {priority}.",
                metadata={"priority": priority},
                created_at=now,
            )
            return True

    def record_message_to_requester(
        self,
        escalation_id: int,
        message: str,
        updated_by_employee_id: int,
    ) -> bool:
        """Store the last message sent to requester."""
        now = datetime.now().isoformat()
        rows = self._execute_update(
            """UPDATE hr_escalation_request
               SET last_message_to_requester = :message,
                   last_message_at = :last_message_at,
                   updated_by_employee_id = :updated_by_employee_id,
                   updated_at = :updated_at
               WHERE escalation_id = :escalation_id""",
            {
                "message": message,
                "last_message_at": now,
                "updated_by_employee_id": updated_by_employee_id,
                "updated_at": now,
                "escalation_id": escalation_id,
            },
        )
        return rows > 0

    def record_message_to_requester_with_event(
        self,
        escalation_id: int,
        message: str,
        updated_by_employee_id: int,
        actor_email: str,
    ) -> bool:
        """Persist message and timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(
                text(
                    """UPDATE hr_escalation_request
                       SET last_message_to_requester = :message,
                           last_message_at = :last_message_at,
                           updated_by_employee_id = :updated_by_employee_id,
                           updated_at = :updated_at
                       WHERE escalation_id = :escalation_id"""
                ),
                {
                    "message": message,
                    "last_message_at": now,
                    "updated_by_employee_id": updated_by_employee_id,
                    "updated_at": now,
                    "escalation_id": escalation_id,
                },
            )
            if result.rowcount <= 0:
                return False
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type="MESSAGE_REQUESTER",
                actor_employee_id=updated_by_employee_id,
                actor_email=actor_email,
                event_note=message,
                created_at=now,
            )
            return True

    def record_requester_reply_with_event(
        self,
        escalation_id: int,
        message: str,
        updated_by_employee_id: int,
        actor_email: str,
    ) -> bool:
        """Persist requester reply and timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(
                text(
                    """UPDATE hr_escalation_request
                       SET updated_by_employee_id = :updated_by_employee_id,
                           updated_at = :updated_at
                       WHERE escalation_id = :escalation_id"""
                ),
                {
                    "updated_by_employee_id": updated_by_employee_id,
                    "updated_at": now,
                    "escalation_id": escalation_id,
                },
            )
            if result.rowcount <= 0:
                return False
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type="REQUESTER_REPLY",
                actor_employee_id=updated_by_employee_id,
                actor_email=actor_email,
                event_note=message,
                created_at=now,
            )
            return True

    def escalate_case(
        self,
        escalation_id: int,
        updated_by_employee_id: int,
        note: str | None = None,
    ) -> bool:
        """Escalate a request severity and level."""
        now = datetime.now().isoformat()
        rows = self._execute_update(
            """UPDATE hr_escalation_request
               SET escalation_level = COALESCE(escalation_level, 1) + 1,
                   priority = 'CRITICAL',
                   status = CASE
                     WHEN status = 'PENDING' THEN 'IN_REVIEW'
                     ELSE status
                   END,
                   resolution_note = CASE
                     WHEN :note IS NULL OR :note = '' THEN resolution_note
                     ELSE :note
                   END,
                   updated_by_employee_id = :updated_by_employee_id,
                   updated_at = :updated_at
               WHERE escalation_id = :escalation_id""",
            {
                "note": note,
                "updated_by_employee_id": updated_by_employee_id,
                "updated_at": now,
                "escalation_id": escalation_id,
            },
        )
        return rows > 0

    def escalate_case_with_event(
        self,
        escalation_id: int,
        updated_by_employee_id: int,
        actor_email: str,
        note: str | None = None,
    ) -> bool:
        """Escalate case and append timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(
                text(
                    """UPDATE hr_escalation_request
                       SET escalation_level = COALESCE(escalation_level, 1) + 1,
                           priority = 'CRITICAL',
                           status = CASE
                             WHEN status = 'PENDING' THEN 'IN_REVIEW'
                             ELSE status
                           END,
                           resolution_note = CASE
                             WHEN :note IS NULL OR :note = '' THEN resolution_note
                             ELSE :note
                           END,
                           updated_by_employee_id = :updated_by_employee_id,
                           updated_at = :updated_at
                       WHERE escalation_id = :escalation_id"""
                ),
                {
                    "note": note,
                    "updated_by_employee_id": updated_by_employee_id,
                    "updated_at": now,
                    "escalation_id": escalation_id,
                },
            )
            if result.rowcount <= 0:
                return False
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type="ESCALATED",
                actor_employee_id=updated_by_employee_id,
                actor_email=actor_email,
                event_note=note or "Escalated for urgent handling.",
                created_at=now,
            )
            return True

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

    def transition_status_with_event(
        self,
        escalation_id: int,
        status: str,
        updated_by_employee_id: int,
        actor_email: str,
        resolution_note: str | None = None,
    ) -> bool:
        """Transition status and append timeline event atomically."""
        now = datetime.now().isoformat()
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(
                text(
                    """UPDATE hr_escalation_request
                       SET status = :status,
                           updated_at = :updated_at,
                           updated_by_employee_id = :updated_by_employee_id,
                           resolution_note = :resolution_note
                       WHERE escalation_id = :escalation_id"""
                ),
                {
                    "status": status,
                    "updated_at": now,
                    "updated_by_employee_id": updated_by_employee_id,
                    "resolution_note": resolution_note,
                    "escalation_id": escalation_id,
                },
            )
            if result.rowcount <= 0:
                return False
            self._insert_event_in_connection(
                con=con,
                escalation_id=escalation_id,
                event_type="STATUS_CHANGED",
                actor_employee_id=updated_by_employee_id,
                actor_email=actor_email,
                event_note=f"Status changed to {status}.",
                metadata={"new_status": status},
                created_at=now,
            )
            return True
