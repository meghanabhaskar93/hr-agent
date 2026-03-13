from sqlalchemy import text
from .utils.db import get_engine


def _ensure_sqlite_column(con, table_name: str, column_name: str, ddl: str) -> None:
    """Add a column for SQLite tables when upgrading existing local DBs."""
    columns = {
        row["name"]
        for row in con.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    }
    if column_name not in columns:
        con.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def seed_if_needed() -> None:
    eng = get_engine()
    with eng.begin() as con:
        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS employee (
          employee_id INTEGER PRIMARY KEY,
          legal_name TEXT NOT NULL,
          preferred_name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          department TEXT NOT NULL,
          location TEXT NOT NULL,
          hire_date TEXT NOT NULL,
          employment_status TEXT NOT NULL,
          manager_employee_id INTEGER NULL,
          cost_center TEXT NOT NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS identity_map (
          user_email TEXT PRIMARY KEY,
          employee_id INTEGER NOT NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS manager_reports (
          manager_employee_id INTEGER NOT NULL,
          report_employee_id INTEGER NOT NULL,
          PRIMARY KEY (manager_employee_id, report_employee_id)
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS app_role_map (
          user_email TEXT PRIMARY KEY,
          app_role TEXT NOT NULL -- EMPLOYEE / MANAGER / HR / FINANCE
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS holiday_entitlement (
          employee_id INTEGER NOT NULL,
          year INTEGER NOT NULL,
          entitlement_days REAL NOT NULL,
          carried_over_days REAL NOT NULL,
          PRIMARY KEY (employee_id, year)
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS holiday_request (
          request_id INTEGER PRIMARY KEY,
          employee_id INTEGER NOT NULL,
          start_date TEXT NOT NULL,
          end_date TEXT NOT NULL,
          days REAL NOT NULL,
          status TEXT NOT NULL,
          reason TEXT NULL,
          requested_at TEXT NOT NULL,
          reviewed_by INTEGER NULL,
          reviewed_at TEXT NULL,
          rejection_reason TEXT NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS hr_escalation_request (
          escalation_id INTEGER PRIMARY KEY,
          requester_employee_id INTEGER NOT NULL,
          requester_email TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          source_message_excerpt TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          updated_by_employee_id INTEGER NULL,
          resolution_note TEXT NULL,
          priority TEXT NOT NULL DEFAULT 'MEDIUM',
          category TEXT NULL,
          assigned_to_employee_id INTEGER NULL,
          assigned_to_email TEXT NULL,
          agent_suggestion TEXT NULL,
          last_message_to_requester TEXT NULL,
          last_message_at TEXT NULL,
          escalation_level INTEGER NOT NULL DEFAULT 1
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS hr_escalation_event (
          event_id INTEGER PRIMARY KEY,
          escalation_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,
          event_note TEXT NULL,
          actor_employee_id INTEGER NULL,
          actor_email TEXT NULL,
          metadata_json TEXT NULL,
          created_at TEXT NOT NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE INDEX IF NOT EXISTS idx_escalation_status_priority_updated
          ON hr_escalation_request(status, priority, updated_at);
        """
            )
        )
        con.execute(
            text(
                """
        CREATE INDEX IF NOT EXISTS idx_escalation_assignee_updated
          ON hr_escalation_request(assigned_to_email, updated_at);
        """
            )
        )
        con.execute(
            text(
                """
        CREATE INDEX IF NOT EXISTS idx_escalation_requester_updated
          ON hr_escalation_request(requester_email, updated_at);
        """
            )
        )
        con.execute(
            text(
                """
        CREATE INDEX IF NOT EXISTS idx_escalation_event_parent_created
          ON hr_escalation_event(escalation_id, created_at);
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS compensation (
          employee_id INTEGER PRIMARY KEY,
          currency TEXT NOT NULL,
          base_salary REAL NOT NULL,
          bonus_target_pct REAL NOT NULL,
          equity_shares INTEGER DEFAULT 0,
          last_review_date TEXT NULL,
          next_review_date TEXT NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS salary_history (
          id INTEGER PRIMARY KEY,
          employee_id INTEGER NOT NULL,
          effective_date TEXT NOT NULL,
          base_salary REAL NOT NULL,
          currency TEXT NOT NULL,
          change_reason TEXT NULL,
          change_pct REAL NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS finance_cost_center_access (
          user_email TEXT NOT NULL,
          cost_center TEXT NOT NULL,
          PRIMARY KEY (user_email, cost_center)
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS company_policy (
          policy_id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          summary TEXT NOT NULL,
          full_text TEXT NOT NULL,
          effective_date TEXT NOT NULL,
          last_updated TEXT NOT NULL,
          status TEXT DEFAULT 'ACTIVE'
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS company_holiday (
          id INTEGER PRIMARY KEY,
          holiday_date TEXT NOT NULL,
          name TEXT NOT NULL,
          is_paid INTEGER DEFAULT 1
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS announcement (
          announcement_id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          summary TEXT NOT NULL,
          category TEXT NOT NULL,
          posted_by INTEGER NOT NULL,
          posted_at TEXT NOT NULL,
          expires_at TEXT NULL
        );
        """
            )
        )

        con.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS company_event (
          event_id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          event_date TEXT NOT NULL,
          event_time TEXT NULL,
          location TEXT NULL,
          description TEXT NULL
        );
        """
            )
        )

        # Migration-safe column upgrades for existing local DBs.
        _ensure_sqlite_column(
            con, "hr_escalation_request", "priority", "priority TEXT NOT NULL DEFAULT 'MEDIUM'"
        )
        _ensure_sqlite_column(con, "hr_escalation_request", "category", "category TEXT NULL")
        _ensure_sqlite_column(
            con,
            "hr_escalation_request",
            "assigned_to_employee_id",
            "assigned_to_employee_id INTEGER NULL",
        )
        _ensure_sqlite_column(
            con, "hr_escalation_request", "assigned_to_email", "assigned_to_email TEXT NULL"
        )
        _ensure_sqlite_column(
            con, "hr_escalation_request", "agent_suggestion", "agent_suggestion TEXT NULL"
        )
        _ensure_sqlite_column(
            con,
            "hr_escalation_request",
            "last_message_to_requester",
            "last_message_to_requester TEXT NULL",
        )
        _ensure_sqlite_column(
            con, "hr_escalation_request", "last_message_at", "last_message_at TEXT NULL"
        )
        _ensure_sqlite_column(
            con,
            "hr_escalation_request",
            "escalation_level",
            "escalation_level INTEGER NOT NULL DEFAULT 1",
        )

        existing = (
            con.execute(text("SELECT COUNT(*) AS c FROM employee;"))
            .mappings()
            .one()["c"]
        )
        if existing > 0:
            return

        # ============================================================================
        # EMPLOYEES (50+ employees across multiple departments and locations)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO employee VALUES
          -- Executive Team
          (100,'Jordan Lee','Jordan','jordan.lee@acme.com','CEO','Executive','Berlin','2018-03-12','ACTIVE',NULL,'CC-EXEC'),
          (101,'Victoria Adams','Victoria','victoria.adams@acme.com','COO','Executive','Berlin','2018-09-15','ACTIVE',100,'CC-EXEC'),
          (102,'Richard Chen','Richard','richard.chen@acme.com','CFO','Executive','Berlin','2019-01-20','ACTIVE',100,'CC-EXEC'),
          (103,'Amanda Foster','Amanda','amanda.foster@acme.com','CTO','Executive','Berlin','2019-03-01','ACTIVE',100,'CC-EXEC'),

          -- HR Department
          (110,'Mina Patel','Mina','mina.patel@acme.com','Head of People','HR','Berlin','2019-06-01','ACTIVE',101,'CC-HR'),
          (111,'Lisa Chen','Lisa','lisa.chen@acme.com','HR Business Partner','HR','Berlin','2022-03-15','ACTIVE',110,'CC-HR'),
          (112,'James Wilson','James','james.wilson@acme.com','Talent Acquisition Lead','HR','Berlin','2021-05-10','ACTIVE',110,'CC-HR'),
          (113,'Emily Rodriguez','Emily','emily.rodriguez@acme.com','HR Coordinator','HR','Munich','2023-08-01','ACTIVE',110,'CC-HR'),
          (114,'Daniel Park','Daniel','daniel.park@acme.com','Learning & Development Specialist','HR','Berlin','2022-11-15','ACTIVE',110,'CC-HR'),
          (115,'Sarah Mitchell','Sarah','sarah.mitchell@acme.com','Recruiter','HR','Hamburg','2024-03-01','ACTIVE',112,'CC-HR'),

          -- Finance Department
          (120,'Tobias Klein','Tobias','tobias.klein@acme.com','Finance Director','Finance','Munich','2020-02-17','ACTIVE',102,'CC-FIN'),
          (121,'Maria Garcia','Maria','maria.garcia@acme.com','Senior Financial Analyst','Finance','Munich','2023-01-09','ACTIVE',120,'CC-FIN'),
          (122,'Benjamin Scott','Benjamin','benjamin.scott@acme.com','Controller','Finance','Munich','2021-07-01','ACTIVE',120,'CC-FIN'),
          (123,'Natalie Hughes','Natalie','natalie.hughes@acme.com','Accounts Payable Specialist','Finance','Munich','2022-04-18','ACTIVE',122,'CC-FIN'),
          (124,'Kevin O''Brien','Kevin','kevin.obrien@acme.com','Financial Analyst','Finance','Berlin','2023-06-12','ACTIVE',120,'CC-FIN'),
          (125,'Rachel Green','Rachel','rachel.green@acme.com','Payroll Administrator','Finance','Munich','2024-01-15','ACTIVE',122,'CC-FIN'),

          -- Engineering Department - Backend Team
          (200,'Sam Nguyen','Sam','sam.nguyen@acme.com','Engineering Manager','Engineering','Berlin','2021-04-05','ACTIVE',103,'CC-ENG'),
          (201,'Alex Kim','Alex','alex.kim@acme.com','Software Engineer','Engineering','Berlin','2022-01-10','ACTIVE',200,'CC-ENG'),
          (202,'Priya Shah','Priya','priya.shah@acme.com','Data Engineer','Engineering','Berlin','2023-09-18','ACTIVE',200,'CC-ENG'),
          (203,'Marcus Johnson','Marcus','marcus.johnson@acme.com','Senior Software Engineer','Engineering','Berlin','2021-08-23','ACTIVE',200,'CC-ENG'),
          (204,'Jennifer Liu','Jennifer','jennifer.liu@acme.com','Staff Engineer','Engineering','Berlin','2020-06-15','ACTIVE',200,'CC-ENG'),
          (205,'Michael Brown','Michael','michael.brown@acme.com','Software Engineer','Engineering','Berlin','2023-02-01','ACTIVE',200,'CC-ENG'),
          (206,'Aisha Hassan','Aisha','aisha.hassan@acme.com','Junior Software Engineer','Engineering','Berlin','2024-07-01','ACTIVE',203,'CC-ENG'),
          (207,'Thomas Mueller','Thomas','thomas.mueller@acme.com','DevOps Engineer','Engineering','Berlin','2022-09-01','ACTIVE',200,'CC-ENG'),

          -- Engineering Department - Frontend Team
          (210,'Olivia Wang','Olivia','olivia.wang@acme.com','Frontend Lead','Engineering','Berlin','2020-11-01','ACTIVE',103,'CC-ENG'),
          (211,'David Kim','David','david.kim@acme.com','Senior Frontend Engineer','Engineering','Berlin','2021-03-15','ACTIVE',210,'CC-ENG'),
          (212,'Emma Thompson','Emma','emma.thompson@acme.com','Frontend Engineer','Engineering','Berlin','2022-08-01','ACTIVE',210,'CC-ENG'),
          (213,'Lucas Santos','Lucas','lucas.santos@acme.com','UI/UX Engineer','Engineering','Berlin','2023-04-01','ACTIVE',210,'CC-ENG'),
          (214,'Nina Andersson','Nina','nina.andersson@acme.com','Frontend Engineer','Engineering','Berlin','2024-02-15','ACTIVE',210,'CC-ENG'),

          -- Engineering Department - Data Team
          (220,'Robert Taylor','Robert','robert.taylor@acme.com','Data Science Manager','Engineering','Berlin','2021-01-15','ACTIVE',103,'CC-ENG'),
          (221,'Sophia Martinez','Sophia','sophia.martinez@acme.com','Senior Data Scientist','Engineering','Berlin','2021-09-01','ACTIVE',220,'CC-ENG'),
          (222,'William Jackson','William','william.jackson@acme.com','Data Scientist','Engineering','Munich','2022-05-01','ACTIVE',220,'CC-ENG'),
          (223,'Isabella Clark','Isabella','isabella.clark@acme.com','ML Engineer','Engineering','Berlin','2023-01-20','ACTIVE',220,'CC-ENG'),
          (224,'Ethan Davis','Ethan','ethan.davis@acme.com','Data Analyst','Engineering','Munich','2023-11-01','ACTIVE',220,'CC-ENG'),

          -- Sales Department
          (300,'Elena Rossi','Elena','elena.rossi@acme.com','VP of Sales','Sales','Hamburg','2021-07-19','ACTIVE',101,'CC-SALES'),
          (301,'Chris Wong','Chris','chris.wong@acme.com','Senior Account Executive','Sales','Hamburg','2022-11-14','ACTIVE',300,'CC-SALES'),
          (302,'Fatima Ali','Fatima','fatima.ali@acme.com','Sales Ops Manager','Sales','Hamburg','2024-02-01','ACTIVE',300,'CC-SALES'),
          (303,'Andrew Phillips','Andrew','andrew.phillips@acme.com','Account Executive','Sales','Hamburg','2023-03-15','ACTIVE',300,'CC-SALES'),
          (304,'Jessica Turner','Jessica','jessica.turner@acme.com','Account Executive','Sales','Munich','2022-06-01','ACTIVE',300,'CC-SALES'),
          (305,'Ryan Cooper','Ryan','ryan.cooper@acme.com','Sales Development Rep','Sales','Hamburg','2024-01-10','ACTIVE',302,'CC-SALES'),
          (306,'Michelle Lee','Michelle','michelle.lee@acme.com','Sales Development Rep','Sales','Hamburg','2024-05-01','ACTIVE',302,'CC-SALES'),
          (307,'Patrick O''Connor','Patrick','patrick.oconnor@acme.com','Enterprise Account Executive','Sales','Berlin','2021-11-01','ACTIVE',300,'CC-SALES'),

          -- Marketing Department
          (310,'Hannah Wright','Hannah','hannah.wright@acme.com','Marketing Director','Marketing','Berlin','2020-08-01','ACTIVE',101,'CC-MKT'),
          (311,'Jason Kim','Jason','jason.kim@acme.com','Content Marketing Manager','Marketing','Berlin','2021-10-15','ACTIVE',310,'CC-MKT'),
          (312,'Laura Bennett','Laura','laura.bennett@acme.com','Digital Marketing Specialist','Marketing','Berlin','2022-12-01','ACTIVE',310,'CC-MKT'),
          (313,'Oscar Fernandez','Oscar','oscar.fernandez@acme.com','Brand Manager','Marketing','Hamburg','2023-05-15','ACTIVE',310,'CC-MKT'),
          (314,'Grace Yang','Grace','grace.yang@acme.com','Marketing Coordinator','Marketing','Berlin','2024-03-20','ACTIVE',311,'CC-MKT'),

          -- IT Department
          (400,'Noah Fischer','Noah','noah.fischer@acme.com','IT Director','IT','Berlin','2020-10-26','ACTIVE',103,'CC-IT'),
          (401,'Sophie Brown','Sophie','sophie.brown@acme.com','IT Support Lead','IT','Berlin','2023-05-08','ACTIVE',400,'CC-IT'),
          (402,'Carlos Rivera','Carlos','carlos.rivera@acme.com','Systems Administrator','IT','Berlin','2021-08-15','ACTIVE',400,'CC-IT'),
          (403,'Amy Chen','Amy','amy.chen@acme.com','IT Support Specialist','IT','Munich','2022-02-01','ACTIVE',401,'CC-IT'),
          (404,'Brian Walsh','Brian','brian.walsh@acme.com','Security Engineer','IT','Berlin','2022-10-01','ACTIVE',400,'CC-IT'),
          (405,'Diana Kovacs','Diana','diana.kovacs@acme.com','IT Support Specialist','IT','Berlin','2024-06-01','ACTIVE',401,'CC-IT'),

          -- Customer Success Department
          (500,'Alexandra Stone','Alexandra','alexandra.stone@acme.com','Customer Success Director','Customer Success','Hamburg','2021-02-01','ACTIVE',101,'CC-CS'),
          (501,'Mark Stevens','Mark','mark.stevens@acme.com','Senior Customer Success Manager','Customer Success','Hamburg','2021-09-15','ACTIVE',500,'CC-CS'),
          (502,'Julia Hoffman','Julia','julia.hoffman@acme.com','Customer Success Manager','Customer Success','Hamburg','2022-07-01','ACTIVE',500,'CC-CS'),
          (503,'Peter Lindgren','Peter','peter.lindgren@acme.com','Customer Success Manager','Customer Success','Munich','2023-02-15','ACTIVE',500,'CC-CS'),
          (504,'Chloe Martin','Chloe','chloe.martin@acme.com','Customer Support Specialist','Customer Success','Hamburg','2023-10-01','ACTIVE',501,'CC-CS'),
          (505,'Nathan Brooks','Nathan','nathan.brooks@acme.com','Customer Support Specialist','Customer Success','Berlin','2024-04-01','ACTIVE',501,'CC-CS'),

          -- Legal & Compliance
          (600,'Margaret Thompson','Margaret','margaret.thompson@acme.com','General Counsel','Legal','Berlin','2020-01-15','ACTIVE',100,'CC-LEGAL'),
          (601,'Steven Clarke','Steven','steven.clarke@acme.com','Corporate Counsel','Legal','Berlin','2022-03-01','ACTIVE',600,'CC-LEGAL'),
          (602,'Rebecca Moore','Rebecca','rebecca.moore@acme.com','Compliance Manager','Legal','Berlin','2023-07-15','ACTIVE',600,'CC-LEGAL');
        """
            )
        )

        # ============================================================================
        # IDENTITY MAP (maps email to employee_id)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO identity_map VALUES
          -- Executive
          ('jordan.lee@acme.com',100),
          ('victoria.adams@acme.com',101),
          ('richard.chen@acme.com',102),
          ('amanda.foster@acme.com',103),
          -- HR
          ('mina.patel@acme.com',110),
          ('lisa.chen@acme.com',111),
          ('james.wilson@acme.com',112),
          ('emily.rodriguez@acme.com',113),
          ('daniel.park@acme.com',114),
          ('sarah.mitchell@acme.com',115),
          -- Finance
          ('tobias.klein@acme.com',120),
          ('maria.garcia@acme.com',121),
          ('benjamin.scott@acme.com',122),
          ('natalie.hughes@acme.com',123),
          ('kevin.obrien@acme.com',124),
          ('rachel.green@acme.com',125),
          -- Engineering - Backend
          ('sam.nguyen@acme.com',200),
          ('alex.kim@acme.com',201),
          ('priya.shah@acme.com',202),
          ('marcus.johnson@acme.com',203),
          ('jennifer.liu@acme.com',204),
          ('michael.brown@acme.com',205),
          ('aisha.hassan@acme.com',206),
          ('thomas.mueller@acme.com',207),
          -- Engineering - Frontend
          ('olivia.wang@acme.com',210),
          ('david.kim@acme.com',211),
          ('emma.thompson@acme.com',212),
          ('lucas.santos@acme.com',213),
          ('nina.andersson@acme.com',214),
          -- Engineering - Data
          ('robert.taylor@acme.com',220),
          ('sophia.martinez@acme.com',221),
          ('william.jackson@acme.com',222),
          ('isabella.clark@acme.com',223),
          ('ethan.davis@acme.com',224),
          -- Sales
          ('elena.rossi@acme.com',300),
          ('chris.wong@acme.com',301),
          ('fatima.ali@acme.com',302),
          ('andrew.phillips@acme.com',303),
          ('jessica.turner@acme.com',304),
          ('ryan.cooper@acme.com',305),
          ('michelle.lee@acme.com',306),
          ('patrick.oconnor@acme.com',307),
          -- Marketing
          ('hannah.wright@acme.com',310),
          ('jason.kim@acme.com',311),
          ('laura.bennett@acme.com',312),
          ('oscar.fernandez@acme.com',313),
          ('grace.yang@acme.com',314),
          -- IT
          ('noah.fischer@acme.com',400),
          ('sophie.brown@acme.com',401),
          ('carlos.rivera@acme.com',402),
          ('amy.chen@acme.com',403),
          ('brian.walsh@acme.com',404),
          ('diana.kovacs@acme.com',405),
          -- Customer Success
          ('alexandra.stone@acme.com',500),
          ('mark.stevens@acme.com',501),
          ('julia.hoffman@acme.com',502),
          ('peter.lindgren@acme.com',503),
          ('chloe.martin@acme.com',504),
          ('nathan.brooks@acme.com',505),
          -- Legal
          ('margaret.thompson@acme.com',600),
          ('steven.clarke@acme.com',601),
          ('rebecca.moore@acme.com',602);
        """
            )
        )

        # ============================================================================
        # MANAGER REPORTS (who reports to whom)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO manager_reports VALUES
          -- CEO direct reports
          (100,101),(100,102),(100,103),(100,600),
          -- COO direct reports
          (101,110),(101,300),(101,310),(101,500),
          -- CFO direct reports
          (102,120),
          -- CTO direct reports
          (103,200),(103,210),(103,220),(103,400),
          -- HR
          (110,111),(110,112),(110,113),(110,114),
          (112,115),
          -- Finance
          (120,121),(120,122),(120,124),
          (122,123),(122,125),
          -- Engineering - Backend
          (200,201),(200,202),(200,203),(200,204),(200,205),(200,207),
          (203,206),
          -- Engineering - Frontend
          (210,211),(210,212),(210,213),(210,214),
          -- Engineering - Data
          (220,221),(220,222),(220,223),(220,224),
          -- Sales
          (300,301),(300,302),(300,303),(300,304),(300,307),
          (302,305),(302,306),
          -- Marketing
          (310,311),(310,312),(310,313),
          (311,314),
          -- IT
          (400,401),(400,402),(400,404),
          (401,403),(401,405),
          -- Customer Success
          (500,501),(500,502),(500,503),
          (501,504),(501,505),
          -- Legal
          (600,601),(600,602);
        """
            )
        )

        # ============================================================================
        # ROLE MAP (application roles for access control)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO app_role_map VALUES
          -- HR Role
          ('jordan.lee@acme.com','HR'),
          ('mina.patel@acme.com','HR'),
          ('lisa.chen@acme.com','HR'),
          ('james.wilson@acme.com','HR'),
          ('emily.rodriguez@acme.com','HR'),
          ('daniel.park@acme.com','HR'),
          ('sarah.mitchell@acme.com','EMPLOYEE'),
          -- Finance Role
          ('richard.chen@acme.com','FINANCE'),
          ('tobias.klein@acme.com','FINANCE'),
          ('maria.garcia@acme.com','FINANCE'),
          ('benjamin.scott@acme.com','FINANCE'),
          ('natalie.hughes@acme.com','EMPLOYEE'),
          ('kevin.obrien@acme.com','EMPLOYEE'),
          ('rachel.green@acme.com','EMPLOYEE'),
          -- Manager Role
          ('victoria.adams@acme.com','MANAGER'),
          ('amanda.foster@acme.com','MANAGER'),
          ('sam.nguyen@acme.com','MANAGER'),
          ('olivia.wang@acme.com','MANAGER'),
          ('robert.taylor@acme.com','MANAGER'),
          ('elena.rossi@acme.com','MANAGER'),
          ('fatima.ali@acme.com','MANAGER'),
          ('hannah.wright@acme.com','MANAGER'),
          ('jason.kim@acme.com','MANAGER'),
          ('noah.fischer@acme.com','MANAGER'),
          ('sophie.brown@acme.com','MANAGER'),
          ('alexandra.stone@acme.com','MANAGER'),
          ('mark.stevens@acme.com','MANAGER'),
          ('margaret.thompson@acme.com','MANAGER'),
          ('marcus.johnson@acme.com','MANAGER'),
          -- Employee Role
          ('alex.kim@acme.com','EMPLOYEE'),
          ('priya.shah@acme.com','EMPLOYEE'),
          ('jennifer.liu@acme.com','EMPLOYEE'),
          ('michael.brown@acme.com','EMPLOYEE'),
          ('aisha.hassan@acme.com','EMPLOYEE'),
          ('thomas.mueller@acme.com','EMPLOYEE'),
          ('david.kim@acme.com','EMPLOYEE'),
          ('emma.thompson@acme.com','EMPLOYEE'),
          ('lucas.santos@acme.com','EMPLOYEE'),
          ('nina.andersson@acme.com','EMPLOYEE'),
          ('sophia.martinez@acme.com','EMPLOYEE'),
          ('william.jackson@acme.com','EMPLOYEE'),
          ('isabella.clark@acme.com','EMPLOYEE'),
          ('ethan.davis@acme.com','EMPLOYEE'),
          ('chris.wong@acme.com','EMPLOYEE'),
          ('andrew.phillips@acme.com','EMPLOYEE'),
          ('jessica.turner@acme.com','EMPLOYEE'),
          ('ryan.cooper@acme.com','EMPLOYEE'),
          ('michelle.lee@acme.com','EMPLOYEE'),
          ('patrick.oconnor@acme.com','EMPLOYEE'),
          ('laura.bennett@acme.com','EMPLOYEE'),
          ('oscar.fernandez@acme.com','EMPLOYEE'),
          ('grace.yang@acme.com','EMPLOYEE'),
          ('carlos.rivera@acme.com','EMPLOYEE'),
          ('amy.chen@acme.com','EMPLOYEE'),
          ('brian.walsh@acme.com','EMPLOYEE'),
          ('diana.kovacs@acme.com','EMPLOYEE'),
          ('julia.hoffman@acme.com','EMPLOYEE'),
          ('peter.lindgren@acme.com','EMPLOYEE'),
          ('chloe.martin@acme.com','EMPLOYEE'),
          ('nathan.brooks@acme.com','EMPLOYEE'),
          ('steven.clarke@acme.com','EMPLOYEE'),
          ('rebecca.moore@acme.com','EMPLOYEE');
        """
            )
        )

        # ============================================================================
        # HOLIDAY ENTITLEMENTS (2025 + 2026 for all employees)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO holiday_entitlement VALUES
          -- Executive (30 days)
          (100,2025,30,0),(100,2026,30,2),
          (101,2025,30,0),(101,2026,30,0),
          (102,2025,30,0),(102,2026,30,5),
          (103,2025,30,0),(103,2026,30,3),
          -- HR
          (110,2025,30,0),(110,2026,30,3),
          (111,2025,28,0),(111,2026,28,0),
          (112,2025,28,0),(112,2026,28,2),
          (113,2025,28,0),(113,2026,28,0),
          (114,2025,28,0),(114,2026,28,1),
          (115,2025,28,0),(115,2026,28,0),
          -- Finance
          (120,2025,30,0),(120,2026,30,1),
          (121,2025,28,0),(121,2026,28,0),
          (122,2025,28,0),(122,2026,28,3),
          (123,2025,28,0),(123,2026,28,0),
          (124,2025,28,0),(124,2026,28,0),
          (125,2025,28,0),(125,2026,28,0),
          -- Engineering - Backend
          (200,2025,30,0),(200,2026,30,0),
          (201,2025,28,0),(201,2026,28,2),
          (202,2025,28,0),(202,2026,28,0),
          (203,2025,28,0),(203,2026,28,5),
          (204,2025,28,0),(204,2026,28,4),
          (205,2025,28,0),(205,2026,28,0),
          (206,2025,28,0),(206,2026,28,0),
          (207,2025,28,0),(207,2026,28,2),
          -- Engineering - Frontend
          (210,2025,30,0),(210,2026,30,0),
          (211,2025,28,0),(211,2026,28,3),
          (212,2025,28,0),(212,2026,28,0),
          (213,2025,28,0),(213,2026,28,1),
          (214,2025,28,0),(214,2026,28,0),
          -- Engineering - Data
          (220,2025,30,0),(220,2026,30,2),
          (221,2025,28,0),(221,2026,28,0),
          (222,2025,28,0),(222,2026,28,4),
          (223,2025,28,0),(223,2026,28,0),
          (224,2025,28,0),(224,2026,28,0),
          -- Sales
          (300,2025,30,0),(300,2026,30,0),
          (301,2025,28,0),(301,2026,28,0),
          (302,2025,28,0),(302,2026,28,0),
          (303,2025,28,0),(303,2026,28,2),
          (304,2025,28,0),(304,2026,28,3),
          (305,2025,28,0),(305,2026,28,0),
          (306,2025,28,0),(306,2026,28,0),
          (307,2025,28,0),(307,2026,28,5),
          -- Marketing
          (310,2025,30,0),(310,2026,30,1),
          (311,2025,28,0),(311,2026,28,0),
          (312,2025,28,0),(312,2026,28,2),
          (313,2025,28,0),(313,2026,28,0),
          (314,2025,28,0),(314,2026,28,0),
          -- IT
          (400,2025,30,0),(400,2026,30,3),
          (401,2025,28,0),(401,2026,28,0),
          (402,2025,28,0),(402,2026,28,2),
          (403,2025,28,0),(403,2026,28,1),
          (404,2025,28,0),(404,2026,28,0),
          (405,2025,28,0),(405,2026,28,0),
          -- Customer Success
          (500,2025,30,0),(500,2026,30,0),
          (501,2025,28,0),(501,2026,28,3),
          (502,2025,28,0),(502,2026,28,0),
          (503,2025,28,0),(503,2026,28,1),
          (504,2025,28,0),(504,2026,28,0),
          (505,2025,28,0),(505,2026,28,0),
          -- Legal
          (600,2025,30,0),(600,2026,30,5),
          (601,2025,28,0),(601,2026,28,2),
          (602,2025,28,0),(602,2026,28,0);
        """
            )
        )

        # ============================================================================
        # HOLIDAY REQUESTS (diverse set of requests across departments)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO holiday_request (request_id, employee_id, start_date, end_date, days, status, reason, requested_at, reviewed_by, reviewed_at, rejection_reason) VALUES
          -- Past approved requests (2025)
          (9001,201,'2025-12-23','2025-12-31',5,'APPROVED','Christmas holidays','2025-11-15 10:00:00',200,'2025-11-16 09:00:00',NULL),
          (9002,203,'2025-08-04','2025-08-15',10,'APPROVED','Summer vacation','2025-06-20 14:30:00',200,'2025-06-21 10:00:00',NULL),
          (9003,211,'2025-07-21','2025-07-25',5,'APPROVED','Family wedding','2025-06-01 09:00:00',210,'2025-06-02 11:00:00',NULL),
          (9004,301,'2025-09-01','2025-09-05',5,'APPROVED','Beach vacation','2025-07-15 16:00:00',300,'2025-07-16 08:30:00',NULL),
          (9005,401,'2025-10-27','2025-10-31',5,'APPROVED','Fall break','2025-09-15 11:00:00',400,'2025-09-16 10:00:00',NULL),
          (9006,221,'2025-11-24','2025-11-28',5,'APPROVED','Thanksgiving travel','2025-10-01 13:00:00',220,'2025-10-02 09:00:00',NULL),
          (9007,122,'2025-12-27','2025-12-31',3,'APPROVED','Year end break','2025-11-20 10:00:00',120,'2025-11-21 14:00:00',NULL),

          -- 2026 approved requests
          (9010,202,'2026-01-27','2026-01-31',5,'APPROVED','Personal travel','2026-01-05 14:30:00',200,'2026-01-06 10:00:00',NULL),
          (9011,200,'2026-01-27','2026-01-31',5,'APPROVED','Team offsite','2025-12-15 08:00:00',103,'2025-12-16 11:00:00',NULL),
          (9012,203,'2026-03-10','2026-03-14',5,'APPROVED','Spring break','2026-01-20 09:15:00',200,'2026-01-21 08:30:00',NULL),
          (9013,401,'2026-05-01','2026-05-02',2,'APPROVED','Long weekend','2026-01-10 15:00:00',400,'2026-01-11 09:00:00',NULL),
          (9014,211,'2026-04-06','2026-04-10',5,'APPROVED','Easter holiday','2026-02-15 10:00:00',210,'2026-02-16 09:00:00',NULL),
          (9015,304,'2026-02-23','2026-02-27',5,'APPROVED','Ski trip','2026-01-08 11:30:00',300,'2026-01-09 08:00:00',NULL),
          (9016,502,'2026-03-02','2026-03-06',5,'APPROVED','Conference + vacation','2026-01-15 09:00:00',500,'2026-01-16 10:00:00',NULL),
          (9017,113,'2026-04-20','2026-04-24',5,'APPROVED','Family visit','2026-02-01 14:00:00',110,'2026-02-02 11:00:00',NULL),
          (9018,312,'2026-03-16','2026-03-20',5,'APPROVED','Spring getaway','2026-01-25 10:00:00',310,'2026-01-26 09:00:00',NULL),
          (9019,207,'2026-02-16','2026-02-20',5,'APPROVED','Personal time','2026-01-05 09:00:00',200,'2026-01-06 08:00:00',NULL),
          (9020,404,'2026-05-18','2026-05-22',5,'APPROVED','Vacation','2026-03-01 10:00:00',400,'2026-03-02 09:00:00',NULL),

          -- Pending requests (2026)
          (9030,201,'2026-02-10','2026-02-14',5,'PENDING','Winter vacation','2026-01-10 10:02:00',NULL,NULL,NULL),
          (9031,302,'2026-03-18','2026-03-20',3,'PENDING','Doctor appointments','2026-01-12 16:30:00',NULL,NULL,NULL),
          (9032,301,'2026-04-14','2026-04-18',5,'PENDING','Easter vacation','2026-01-22 11:00:00',NULL,NULL,NULL),
          (9033,205,'2026-06-01','2026-06-12',10,'PENDING','Summer travel','2026-01-18 09:00:00',NULL,NULL,NULL),
          (9034,212,'2026-05-25','2026-05-29',5,'PENDING','Wedding attendance','2026-01-20 14:00:00',NULL,NULL,NULL),
          (9035,222,'2026-07-06','2026-07-17',10,'PENDING','Family vacation','2026-01-22 10:00:00',NULL,NULL,NULL),
          (9036,303,'2026-04-27','2026-05-01',5,'PENDING','Long weekend trip','2026-01-24 11:00:00',NULL,NULL,NULL),
          (9037,403,'2026-06-15','2026-06-19',5,'PENDING','Personal time','2026-01-21 09:30:00',NULL,NULL,NULL),
          (9038,501,'2026-08-03','2026-08-14',10,'PENDING','Summer holiday','2026-01-23 10:00:00',NULL,NULL,NULL),
          (9039,123,'2026-05-11','2026-05-15',5,'PENDING','Vacation','2026-01-19 15:00:00',NULL,NULL,NULL),
          (9040,213,'2026-07-20','2026-07-31',10,'PENDING','Extended vacation','2026-01-25 08:00:00',NULL,NULL,NULL),
          (9041,306,'2026-03-23','2026-03-27',5,'PENDING','Spring break','2026-01-24 16:00:00',NULL,NULL,NULL),
          (9042,504,'2026-04-06','2026-04-10',5,'PENDING','Easter holiday','2026-01-20 11:00:00',NULL,NULL,NULL),
          (9043,314,'2026-05-04','2026-05-08',5,'PENDING','Personal travel','2026-01-22 09:00:00',NULL,NULL,NULL),
          (9044,602,'2026-06-22','2026-06-26',5,'PENDING','Family event','2026-01-23 14:00:00',NULL,NULL,NULL),

          -- Rejected requests
          (9050,305,'2025-12-22','2026-01-02',10,'REJECTED','Holiday break','2025-11-01 09:00:00',302,'2025-11-02 10:00:00','Coverage needed during peak sales period'),
          (9051,405,'2025-11-25','2025-11-28',3,'REJECTED','Thanksgiving','2025-10-15 11:00:00',401,'2025-10-16 09:00:00','System upgrade scheduled - all IT staff needed'),
          (9052,206,'2025-12-20','2025-12-31',8,'REJECTED','Holiday travel','2025-11-10 10:00:00',203,'2025-11-11 14:00:00','Project deadline - please reschedule'),

          -- Cancelled requests
          (9060,224,'2026-02-02','2026-02-06',5,'CANCELLED','Personal time','2026-01-05 09:00:00',NULL,NULL,NULL),
          (9061,313,'2026-03-09','2026-03-13',5,'CANCELLED','Travel plans','2026-01-10 10:00:00',NULL,NULL,NULL);
        """
            )
        )

        # ============================================================================
        # COMPENSATION (salary, bonus, equity for all employees)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO compensation VALUES
          -- Executive
          (100,'EUR',280000,50,75000,'2025-04-01','2026-04-01'),
          (101,'EUR',220000,40,50000,'2025-09-15','2026-09-15'),
          (102,'EUR',230000,40,55000,'2025-01-20','2026-01-20'),
          (103,'EUR',240000,40,60000,'2025-03-01','2026-03-01'),
          -- HR
          (110,'EUR',125000,25,12000,'2025-06-01','2026-06-01'),
          (111,'EUR',78000,15,2500,'2025-03-15','2026-03-15'),
          (112,'EUR',85000,15,3000,'2025-05-10','2026-05-10'),
          (113,'EUR',62000,10,1000,'2025-08-01','2026-08-01'),
          (114,'EUR',72000,12,1500,'2025-11-15','2026-11-15'),
          (115,'EUR',55000,10,0,'2025-03-01','2026-03-01'),
          -- Finance
          (120,'EUR',140000,25,18000,'2025-02-17','2026-02-17'),
          (121,'EUR',75000,12,2000,'2026-01-09','2027-01-09'),
          (122,'EUR',95000,15,5000,'2025-07-01','2026-07-01'),
          (123,'EUR',58000,10,500,'2025-04-18','2026-04-18'),
          (124,'EUR',68000,10,1000,'2025-06-12','2026-06-12'),
          (125,'EUR',52000,8,0,'2025-01-15','2026-01-15'),
          -- Engineering - Backend
          (200,'EUR',115000,18,10000,'2025-04-05','2026-04-05'),
          (201,'EUR',85000,12,2500,'2026-01-10','2027-01-10'),
          (202,'EUR',82000,12,2000,'2025-09-18','2026-09-18'),
          (203,'EUR',98000,15,6000,'2025-08-23','2026-08-23'),
          (204,'EUR',125000,18,12000,'2025-06-15','2026-06-15'),
          (205,'EUR',75000,10,1500,'2025-02-01','2026-02-01'),
          (206,'EUR',58000,8,500,'2025-07-01','2026-07-01'),
          (207,'EUR',88000,12,3000,'2025-09-01','2026-09-01'),
          -- Engineering - Frontend
          (210,'EUR',118000,18,11000,'2025-11-01','2026-11-01'),
          (211,'EUR',95000,15,5500,'2025-03-15','2026-03-15'),
          (212,'EUR',78000,12,2000,'2025-08-01','2026-08-01'),
          (213,'EUR',72000,10,1500,'2025-04-01','2026-04-01'),
          (214,'EUR',68000,10,1000,'2025-02-15','2026-02-15'),
          -- Engineering - Data
          (220,'EUR',130000,20,15000,'2025-01-15','2026-01-15'),
          (221,'EUR',105000,15,7000,'2025-09-01','2026-09-01'),
          (222,'EUR',85000,12,3500,'2025-05-01','2026-05-01'),
          (223,'EUR',92000,12,4000,'2025-01-20','2026-01-20'),
          (224,'EUR',65000,10,1000,'2025-11-01','2026-11-01'),
          -- Sales
          (300,'EUR',135000,30,14000,'2025-07-19','2026-07-19'),
          (301,'EUR',80000,25,2500,'2025-11-14','2026-11-14'),
          (302,'EUR',78000,15,2000,'2025-02-01','2026-02-01'),
          (303,'EUR',72000,25,1500,'2025-03-15','2026-03-15'),
          (304,'EUR',75000,25,2000,'2025-06-01','2026-06-01'),
          (305,'EUR',52000,20,0,'2025-01-10','2026-01-10'),
          (306,'EUR',50000,20,0,'2025-05-01','2026-05-01'),
          (307,'EUR',110000,30,8000,'2025-11-01','2026-11-01'),
          -- Marketing
          (310,'EUR',120000,20,10000,'2025-08-01','2026-08-01'),
          (311,'EUR',82000,15,3000,'2025-10-15','2026-10-15'),
          (312,'EUR',68000,12,1500,'2025-12-01','2026-12-01'),
          (313,'EUR',75000,12,2000,'2025-05-15','2026-05-15'),
          (314,'EUR',55000,10,500,'2025-03-20','2026-03-20'),
          -- IT
          (400,'EUR',115000,15,8000,'2025-10-26','2026-10-26'),
          (401,'EUR',75000,12,2000,'2025-05-08','2026-05-08'),
          (402,'EUR',78000,12,2500,'2025-08-15','2026-08-15'),
          (403,'EUR',58000,10,500,'2025-02-01','2026-02-01'),
          (404,'EUR',95000,15,5000,'2025-10-01','2026-10-01'),
          (405,'EUR',52000,8,0,'2025-06-01','2026-06-01'),
          -- Customer Success
          (500,'EUR',115000,20,9000,'2025-02-01','2026-02-01'),
          (501,'EUR',82000,18,3500,'2025-09-15','2026-09-15'),
          (502,'EUR',72000,15,2000,'2025-07-01','2026-07-01'),
          (503,'EUR',70000,15,1500,'2025-02-15','2026-02-15'),
          (504,'EUR',52000,12,500,'2025-10-01','2026-10-01'),
          (505,'EUR',50000,12,0,'2025-04-01','2026-04-01'),
          -- Legal
          (600,'EUR',180000,25,25000,'2025-01-15','2026-01-15'),
          (601,'EUR',110000,18,8000,'2025-03-01','2026-03-01'),
          (602,'EUR',85000,15,3500,'2025-07-15','2026-07-15');
        """
            )
        )

        # ============================================================================
        # SALARY HISTORY (detailed history for employees with tenure)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO salary_history VALUES
          -- Alex Kim (201) - Software Engineer
          (1,201,'2022-01-10',75000,'EUR','Initial hire',NULL),
          (2,201,'2023-01-10',78000,'EUR','Annual review',4.0),
          (3,201,'2024-01-10',82000,'EUR','Annual review',5.1),
          (4,201,'2025-01-10',85000,'EUR','Annual review',3.7),

          -- Priya Shah (202) - Data Engineer
          (5,202,'2023-09-18',75000,'EUR','Initial hire',NULL),
          (6,202,'2024-09-18',79000,'EUR','Annual review',5.3),
          (7,202,'2025-09-18',82000,'EUR','Annual review',3.8),

          -- Marcus Johnson (203) - Senior Software Engineer
          (8,203,'2021-08-23',78000,'EUR','Initial hire',NULL),
          (9,203,'2022-08-23',85000,'EUR','Promotion to Mid-level',9.0),
          (10,203,'2023-08-23',92000,'EUR','Annual review + Promotion to Senior',8.2),
          (11,203,'2024-08-23',98000,'EUR','Annual review',6.5),

          -- Sam Nguyen (200) - Engineering Manager
          (12,200,'2021-04-05',88000,'EUR','Initial hire',NULL),
          (13,200,'2022-04-05',95000,'EUR','Annual review',8.0),
          (14,200,'2023-04-05',105000,'EUR','Promotion to Manager',10.5),
          (15,200,'2024-04-05',110000,'EUR','Annual review',4.8),
          (16,200,'2025-04-05',115000,'EUR','Annual review',4.5),

          -- Jennifer Liu (204) - Staff Engineer
          (17,204,'2020-06-15',95000,'EUR','Initial hire',NULL),
          (18,204,'2021-06-15',102000,'EUR','Annual review',7.4),
          (19,204,'2022-06-15',110000,'EUR','Promotion to Staff',7.8),
          (20,204,'2023-06-15',118000,'EUR','Annual review',7.3),
          (21,204,'2024-06-15',125000,'EUR','Annual review',5.9),

          -- David Kim (211) - Senior Frontend Engineer
          (22,211,'2021-03-15',72000,'EUR','Initial hire',NULL),
          (23,211,'2022-03-15',78000,'EUR','Annual review',8.3),
          (24,211,'2023-03-15',85000,'EUR','Promotion to Senior',9.0),
          (25,211,'2024-03-15',92000,'EUR','Annual review',8.2),
          (26,211,'2025-03-15',95000,'EUR','Annual review',3.3),

          -- Sophia Martinez (221) - Senior Data Scientist
          (27,221,'2021-09-01',85000,'EUR','Initial hire',NULL),
          (28,221,'2022-09-01',92000,'EUR','Annual review',8.2),
          (29,221,'2023-09-01',98000,'EUR','Promotion to Senior',6.5),
          (30,221,'2024-09-01',105000,'EUR','Annual review',7.1),

          -- Chris Wong (301) - Senior Account Executive
          (31,301,'2022-11-14',62000,'EUR','Initial hire',NULL),
          (32,301,'2023-11-14',70000,'EUR','Annual review + exceeded quota',12.9),
          (33,301,'2024-11-14',80000,'EUR','Promotion to Senior AE',14.3),

          -- Elena Rossi (300) - VP of Sales
          (34,300,'2021-07-19',95000,'EUR','Initial hire as Sales Manager',NULL),
          (35,300,'2022-07-19',105000,'EUR','Annual review',10.5),
          (36,300,'2023-07-19',120000,'EUR','Promotion to VP',14.3),
          (37,300,'2024-07-19',135000,'EUR','Annual review',12.5),

          -- Mina Patel (110) - Head of People
          (38,110,'2019-06-01',85000,'EUR','Initial hire',NULL),
          (39,110,'2020-06-01',92000,'EUR','Annual review',8.2),
          (40,110,'2021-06-01',100000,'EUR','Annual review',8.7),
          (41,110,'2022-06-01',110000,'EUR','Promotion to Head',10.0),
          (42,110,'2023-06-01',118000,'EUR','Annual review',7.3),
          (43,110,'2024-06-01',125000,'EUR','Annual review',5.9),

          -- Tobias Klein (120) - Finance Director
          (44,120,'2020-02-17',105000,'EUR','Initial hire',NULL),
          (45,120,'2021-02-17',115000,'EUR','Annual review',9.5),
          (46,120,'2022-02-17',125000,'EUR','Promotion to Director',8.7),
          (47,120,'2023-02-17',132000,'EUR','Annual review',5.6),
          (48,120,'2024-02-17',140000,'EUR','Annual review',6.1),

          -- Robert Taylor (220) - Data Science Manager
          (49,220,'2021-01-15',100000,'EUR','Initial hire',NULL),
          (50,220,'2022-01-15',110000,'EUR','Annual review',10.0),
          (51,220,'2023-01-15',120000,'EUR','Promotion to Manager',9.1),
          (52,220,'2024-01-15',130000,'EUR','Annual review',8.3),

          -- Hannah Wright (310) - Marketing Director
          (53,310,'2020-08-01',90000,'EUR','Initial hire',NULL),
          (54,310,'2021-08-01',98000,'EUR','Annual review',8.9),
          (55,310,'2022-08-01',108000,'EUR','Promotion to Director',10.2),
          (56,310,'2023-08-01',115000,'EUR','Annual review',6.5),
          (57,310,'2024-08-01',120000,'EUR','Annual review',4.3),

          -- Noah Fischer (400) - IT Director
          (58,400,'2020-10-26',85000,'EUR','Initial hire',NULL),
          (59,400,'2021-10-26',92000,'EUR','Annual review',8.2),
          (60,400,'2022-10-26',100000,'EUR','Promotion to Director',8.7),
          (61,400,'2023-10-26',108000,'EUR','Annual review',8.0),
          (62,400,'2024-10-26',115000,'EUR','Annual review',6.5),

          -- Patrick O''Connor (307) - Enterprise Account Executive
          (63,307,'2021-11-01',85000,'EUR','Initial hire',NULL),
          (64,307,'2022-11-01',95000,'EUR','Exceeded quota',11.8),
          (65,307,'2023-11-01',105000,'EUR','Annual review + top performer',10.5),
          (66,307,'2024-11-01',110000,'EUR','Annual review',4.8),

          -- Brian Walsh (404) - Security Engineer
          (67,404,'2022-10-01',78000,'EUR','Initial hire',NULL),
          (68,404,'2023-10-01',85000,'EUR','Annual review + certifications',9.0),
          (69,404,'2024-10-01',95000,'EUR','Market adjustment + review',11.8);
        """
            )
        )

        # ============================================================================
        # FINANCE COST CENTER ACCESS (who can see what cost centers)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO finance_cost_center_access VALUES
          -- CFO has access to all
          ('richard.chen@acme.com','CC-EXEC'),
          ('richard.chen@acme.com','CC-HR'),
          ('richard.chen@acme.com','CC-FIN'),
          ('richard.chen@acme.com','CC-ENG'),
          ('richard.chen@acme.com','CC-SALES'),
          ('richard.chen@acme.com','CC-MKT'),
          ('richard.chen@acme.com','CC-IT'),
          ('richard.chen@acme.com','CC-CS'),
          ('richard.chen@acme.com','CC-LEGAL'),
          -- Finance Director has most access
          ('tobias.klein@acme.com','CC-HR'),
          ('tobias.klein@acme.com','CC-FIN'),
          ('tobias.klein@acme.com','CC-ENG'),
          ('tobias.klein@acme.com','CC-SALES'),
          ('tobias.klein@acme.com','CC-MKT'),
          ('tobias.klein@acme.com','CC-IT'),
          ('tobias.klein@acme.com','CC-CS'),
          -- Senior Financial Analyst - limited access
          ('maria.garcia@acme.com','CC-ENG'),
          ('maria.garcia@acme.com','CC-SALES'),
          ('maria.garcia@acme.com','CC-MKT'),
          -- Controller - operational departments
          ('benjamin.scott@acme.com','CC-FIN'),
          ('benjamin.scott@acme.com','CC-IT'),
          ('benjamin.scott@acme.com','CC-CS');
        """
            )
        )

        # ============================================================================
        # COMPANY POLICIES (comprehensive policy library)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO company_policy VALUES
          (1,'Remote Work Policy','Work Arrangements','Guidelines for working remotely including eligibility, equipment, and expectations.',
           'ACME Remote Work Policy\n\n1. Eligibility: All employees after 3 months of employment.\n2. Equipment: Company provides laptop and monitor.\n3. Expectations: Core hours 10am-4pm local time.\n4. Communication: Must be reachable via Slack during core hours.\n5. Office days: Minimum 2 days per week in office for collaboration.\n6. Approval: Manager approval required for regular remote work arrangements.\n7. International remote work: Requires HR and Legal approval, max 4 weeks per year.',
           '2024-01-01','2025-06-15','ACTIVE'),

          (2,'Annual Leave Policy','Time Off','Standard annual leave entitlements and booking procedures.',
           'ACME Annual Leave Policy\n\n1. Entitlement: 28 days for standard employees, 30 days for managers and above.\n2. Carry over: Maximum 5 days can be carried to next year.\n3. Booking: Submit requests at least 2 weeks in advance.\n4. Approval: Manager approval required.\n5. Peak periods: December holidays require 4 weeks notice.\n6. Unused leave: Must be used by end of Q1 next year.\n7. Probation: Full entitlement available from day 1, but limited to 2 days per month during probation.',
           '2023-01-01','2025-01-10','ACTIVE'),

          (3,'Expense Policy','Finance','Guidelines for business expense claims and reimbursement.',
           'ACME Expense Policy\n\n1. Eligible expenses: Travel, meals during business trips, client entertainment.\n2. Limits: Meals up to 50 EUR per day, hotels up to 200 EUR per night in Germany, 250 EUR internationally.\n3. Approval: Manager approval required for expenses over 100 EUR, Director for over 1000 EUR.\n4. Receipts: Required for all expenses over 25 EUR.\n5. Submission: Within 30 days of expense.\n6. Reimbursement: Processed within 14 days of approval.\n7. Corporate card: Available for frequent travelers upon manager request.',
           '2024-03-01','2025-03-01','ACTIVE'),

          (4,'Parental Leave Policy','Time Off','Maternity, paternity, and adoption leave entitlements.',
           'ACME Parental Leave Policy\n\n1. Maternity leave: 14 weeks fully paid + up to 12 weeks at 50%.\n2. Paternity leave: 4 weeks fully paid.\n3. Adoption leave: Same as maternity/paternity based on primary caregiver status.\n4. Notification: Inform HR at least 3 months before expected date.\n5. Return to work: Phased return option available (50%, 75%, 100% over 4 weeks).\n6. Childcare support: Up to 500 EUR monthly subsidy for first 2 years.\n7. Flexible working: Parents can request flexible hours until child is 8 years old.',
           '2024-01-01','2025-01-01','ACTIVE'),

          (5,'Code of Conduct','Ethics','Expected standards of behavior and ethics for all employees.',
           'ACME Code of Conduct\n\n1. Integrity: Act honestly and ethically in all business dealings.\n2. Respect: Treat all colleagues, customers, and partners with respect.\n3. Confidentiality: Protect company and customer information.\n4. Conflicts of interest: Disclose any potential conflicts to your manager.\n5. Compliance: Follow all applicable laws and regulations.\n6. Reporting: Report any violations to HR or use anonymous hotline.\n7. Social media: Personal opinions must be clearly separated from company views.\n8. Anti-bribery: No gifts over 50 EUR value to/from business partners.',
           '2023-01-01','2024-06-01','ACTIVE'),

          (6,'Learning & Development Policy','Career','Professional development opportunities and training budget.',
           'ACME Learning & Development Policy\n\n1. Training budget: 2,000 EUR per employee per year, 3,500 EUR for managers.\n2. Conference attendance: Up to 2 conferences per year with manager approval.\n3. Certification: Company pays for job-relevant certifications + one retake.\n4. Study leave: Up to 5 days per year for exam preparation.\n5. Internal mobility: Encouraged to apply for internal positions after 12 months.\n6. Mentorship: Formal mentorship program available - request through HR.\n7. Language courses: 50% subsidy for business-relevant language learning.\n8. Online learning: Unlimited access to LinkedIn Learning and Udemy Business.',
           '2024-01-01','2025-01-15','ACTIVE'),

          (7,'Performance Review Policy','Career','Annual performance review process and timeline.',
           'ACME Performance Review Policy\n\n1. Review cycle: Annual reviews conducted in Q1 for the previous year.\n2. Self-assessment: Employees complete self-review by January 31.\n3. Manager review: Managers complete evaluations by February 15.\n4. Calibration: Department-level calibration sessions in late February.\n5. Feedback delivery: All reviews delivered by March 15.\n6. Rating scale: 1-5 scale (Needs Improvement to Exceptional).\n7. Development plan: Each employee creates a development plan with manager.\n8. Mid-year check-in: Informal progress review in July.',
           '2024-01-01','2025-02-01','ACTIVE'),

          (8,'Sick Leave Policy','Time Off','Guidelines for reporting illness and sick leave entitlements.',
           'ACME Sick Leave Policy\n\n1. Notification: Inform your manager before your normal start time.\n2. Documentation: Medical certificate required for absences over 3 consecutive days.\n3. Entitlement: Full pay for first 6 weeks of illness per year.\n4. Extended illness: After 6 weeks, statutory sick pay applies.\n5. Return to work: Manager check-in required after 5+ consecutive days.\n6. Mental health: Same provisions as physical illness, EAP support available.\n7. Chronic conditions: Reasonable adjustments available - discuss with HR.',
           '2023-06-01','2025-01-01','ACTIVE'),

          (9,'Information Security Policy','IT','Guidelines for protecting company and customer data.',
           'ACME Information Security Policy\n\n1. Passwords: Minimum 12 characters, changed every 90 days, no reuse.\n2. Two-factor: Required for all company systems.\n3. Device security: All devices must have encryption and screen lock.\n4. Data classification: Confidential, Internal, Public - handle accordingly.\n5. Clean desk: Lock screens, secure documents when away from desk.\n6. Reporting: Report security incidents to IT immediately.\n7. Personal devices: Not permitted for work data without MDM enrollment.\n8. Training: Annual security awareness training mandatory.',
           '2024-01-01','2025-06-01','ACTIVE'),

          (10,'Diversity & Inclusion Policy','Ethics','Commitment to diversity, equity, and inclusion.',
           'ACME Diversity & Inclusion Policy\n\n1. Equal opportunity: Hiring and promotion based solely on merit.\n2. Non-discrimination: Zero tolerance for discrimination of any kind.\n3. Harassment: Strict anti-harassment policy with clear reporting channels.\n4. Accommodation: Reasonable accommodations for disabilities.\n5. ERGs: Employee Resource Groups supported and funded by company.\n6. Training: Annual D&I training required for all employees.\n7. Pay equity: Annual audit to ensure pay equity across demographics.\n8. Reporting: Anonymous reporting channel for concerns.',
           '2023-01-01','2025-03-01','ACTIVE'),

          (11,'Travel Policy','Finance','Guidelines for business travel arrangements and reimbursement.',
           'ACME Travel Policy\n\n1. Booking: Use corporate travel portal for all bookings.\n2. Flights: Economy class for flights under 6 hours, business class over 6 hours.\n3. Hotels: Up to 4-star hotels, use preferred vendors when available.\n4. Ground transport: Public transport preferred, taxi/rideshare when necessary.\n5. Per diem: 50 EUR/day domestic, 75 EUR/day international.\n6. Approval: Manager approval required for all travel.\n7. Advance booking: Book at least 2 weeks ahead when possible.\n8. Frequent flyer: Personal frequent flyer accounts permitted.',
           '2024-01-01','2025-04-01','ACTIVE'),

          (12,'Referral Bonus Policy','HR','Employee referral program for recruiting.',
           'ACME Referral Bonus Policy\n\n1. Eligibility: All employees except HR and hiring managers for their team.\n2. Bonus amount: 2,500 EUR for successful referrals.\n3. Payment: 50% after 30 days, 50% after 6 months of employment.\n4. Conditions: Referred candidate must stay 6 months minimum.\n5. Submission: Submit referrals through the HR portal.\n6. Timing: Referral must be submitted before candidate applies.\n7. Hard-to-fill roles: Double bonus for designated positions.\n8. Executive roles: Special bonus structure, contact HR.',
           '2024-01-01','2025-01-01','ACTIVE');
        """
            )
        )

        # ============================================================================
        # COMPANY HOLIDAYS 2025 & 2026 (German public holidays)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO company_holiday VALUES
          -- 2025 Holidays
          (1,'2025-01-01','New Year''s Day',1),
          (2,'2025-04-18','Good Friday',1),
          (3,'2025-04-21','Easter Monday',1),
          (4,'2025-05-01','Labour Day',1),
          (5,'2025-05-29','Ascension Day',1),
          (6,'2025-06-09','Whit Monday',1),
          (7,'2025-10-03','German Unity Day',1),
          (8,'2025-12-24','Christmas Eve',1),
          (9,'2025-12-25','Christmas Day',1),
          (10,'2025-12-26','Boxing Day',1),
          (11,'2025-12-31','New Year''s Eve',1),
          -- 2026 Holidays
          (12,'2026-01-01','New Year''s Day',1),
          (13,'2026-04-03','Good Friday',1),
          (14,'2026-04-06','Easter Monday',1),
          (15,'2026-05-01','Labour Day',1),
          (16,'2026-05-14','Ascension Day',1),
          (17,'2026-05-25','Whit Monday',1),
          (18,'2026-10-03','German Unity Day',1),
          (19,'2026-12-24','Christmas Eve',1),
          (20,'2026-12-25','Christmas Day',1),
          (21,'2026-12-26','Boxing Day',1),
          (22,'2026-12-31','New Year''s Eve',1),
          -- Company-specific holidays
          (23,'2026-06-15','ACME Founder''s Day',1),
          (24,'2026-08-14','Summer Friday (Company Gift)',1);
        """
            )
        )

        # ============================================================================
        # ANNOUNCEMENTS (company news and updates)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO announcement VALUES
          (1,'Q4 2025 All-Hands Meeting','Join us for our quarterly all-hands meeting on January 30th at 2pm CET. We''ll review Q4 results, celebrate wins, and discuss 2026 priorities. Remote employees can join via Zoom.','Company',100,'2026-01-15 09:00:00','2026-01-31 23:59:59'),

          (2,'New Health Insurance Provider','We''re excited to announce our partnership with HealthPlus starting February 1st. New benefits include expanded mental health coverage, dental, and vision. Check your email for enrollment details. HR will host info sessions on Jan 25 and Jan 27.','Benefits',110,'2026-01-10 10:00:00','2026-02-15 23:59:59'),

          (3,'Office Renovation Complete','The 3rd floor renovation is complete! New collaboration spaces, phone booths, and a wellness room are now available. Book spaces through the Facilities app. Special thanks to the IT team for minimal disruption during the transition.','Facilities',400,'2026-01-08 14:00:00','2026-02-08 23:59:59'),

          (4,'Engineering Hackathon 2026','Save the date! Our annual hackathon will be held February 20-21. This year''s theme is "AI for Good." Teams of 3-5 can register starting February 1st. Prizes include extra PTO days and the latest tech gadgets!','Engineering',103,'2026-01-20 11:00:00','2026-02-21 23:59:59'),

          (5,'Welcome New Team Members - January','Please welcome our newest colleagues who joined in January: Emily Rodriguez (HR), Kevin O''Brien (Finance), Aisha Hassan (Engineering), Nina Andersson (Engineering), Ryan Cooper (Sales), and Diana Kovacs (IT). Stop by and say hello!','People',110,'2026-01-22 09:00:00',NULL),

          (6,'2025 Year in Review','What a year! Check out our 2025 highlights: 40% revenue growth, 15 new hires, 3 product launches, and our first international office in Munich. Thank you all for your incredible work. Full report available on the intranet.','Company',100,'2026-01-05 10:00:00',NULL),

          (7,'New Learning Platform Launch','We''ve launched a new learning platform with over 10,000 courses! Access LinkedIn Learning and Udemy Business through the new L&D portal. Your 2026 training budget has been refreshed. Contact Daniel Park for questions.','Learning',114,'2026-01-12 11:00:00','2026-02-28 23:59:59'),

          (8,'IT Maintenance Window - January 28','Planned maintenance on January 28th, 10pm-2am CET. Email and internal tools will be unavailable. Please save your work and log off before 10pm. Emergency contact: it-oncall@acme.com','IT',400,'2026-01-21 15:00:00','2026-01-29 00:00:00'),

          (9,'Sales Team Hits Record Quarter','Congratulations to our Sales team for achieving 125% of Q4 quota! Special recognition to Patrick O''Connor for closing our largest enterprise deal ever, and to the entire team for their dedication. Celebration lunch on Friday!','Sales',300,'2026-01-18 09:00:00',NULL),

          (10,'Mental Health Awareness Week','February 3-7 is Mental Health Awareness Week. We''ll have daily workshops, meditation sessions, and guest speakers. Remember, our Employee Assistance Program offers free confidential counseling. Take care of yourselves!','Wellbeing',110,'2026-01-24 10:00:00','2026-02-07 23:59:59'),

          (11,'Office Closure - Carnival','Reminder: Our Munich office will be closed on February 16-17 for Carnival. Berlin and Hamburg offices remain open. Munich colleagues, please coordinate coverage with your teams.','Company',101,'2026-01-20 14:00:00','2026-02-17 23:59:59'),

          (12,'Referral Bonus Increase','For Q1 2026, we''re doubling our referral bonus for Engineering and Data Science roles! Refer a friend and earn up to 5,000 EUR. Submit referrals through the HR portal. See the updated Referral Policy for details.','HR',112,'2026-01-23 11:00:00','2026-03-31 23:59:59');
        """
            )
        )

        # ============================================================================
        # COMPANY EVENTS (upcoming and scheduled events)
        # ============================================================================
        con.execute(
            text(
                """
        INSERT INTO company_event VALUES
          (1,'Q4 All-Hands Meeting','2026-01-30','14:00','Main Auditorium + Zoom','Quarterly company update, Q4 results review, 2026 roadmap, and Q&A with leadership. Remote-friendly.'),
          (2,'Mental Health Workshop: Stress Management','2026-02-03','12:00','Conference Room B','Part of Mental Health Week. Learn practical techniques for managing workplace stress. Lunch provided.'),
          (3,'Mental Health Workshop: Work-Life Balance','2026-02-05','12:00','Conference Room B','Part of Mental Health Week. Strategies for maintaining healthy boundaries. Lunch provided.'),
          (4,'New Employee Orientation','2026-02-10','09:00','HR Training Room','Welcome session for January/February new hires. Overview of company culture, policies, and benefits.'),
          (5,'Engineering Hackathon 2026','2026-02-20','09:00','Engineering Floor','48-hour hackathon - theme: AI for Good. Form teams of 3-5 and build something amazing!'),
          (6,'Women in Tech Panel','2026-03-08','12:00','Conference Room A','International Women''s Day celebration. Panel discussion with women leaders in tech. Lunch provided.'),
          (7,'Q1 All-Hands Meeting','2026-04-02','14:00','Main Auditorium + Zoom','Q1 results review, performance awards, and company updates.'),
          (8,'Spring Team Building','2026-04-17','10:00','Tiergarten Park','Annual spring team building activities, outdoor games, and BBQ. Family members welcome!'),
          (9,'Learning Day 2026','2026-05-15','09:00','All Floors','Company-wide learning and development day. Choose from 20+ workshops on technical and soft skills.'),
          (10,'ACME Founder''s Day Celebration','2026-06-15','15:00','Rooftop Terrace','Celebrating 8 years of ACME! Speeches, awards, cake, and early release at 4pm.'),
          (11,'Summer Party 2026','2026-07-10','17:00','Beach Club Berlin','Annual summer celebration with food, drinks, DJ, and beach activities. Plus-ones welcome!'),
          (12,'Engineering Tech Talks','2026-08-06','16:00','Engineering Floor','Monthly tech talk series. August topic: Machine Learning in Production. Snacks provided.'),
          (13,'Back to School Drive','2026-08-20','All Day','All Offices','Donate school supplies for underprivileged children. Collection boxes in all lobbies.'),
          (14,'Oktoberfest Celebration','2026-09-25','16:00','Cafeteria','Bavarian-themed celebration with traditional food, beer, and music. Dirndl and Lederhosen encouraged!'),
          (15,'Halloween Party','2026-10-30','17:00','Main Lobby','Annual costume contest with prizes! Snacks, drinks, and spooky fun for all.'),
          (16,'Thanksgiving Potluck','2026-11-26','12:00','Cafeteria','American-style Thanksgiving potluck. Sign up to bring a dish!'),
          (17,'Winter Holiday Party','2026-12-18','18:00','Grand Hotel Berlin','Annual winter celebration with dinner, dancing, and awards. Formal attire. Plus-ones welcome.'),
          (18,'Year-End Town Hall','2026-12-22','11:00','Main Auditorium + Zoom','2026 wrap-up, achievements celebration, and sneak peek at 2027. Last day before holiday break.');
        """
            )
        )
