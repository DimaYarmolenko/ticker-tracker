from fastapi.testclient import TestClient

from tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD


def _register(client: TestClient, email: str, password: str):
    return client.post(
        "/register",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


class TestRegister:
    def test_register_creates_session_and_redirects(self, anon_client: TestClient) -> None:
        response = _register(anon_client, "alice@example.com", "super-secret")
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        # Session cookie should let the next request through.
        me = anon_client.get("/tickers")
        assert me.status_code == 200

    def test_register_duplicate_email_409(self, anon_client: TestClient) -> None:
        _register(anon_client, "dup@example.com", "super-secret")
        anon_client.cookies.clear()
        response = _register(anon_client, "dup@example.com", "another-pass")
        assert response.status_code == 409
        assert "already exists" in response.text

    def test_register_short_password_400(self, anon_client: TestClient) -> None:
        response = _register(anon_client, "bob@example.com", "short")
        assert response.status_code == 400
        assert "at least" in response.text

    def test_register_invalid_email_400(self, anon_client: TestClient) -> None:
        response = _register(anon_client, "not-an-email", "super-secret")
        assert response.status_code == 400
        assert "valid email" in response.text


class TestLogin:
    def test_login_happy_path(self, anon_client: TestClient, seeded_user) -> None:
        response = _login(anon_client, TEST_USER_EMAIL, TEST_USER_PASSWORD)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_login_wrong_password_401(self, anon_client: TestClient, seeded_user) -> None:
        response = _login(anon_client, TEST_USER_EMAIL, "wrong-password")
        assert response.status_code == 401

    def test_login_unknown_email_401(self, anon_client: TestClient) -> None:
        response = _login(anon_client, "nobody@example.com", "super-secret")
        assert response.status_code == 401

    def test_login_case_insensitive_email(self, anon_client: TestClient, seeded_user) -> None:
        response = _login(anon_client, TEST_USER_EMAIL.upper(), TEST_USER_PASSWORD)
        assert response.status_code == 303


class TestLogout:
    def test_logout_clears_session(self, client: TestClient) -> None:
        response = client.post("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        # Subsequent API call now anonymous → 401.
        assert client.get("/tickers").status_code == 401


class TestAnonymousAccess:
    def test_rest_returns_401_when_anonymous(self, anon_client: TestClient) -> None:
        assert anon_client.get("/tickers").status_code == 401
        assert anon_client.post("/tickers", json={"symbol": "AAPL"}).status_code == 401
        assert anon_client.delete("/tickers/AAPL").status_code == 401
        assert anon_client.get("/tickers/AAPL/news").status_code == 401
        assert anon_client.get("/tickers/AAPL/prices").status_code == 401

    def test_ui_redirects_when_anonymous(self, anon_client: TestClient) -> None:
        response = anon_client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_login_page_renders(self, anon_client: TestClient) -> None:
        response = anon_client.get("/login")
        assert response.status_code == 200
        assert "Sign in" in response.text

    def test_register_page_renders(self, anon_client: TestClient) -> None:
        response = anon_client.get("/register")
        assert response.status_code == 200
        assert "Create account" in response.text

    def test_login_page_redirects_authenticated(self, client: TestClient) -> None:
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
