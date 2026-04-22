def test_homepage_route(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "ЧНУ Jobs" in response.get_data(as_text=True)


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "up"}


def test_registration_and_login_flow(client, fake_state):
    register_response = client.post(
        "/register",
        data={
            "full_name": "Test Student",
            "email": "student@example.com",
            "password": "student123",
            "role": "STUDENT",
        },
        follow_redirects=False,
    )

    assert register_response.status_code == 302
    assert register_response.headers["Location"].endswith("/login")
    assert any(user["email"] == "student@example.com" for user in fake_state["users"])

    login_response = client.post(
        "/login",
        data={"email": "student@example.com", "password": "student123"},
        follow_redirects=True,
    )

    assert login_response.status_code == 200
    assert "Кабінет студента" in login_response.get_data(as_text=True)


def test_jobs_page_route(client):
    response = client.get("/jobs")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Python Intern" in page
    assert "ACME Company" in page
