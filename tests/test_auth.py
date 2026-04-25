"""Tests for Auth0 login flow and the /cards placeholder section."""

import pytest

import app as app_module
from app import app as flask_app


@pytest.fixture
def app(monkeypatch):
    """Test app with stub Auth0 env vars."""
    monkeypatch.setenv("AUTH0_DOMAIN", "test-tenant.eu.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "test-client-secret")
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


SAMPLE_USER = {
    "sub": "auth0|abc123",
    "name": "Ada Lovelace",
    "email": "ada@example.com",
}


class TestCardsAccess:
    def test_cards_redirects_to_login_when_logged_out(self, client):
        response = client.get("/cards")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_cards_renders_when_logged_in(self, client):
        with client.session_transaction() as sess:
            sess["user"] = SAMPLE_USER
        response = client.get("/cards")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Ada Lovelace" in body
        assert "My Cards" in body


class TestLogin:
    def test_login_redirects_to_auth0(self, client, monkeypatch):
        captured = {}

        def fake_authorize_redirect(redirect_uri):
            captured["redirect_uri"] = redirect_uri
            from flask import redirect

            return redirect(
                "https://test-tenant.eu.auth0.com/authorize?client_id=test-client-id"
            )

        monkeypatch.setattr(
            app_module.oauth.auth0,
            "authorize_redirect",
            fake_authorize_redirect,
        )
        response = client.get("/login")
        assert response.status_code == 302
        assert "test-tenant.eu.auth0.com" in response.headers["Location"]
        assert captured["redirect_uri"].endswith("/callback")


class TestCallback:
    def test_callback_stores_user_and_redirects_to_cards(self, client, monkeypatch):
        def fake_authorize_access_token():
            return {"userinfo": SAMPLE_USER}

        monkeypatch.setattr(
            app_module.oauth.auth0,
            "authorize_access_token",
            fake_authorize_access_token,
        )
        response = client.get("/callback")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/cards")
        with client.session_transaction() as sess:
            assert sess["user"] == SAMPLE_USER


class TestLogout:
    def test_logout_clears_user_and_redirects_to_auth0(self, client):
        with client.session_transaction() as sess:
            sess["user"] = SAMPLE_USER
        response = client.get("/logout")
        assert response.status_code == 302
        location = response.headers["Location"]
        assert "test-tenant.eu.auth0.com/v2/logout" in location
        assert "client_id=test-client-id" in location
        with client.session_transaction() as sess:
            assert "user" not in sess


class TestSessionPreservedAcrossQuiz:
    def test_user_survives_start_quiz(self, client):
        with client.session_transaction() as sess:
            sess["user"] = SAMPLE_USER
        response = client.post("/es/start", data={"mode": "easy"})
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess.get("user") == SAMPLE_USER

    def test_user_survives_restart(self, client):
        with client.session_transaction() as sess:
            sess["user"] = SAMPLE_USER
            sess["score"] = 5
        response = client.post("/restart")
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess.get("user") == SAMPLE_USER
            assert "score" not in sess


class TestLoginButtonVisibility:
    def test_landing_page_shows_login_when_logged_out(self, client):
        response = client.get("/")
        body = response.data.decode("utf-8")
        assert 'href="/login"' in body
        assert "Log in" in body

    def test_landing_page_shows_user_when_logged_in(self, client):
        with client.session_transaction() as sess:
            sess["user"] = SAMPLE_USER
        response = client.get("/")
        body = response.data.decode("utf-8")
        assert "Ada Lovelace" in body
        assert 'href="/logout"' in body
        assert 'href="/cards"' in body
