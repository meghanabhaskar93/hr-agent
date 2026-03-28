"""
Employee Repository - Employee and Organization data access
"""

from datetime import datetime, date
from typing import cast
from .base import BaseRepository


class EmployeeRepository(BaseRepository):
    """Repository for employee and organization data."""

    # ========== SEARCH & BASIC INFO ==========

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search employees by name, email, or title."""
        q = f"%{query.lower()}%"
        return self._execute_query(
            """SELECT employee_id, preferred_name, legal_name, email, title, department
               FROM employee
               WHERE lower(preferred_name) LIKE :q
                  OR lower(legal_name) LIKE :q
                  OR lower(email) LIKE :q
                  OR lower(title) LIKE :q
               LIMIT :lim""",
            {"q": q, "lim": limit},
        )

    def get_by_id(self, employee_id: int) -> dict | None:
        """Get basic employee information."""
        return self._execute_query_one(
            """SELECT employee_id, preferred_name, legal_name, email, title, department,
                      location, employment_status, hire_date, cost_center
               FROM employee WHERE employee_id=:e""",
            {"e": employee_id},
        )

    def get_by_email(self, email: str) -> dict | None:
        """Get employee by email."""
        return self._execute_query_one(
            """SELECT employee_id, preferred_name, legal_name, email, title, department
               FROM employee WHERE email=:e""",
            {"e": email},
        )

    def get_cost_center(self, employee_id: int) -> str | None:
        """Get employee's cost center."""
        return cast(
            str | None,
            self._execute_scalar(
                "SELECT cost_center FROM employee WHERE employee_id=:e",
                {"e": employee_id},
            ),
        )

    def get_tenure(self, employee_id: int) -> dict | None:
        """Get employee tenure information."""
        row = self._execute_query_one(
            """SELECT employee_id, preferred_name, hire_date, employment_status
               FROM employee WHERE employee_id=:e""",
            {"e": employee_id},
        )
        if not row:
            return None

        hire_date = datetime.strptime(row["hire_date"], "%Y-%m-%d").date()
        years = (date.today() - hire_date).days / 365.25

        return {
            **row,
            "years_of_service": round(years, 1),
        }

    # ========== ORGANIZATION STRUCTURE ==========

    def get_manager(self, employee_id: int) -> dict | None:
        """Get the direct manager of an employee."""
        return self._execute_query_one(
            """SELECT m.employee_id, m.preferred_name, m.email, m.title, m.department
               FROM employee e
               JOIN employee m ON e.manager_employee_id = m.employee_id
               WHERE e.employee_id=:e""",
            {"e": employee_id},
        )

    def get_direct_reports(self, manager_id: int) -> list[dict]:
        """Get all direct reports for a manager."""
        return self._execute_query(
            """SELECT e.employee_id, e.preferred_name, e.email, e.title, e.department
               FROM manager_reports r
               JOIN employee e ON e.employee_id = r.report_employee_id
               WHERE r.manager_employee_id=:m
               ORDER BY e.preferred_name""",
            {"m": manager_id},
        )

    def get_manager_chain(self, employee_id: int, max_depth: int = 6) -> list[dict]:
        """Get the full management chain up to CEO."""
        chain: list[dict] = []
        current = employee_id
        for _ in range(max_depth):
            mgr = self.get_manager(current)
            if not mgr:
                break
            chain.append(mgr)
            current = mgr["employee_id"]
        return chain

    def get_team_overview(self, manager_id: int) -> dict:
        """Get a summary of a manager's team."""
        mgr = self._execute_query_one(
            """SELECT employee_id, preferred_name, title, department
               FROM employee WHERE employee_id=:m""",
            {"m": manager_id},
        )
        if not mgr:
            return {"error": "Manager not found"}

        reports = self._execute_query(
            """SELECT e.employee_id, e.preferred_name, e.title, e.department, e.employment_status
               FROM manager_reports r
               JOIN employee e ON e.employee_id = r.report_employee_id
               WHERE r.manager_employee_id=:m
               ORDER BY e.department, e.preferred_name""",
            {"m": manager_id},
        )

        # Group by department
        by_dept: dict[str, list] = {}
        for r in reports:
            dept = r["department"]
            by_dept.setdefault(dept, []).append(
                {
                    "employee_id": r["employee_id"],
                    "name": r["preferred_name"],
                    "title": r["title"],
                    "status": r["employment_status"],
                }
            )

        return {
            "manager": mgr,
            "total_direct_reports": len(reports),
            "by_department": by_dept,
        }

    def get_department_members(self, department: str) -> list[dict]:
        """Get all employees in a department."""
        return self._execute_query(
            """SELECT employee_id, preferred_name, email, title, location, employment_status
               FROM employee
               WHERE lower(department) = lower(:dept)
               ORDER BY preferred_name""",
            {"dept": department},
        )

    def get_org_chart(self, root_id: int | None = None, max_depth: int = 3) -> dict:
        """Get organizational chart."""

        def get_subtree(emp_id: int, depth: int) -> dict:
            emp = self._execute_query_one(
                """SELECT employee_id, preferred_name, title, department
                   FROM employee WHERE employee_id=:e""",
                {"e": emp_id},
            )
            if not emp:
                return {}

            result = dict(emp)
            if depth < max_depth:
                report_ids = self._execute_query(
                    "SELECT report_employee_id FROM manager_reports WHERE manager_employee_id=:m",
                    {"m": emp_id},
                )
                if report_ids:
                    result["direct_reports"] = [
                        get_subtree(r["report_employee_id"], depth + 1)
                        for r in report_ids
                    ]
            return result

        # Find CEO if no root specified
        if root_id is None:
            root_id = self._execute_scalar(
                "SELECT employee_id FROM employee WHERE manager_employee_id IS NULL"
            )

        if not root_id:
            return {"error": "No root employee found"}

        return get_subtree(root_id, 0)

    # ========== IDENTITY & ROLE MAPPING ==========

    def get_employee_id_by_email(self, email: str) -> int | None:
        """Get employee ID from email via identity map."""
        return cast(
            int | None,
            self._execute_scalar(
                "SELECT employee_id FROM identity_map WHERE user_email=:u",
                {"u": email},
            ),
        )

    def get_role_by_email(self, email: str) -> str:
        """Get app role from email."""
        role = self._execute_scalar(
            "SELECT app_role FROM app_role_map WHERE user_email=:u", {"u": email}
        )
        return role or "EMPLOYEE"

    def get_direct_report_ids(self, manager_id: int) -> list[int]:
        """Get list of direct report employee IDs."""
        rows = self._execute_query(
            "SELECT report_employee_id FROM manager_reports WHERE manager_employee_id=:e",
            {"e": manager_id},
        )
        return [r["report_employee_id"] for r in rows]

    def is_direct_report(self, manager_id: int, employee_id: int) -> bool:
        """Check if employee is a direct report of manager."""
        result = self._execute_scalar(
            """SELECT 1 FROM manager_reports
               WHERE manager_employee_id=:m AND report_employee_id=:e""",
            {"m": manager_id, "e": employee_id},
        )
        return result is not None

    # ========== UI HELPERS ==========

    def list_all_for_dropdown(self) -> list[dict]:
        """Get all employees for UI dropdown selection."""
        return self._execute_query(
            """SELECT email, legal_name, preferred_name, title, department
               FROM employee
               ORDER BY legal_name""",
        )

    def get_details_with_manager(self, email: str) -> dict | None:
        """Get employee details including manager name for UI display."""
        return self._execute_query_one(
            """SELECT e.legal_name, e.preferred_name, e.title, e.department,
                      e.location, e.hire_date, e.employee_id,
                      m.legal_name as manager_name
               FROM employee e
               LEFT JOIN manager_reports mr ON mr.report_employee_id = e.employee_id
               LEFT JOIN employee m ON mr.manager_employee_id = m.employee_id
               WHERE e.email = :email""",
            {"email": email},
        )
