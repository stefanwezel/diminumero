"""Tests for the index-card CRUD and practice flow."""

import pytest

from app import app as flask_app
from models import Card, db


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "test-tenant.eu.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "test-client-secret")
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


SAMPLE_USER = {"sub": "auth0|user-1", "name": "Ada", "email": "ada@example.com"}
OTHER_USER = {"sub": "auth0|user-2", "name": "Grace", "email": "grace@example.com"}


def login(client, user=SAMPLE_USER):
    with client.session_transaction() as sess:
        sess["user"] = user


def make_card(user_sub, front, back):
    with flask_app.app_context():
        card = Card(user_sub=user_sub, front=front, back=back)
        db.session.add(card)
        db.session.commit()
        return card.id


class TestCardsList:
    def test_logged_out_redirects_to_login(self, client):
        response = client.get("/cards")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_empty_state_shown_when_no_cards(self, client):
        login(client)
        response = client.get("/cards")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        # The empty-state copy has "haven't" which Jinja escapes to "haven&#39;t".
        assert "added any cards" in body

    def test_only_own_cards_visible(self, client):
        # Use distinctive markers so they can't collide with HTML chrome
        # (e.g. aria-hidden, type="hidden").
        make_card(OTHER_USER["sub"], "OTHER_FRONT_XYZ", "OTHER_BACK_XYZ")
        my_id = make_card(SAMPLE_USER["sub"], "MY_FRONT_XYZ", "MY_BACK_XYZ")
        login(client)
        response = client.get("/cards")
        body = response.data.decode("utf-8")
        assert "MY_FRONT_XYZ" in body
        assert "MY_BACK_XYZ" in body
        assert "OTHER_FRONT_XYZ" not in body
        assert "OTHER_BACK_XYZ" not in body
        assert my_id is not None


class TestCardsCreate:
    def test_creates_card(self, client):
        login(client)
        response = client.post(
            "/cards", data={"front": "silla", "back": "chair"}, follow_redirects=False
        )
        assert response.status_code == 302
        with flask_app.app_context():
            cards = db.session.query(Card).all()
            assert len(cards) == 1
            assert cards[0].front == "silla"
            assert cards[0].back == "chair"
            assert cards[0].user_sub == SAMPLE_USER["sub"]

    def test_rejects_empty_sides(self, client):
        login(client)
        client.post("/cards", data={"front": "", "back": "table"})
        with flask_app.app_context():
            assert db.session.query(Card).count() == 0


class TestCardsEdit:
    def test_updates_card(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            f"/cards/{card_id}/edit",
            data={"front": "mesa", "back": "desk"},
        )
        with flask_app.app_context():
            assert db.session.get(Card, card_id).back == "desk"

    def test_cannot_edit_other_users_card(self, client):
        card_id = make_card(OTHER_USER["sub"], "secret", "hidden")
        login(client)
        response = client.post(
            f"/cards/{card_id}/edit",
            data={"front": "hacked", "back": "hacked"},
        )
        assert response.status_code == 404
        with flask_app.app_context():
            assert db.session.get(Card, card_id).front == "secret"


class TestCardsDelete:
    def test_deletes_own_card(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(f"/cards/{card_id}/delete")
        with flask_app.app_context():
            assert db.session.get(Card, card_id) is None

    def test_cannot_delete_other_users_card(self, client):
        card_id = make_card(OTHER_USER["sub"], "secret", "hidden")
        login(client)
        response = client.post(f"/cards/{card_id}/delete")
        assert response.status_code == 404
        with flask_app.app_context():
            assert db.session.get(Card, card_id) is not None


class TestPracticeFlow:
    def test_start_redirects_to_cards_when_no_cards(self, client):
        login(client)
        response = client.post(
            "/cards/practice/start", data={"direction": "front_to_back"}
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/cards")

    def test_full_session_front_to_back(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        make_card(SAMPLE_USER["sub"], "silla", "chair")
        login(client)

        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        # Loop until we hit results
        for _ in range(5):
            response = client.get("/cards/practice", follow_redirects=False)
            if response.status_code == 302 and response.headers["Location"].endswith(
                "/cards/practice/results"
            ):
                break
            assert response.status_code == 200
            with client.session_transaction() as sess:
                state = sess["card_practice"]
            with flask_app.app_context():
                card = db.session.get(Card, state["current_card_id"])
            answer = (
                card.back if state["current_prompt_side"] == "front" else card.front
            )
            client.post("/cards/practice", data={"answer": answer})
        else:
            pytest.fail("practice loop did not terminate")

        # Results page should show 2/2
        results = client.get("/cards/practice/results")
        body = results.data.decode("utf-8")
        assert "2 / 2" in body or "2 / 2" in body.replace("&nbsp;", " ")

    def test_reveal_counts_as_attempted_no_score(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        client.post("/cards/practice", data={"reveal": "1"})
        results = client.get("/cards/practice/results")
        body = results.data.decode("utf-8")
        assert "0 / 1" in body

    def test_validate_api_returns_word_feedback(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "small table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")  # Pin a current card
        response = client.post(
            "/api/cards/validate",
            json={"input": "small"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "words" in data
        assert data["is_complete"] is False
        # "small" should be marked correct (it's a prefix of the answer)
        assert data["words"][0]["status"] in ("correct", "incomplete")

    def test_validate_api_requires_active_session(self, client):
        login(client)
        response = client.post("/api/cards/validate", json={"input": "anything"})
        assert response.status_code == 400


class TestPracticeIsolation:
    def test_practice_only_uses_own_cards(self, client):
        make_card(OTHER_USER["sub"], "private", "hidden")
        my_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)

        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        with client.session_transaction() as sess:
            state = sess["card_practice"]
            assert state["current_card_id"] == my_id
