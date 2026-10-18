"""Tests for Auth0 login flow and the /cards placeholder section."""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pytest

import app as app_module
from app import app as flask_app
from config import LOGIN_SESSION_DAYS


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

    def test_callback_oauth_error_redirects_to_index(self, client, monkeypatch):
        from authlib.integrations.base_client.errors import MismatchingStateError

        def fake_authorize_access_token():
            raise MismatchingStateError()

        monkeypatch.setattr(
            app_module.oauth.auth0,
            "authorize_access_token",
            fake_authorize_access_token,
        )
        response = client.get("/callback")
        assert response.status_code == 302
        assert response.headers["Location"] == "/"
        with client.session_transaction() as sess:
            assert "user" not in sess
            flashes = sess.get("_flashes", [])
        assert any("Login failed" in message for _, message in flashes)


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


def _session_set_cookie(response):
    """The response's Set-Cookie header for the session cookie, or None."""
    for header in response.headers.getlist("Set-Cookie"):
        if header.startswith("session="):
            return header
    return None


def _expires_in_days(set_cookie):
    """Days from now until the cookie's Expires, or None for a browser-session cookie."""
    for attr in set_cookie.split(";"):
        name, _, value = attr.strip().partition("=")
        if name.lower() == "expires":
            remaining = parsedate_to_datetime(value) - datetime.now(timezone.utc)
            return remaining.total_seconds() / 86400
    return None


def _user_logged_in(days_ago):
    """SAMPLE_USER as the callback stores it: ID token claims including `iat`."""
    return {**SAMPLE_USER, "iat": int(time.time() - days_ago * 86400)}


class TestLoginSessionLifetime:
    """A login must survive the browser being closed (issue #110: phones kill
    backgrounded browsers, and a cookie without Expires dies with them), while
    an anonymous visitor's cookie still does, and no login outlives its cap."""

    def _log_in(self, client, monkeypatch):
        monkeypatch.setattr(
            app_module.oauth.auth0,
            "authorize_access_token",
            lambda: {"userinfo": _user_logged_in(days_ago=0)},
        )
        return client.get("/callback")

    def test_login_sets_a_persistent_hardened_cookie(self, client, monkeypatch):
        cookie = _session_set_cookie(self._log_in(client, monkeypatch))
        days = _expires_in_days(cookie)
        assert days is not None, cookie
        assert LOGIN_SESSION_DAYS - 0.01 < days <= LOGIN_SESSION_DAYS
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie

    def test_anonymous_cookie_dies_with_the_browser(self, client):
        cookie = _session_set_cookie(client.get("/es/numbers"))
        assert cookie is not None
        assert _expires_in_days(cookie) is None

    @pytest.mark.parametrize(
        "method, path, data",
        [("post", "/es/start", {"mode": "easy"}), ("post", "/restart", {})],
    )
    def test_login_stays_persistent_when_the_session_is_cleared(
        self, client, monkeypatch, method, path, data
    ):
        # Both routes session.clear() and put the user back; `permanent` is a
        # session key, so it must not be lost along with everything else.
        self._log_in(client, monkeypatch)
        cookie = _session_set_cookie(getattr(client, method)(path, data=data))
        assert _expires_in_days(cookie) is not None, cookie

    def test_logout_returns_to_a_browser_session_cookie(self, client, monkeypatch):
        self._log_in(client, monkeypatch)
        cookie = _session_set_cookie(client.get("/logout"))
        assert cookie is not None
        assert _expires_in_days(cookie) is None

    def test_session_from_before_this_change_is_made_persistent(self, client):
        # Logged in before the fix: the user is there but the cookie is not
        # permanent. The next request has to upgrade it, not wait for a re-login.
        with client.session_transaction() as sess:
            sess["user"] = _user_logged_in(days_ago=3)
        cookie = _session_set_cookie(client.get("/"))
        assert _expires_in_days(cookie) is not None, cookie

    def test_login_within_the_cap_is_kept(self, client):
        with client.session_transaction() as sess:
            sess["user"] = _user_logged_in(days_ago=LOGIN_SESSION_DAYS - 1)
        assert client.get("/cards").status_code == 200

    def test_login_past_the_cap_ends_even_with_a_fresh_cookie(self, client):
        # session_transaction signs the cookie just now, so this login has been
        # "active" a second ago. The cap counts from the login, so it still ends.
        with client.session_transaction() as sess:
            sess["user"] = _user_logged_in(days_ago=LOGIN_SESSION_DAYS + 1)
            sess["learn_language"] = "de"
        response = client.get("/cards")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        with client.session_transaction() as sess:
            assert "user" not in sess
            # Only the login ends; the rest of the session is untouched.
            assert sess["learn_language"] == "de"


class TestSessionStaysOutOfSharedCaches:
    """A shared cache must never store a page rendered for a logged-in user,
    or a response carrying the session cookie — it would hand that login to
    the next person behind the same proxy."""

    def test_logged_in_page_is_private(self, client):
        with client.session_transaction() as sess:
            sess["user"] = _user_logged_in(days_ago=0)
        response = client.get("/about")
        assert response.headers["Cache-Control"] == "private, max-age=3600"

    def test_response_setting_the_cookie_is_private(self, client):
        # The first visit puts the UI language in the session -> Set-Cookie.
        response = client.get("/about")
        assert _session_set_cookie(response) is not None
        assert response.headers["Cache-Control"].startswith("private")

    def test_anonymous_page_without_set_cookie_stays_public(self, client):
        client.get("/about")
        response = client.get("/about")
        assert _session_set_cookie(response) is None
        assert response.headers["Cache-Control"] == "public, max-age=3600"
