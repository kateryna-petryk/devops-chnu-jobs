import bcrypt
import pytest

from backend.app import create_app


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.result = []

    def execute(self, query, params=()):
        normalized = " ".join(query.split()).lower()

        if normalized == "select 1":
            self.result = [(1,)]
            return

        if "insert into users" in normalized:
            full_name, email, password_hash, role = params
            if any(user["email"] == email for user in self.state["users"]):
                raise Exception("duplicate key value")
            next_id = len(self.state["users"]) + 1
            self.state["users"].append(
                {
                    "id": next_id,
                    "full_name": full_name,
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
                }
            )
            self.result = []
            return

        if "from users" in normalized and "where email = %s" in normalized:
            email = params[0]
            user = next(
                (item for item in self.state["users"] if item["email"] == email),
                None,
            )
            self.result = (
                [
                    (
                        user["id"],
                        user["full_name"],
                        user["email"],
                        user["password_hash"],
                        user["role"],
                    )
                ]
                if user
                else []
            )
            return

        if "from jobs j" in normalized and "where j.is_active = true" in normalized:
            rows = []
            for job in self.state["jobs"]:
                if not job["is_active"]:
                    continue
                company = next(
                    user for user in self.state["users"] if user["id"] == job["company_id"]
                )
                rows.append(
                    (
                        job["id"],
                        job["title"],
                        job["location"],
                        job["employment_type"],
                        company["full_name"],
                    )
                )
            self.result = rows
            return

        raise AssertionError(f"Unsupported query in test fake DB: {query}")

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return list(self.result)


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return FakeCursor(self.state)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


@pytest.fixture
def fake_state(monkeypatch):
    company_password = bcrypt.hashpw(b"firma123", bcrypt.gensalt()).decode()
    state = {
        "users": [
            {
                "id": 1,
                "full_name": "ACME Company",
                "email": "firma@example.com",
                "password_hash": company_password,
                "role": "FIRMA",
            }
        ],
        "jobs": [
            {
                "id": 1,
                "company_id": 1,
                "title": "Python Intern",
                "description": "Work with Flask and PostgreSQL",
                "employment_type": "Part-time",
                "location": "Chernivtsi",
                "is_active": True,
            }
        ],
    }

    monkeypatch.setattr("backend.app.get_connection", lambda: FakeConnection(state))
    return state


@pytest.fixture
def app(fake_state):
    return create_app(
        {
            "TESTING": True,
            "SKIP_DB_INIT": True,
            "SECRET_KEY": "test-secret",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()
