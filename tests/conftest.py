import pytest

from miteclock.activities import validate_shortcuts


@pytest.fixture
def shortcuts():
    return validate_shortcuts(
        {
            "o": "OCP",
            "a": "ACME",
            "c": "Communication",
            "d": "Development",
            "q": {"pattern": "QA", "match": "strict"},
            "daily": ["o", "c", "daily stand-up"],
            "weekly": ["o", "c", "weekly meeting"],
            "nested": ["ad", "hunting for bugs"],
            "ad": ["a", "d"],
        }
    )


@pytest.fixture
def services():
    return [
        {"name": "Development", "id": 0},
        {"name": "Design", "id": 1},
        {"name": "Developer Training", "id": 2},
        {"name": "DevOps", "id": 3},
        {"name": "QA", "id": 4},
        {"name": "Language QA", "id": 5},
        {"name": "Communication", "id": 6},
    ]


@pytest.fixture
def projects():
    return [
        {"name": "Company_Internal_2020", "id": 0},
        {"name": "OCP ED-209", "id": 1},
        {"name": "ZDF - Rewriting Backend", "id": 2},
        {"name": "ACME :: Squashing Bugs", "id": 3},
        {"name": "AT&T/Designing OS", "id": 4},
        {"name": "AT&T/Designing OS", "id": 5, "customer_name": "AT&T"},
    ]


@pytest.fixture
def time_entries():
    return [
        {
            "id": 0,
            "project_id": 1,
            "service_id": 6,
            "note": "daily stand-up",
            "updated_at": "2020-06-08T10:15:42.007128",
        },
        {
            "id": 1,
            "project_id": 2,
            "service_id": 4,
            "note": "juggling",
            "updated_at": "2020-06-08T11:05:32.007128",
        },
        {
            "id": 2,
            "project_id": 3,
            "service_id": 6,
            "note": "catching up on email",
            "updated_at": "2020-06-08T11:45:02.044416",
        },
    ]


@pytest.fixture
def mite_server(projects, services, time_entries):
    return {
        "projects": [{"project": proj} for proj in projects],
        "services": [{"service": svc} for svc in services],
        "time_entries": [{"time_entry": te} for te in time_entries],
        "tracker": {"tracker": {}},
    }
