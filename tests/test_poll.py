"""Tests for the feedback poll API."""

import pytest

from app import app as flask_app
from models import PollResponse, db


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


VALID_PAYLOAD = {
    "color_scheme_pref": "dark",
    "cards_aware": "yes",
    "device": "mobile",
    "freeform": "Love the new look!",
}


def _all_responses():
    with flask_app.app_context():
        return PollResponse.query.all()


def test_valid_anonymous_submission_persists(client):
    res = client.post("/api/poll", json=VALID_PAYLOAD)
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}

    rows = _all_responses()
    assert len(rows) == 1
    row = rows[0]
    assert row.color_scheme_pref == "dark"
    assert row.cards_aware == "yes"
    assert row.device == "mobile"
    assert row.freeform == "Love the new look!"
    assert row.user_sub is None


def test_logged_in_submission_captures_user_sub(client):
    with client.session_transaction() as sess:
        sess["user"] = {"sub": "auth0|user-1"}
    res = client.post("/api/poll", json=VALID_PAYLOAD)
    assert res.status_code == 200

    rows = _all_responses()
    assert len(rows) == 1
    assert rows[0].user_sub == "auth0|user-1"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("color_scheme_pref", "rainbow"),
        ("cards_aware", "maybe"),
        ("device", "tablet"),
    ],
)
def test_invalid_enum_rejected(client, field, bad_value):
    payload = dict(VALID_PAYLOAD, **{field: bad_value})
    res = client.post("/api/poll", json=payload)
    assert res.status_code == 400
    assert res.get_json() == {"ok": False, "error": "invalid"}
    assert _all_responses() == []


def test_missing_field_rejected(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "device"}
    res = client.post("/api/poll", json=payload)
    assert res.status_code == 400
    assert _all_responses() == []


def test_empty_freeform_stored_as_null(client):
    payload = dict(VALID_PAYLOAD, freeform="   ")
    res = client.post("/api/poll", json=payload)
    assert res.status_code == 200
    rows = _all_responses()
    assert len(rows) == 1
    assert rows[0].freeform is None


def test_oversized_freeform_truncated(client):
    payload = dict(VALID_PAYLOAD, freeform="x" * 5000)
    res = client.post("/api/poll", json=payload)
    assert res.status_code == 200
    rows = _all_responses()
    assert len(rows) == 1
    assert len(rows[0].freeform) == 2000
