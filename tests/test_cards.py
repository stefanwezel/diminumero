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

    def test_sort_control_rendered_when_cards_exist(self, client):
        # The sort dropdown is the entry point for the client-side sorter;
        # each card row must carry data-created-at for the JS to compare on.
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-sort-select"' in body
        assert 'value="created_desc"' in body
        assert 'value="times_practiced_desc"' in body
        assert 'value="score_asc"' in body
        assert "data-created-at=" in body

    def test_sort_control_hidden_when_no_cards(self, client):
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-sort-select"' not in body


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


class TestCardsApi:
    def test_create_returns_card_json(self, client):
        login(client)
        response = client.post("/api/cards", json={"front": "silla", "back": "chair"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["card"]["front"] == "silla"
        assert data["card"]["back"] == "chair"
        assert isinstance(data["card"]["id"], int)
        # cards.js stamps the new <li> with data-created-at so the sorter can
        # place it correctly — the payload must include it.
        assert isinstance(data["card"]["created_at"], str)
        assert data["card"]["created_at"]
        with flask_app.app_context():
            assert db.session.query(Card).count() == 1

    def test_create_rejects_empty_sides(self, client):
        login(client)
        response = client.post("/api/cards", json={"front": "", "back": "chair"})
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert data["error"]
        with flask_app.app_context():
            assert db.session.query(Card).count() == 0

    def test_create_requires_login(self, client):
        response = client.post("/api/cards", json={"front": "a", "back": "b"})
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_update_returns_card_json(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        response = client.patch(
            f"/api/cards/{card_id}", json={"front": "mesa", "back": "desk"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["card"]["back"] == "desk"
        with flask_app.app_context():
            assert db.session.get(Card, card_id).back == "desk"

    def test_update_rejects_empty_sides(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        response = client.patch(
            f"/api/cards/{card_id}", json={"front": "mesa", "back": ""}
        )
        assert response.status_code == 400
        assert response.get_json()["ok"] is False
        with flask_app.app_context():
            assert db.session.get(Card, card_id).back == "table"

    def test_update_other_users_card_404(self, client):
        card_id = make_card(OTHER_USER["sub"], "secret", "hidden")
        login(client)
        response = client.patch(
            f"/api/cards/{card_id}", json={"front": "x", "back": "y"}
        )
        assert response.status_code == 404
        with flask_app.app_context():
            assert db.session.get(Card, card_id).front == "secret"

    def test_delete_returns_ok(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        response = client.delete(f"/api/cards/{card_id}")
        assert response.status_code == 200
        assert response.get_json() == {"ok": True}
        with flask_app.app_context():
            assert db.session.get(Card, card_id) is None

    def test_delete_other_users_card_404(self, client):
        card_id = make_card(OTHER_USER["sub"], "secret", "hidden")
        login(client)
        response = client.delete(f"/api/cards/{card_id}")
        assert response.status_code == 404
        with flask_app.app_context():
            assert db.session.get(Card, card_id) is not None

    def test_delete_requires_login(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        response = client.delete(f"/api/cards/{card_id}")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


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

        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "count": "10"},
        )
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
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "advanced"},
        )
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

    def test_count_caps_session_below_deck_size(self, client):
        # 5-card deck, count=2 → only 2 questions before results.
        for i in range(5):
            make_card(SAMPLE_USER["sub"], f"front{i}", f"back{i}")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "count": "2"},
        )
        for _ in range(2):
            response = client.get("/cards/practice", follow_redirects=False)
            assert response.status_code == 200
            with client.session_transaction() as sess:
                state = sess["card_practice"]
            with flask_app.app_context():
                card = db.session.get(Card, state["current_card_id"])
            client.post("/cards/practice", data={"answer": card.back})
        # Third GET should redirect to results.
        response = client.get("/cards/practice", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/cards/practice/results")
        with client.session_transaction() as sess:
            assert sess["card_practice"]["total"] == 2

    def test_count_defaults_to_10(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        # No `count` field in form data.
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        with client.session_transaction() as sess:
            assert sess["card_practice"]["count"] == 10

    def test_count_clamped_to_valid_range(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start", data={"direction": "front_to_back", "count": "999"}
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["count"] == 100

        client.post(
            "/cards/practice/start", data={"direction": "front_to_back", "count": "0"}
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["count"] == 1


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


def _answer_one(client, response_text=None):
    """Walk one question of an active practice session.

    Reads the current card from the session, submits the side opposite the
    prompt as the answer (or the value of `response_text` if given), and
    returns the card row reloaded from the DB so the caller can assert on
    the updated counters.
    """
    with client.session_transaction() as sess:
        state = sess["card_practice"]
        card_id = state["current_card_id"]
        prompt_side = state["current_prompt_side"]
    with flask_app.app_context():
        card = db.session.get(Card, card_id)
        correct = card.back if prompt_side == "front" else card.front
    answer = response_text if response_text is not None else correct
    client.post("/cards/practice", data={"answer": answer})
    with flask_app.app_context():
        return db.session.get(Card, card_id)


class TestCardScoring:
    def test_correct_answer_increments_both_counters(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        card = _answer_one(client)  # correct
        assert card.id == card_id
        assert card.times_practiced == 1
        assert card.times_correct == 1

    def test_wrong_answer_increments_practiced_only(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        card = _answer_one(client, response_text="definitely-wrong")
        assert card.id == card_id
        assert card.times_practiced == 1
        assert card.times_correct == 0

    def test_reveal_increments_practiced_only(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        client.post("/cards/practice", data={"reveal": "1"})
        with flask_app.app_context():
            card = db.session.get(Card, card_id)
        assert card.times_practiced == 1
        assert card.times_correct == 0

    def test_to_dict_exposes_score_fields(self, client):
        with flask_app.app_context():
            card = Card(
                user_sub=SAMPLE_USER["sub"],
                front="mesa",
                back="table",
                times_practiced=4,
                times_correct=3,
            )
            db.session.add(card)
            db.session.commit()
            payload = card.to_dict()
        assert payload["times_practiced"] == 4
        assert payload["times_correct"] == 3
        assert payload["score"] == pytest.approx(0.75)

    def test_score_is_none_for_unpracticed_card(self, client):
        with flask_app.app_context():
            card = Card(user_sub=SAMPLE_USER["sub"], front="x", back="y")
            db.session.add(card)
            db.session.commit()
            assert card.score is None
            assert card.to_dict()["score"] is None

    def test_score_is_ratio_after_mixed_attempts(self, client):
        # A practice session asks each card at most once, so to exercise the
        # ratio we drive a card across two separate sessions: one correct,
        # one wrong submission.
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        _answer_one(client)  # correct
        client.get("/cards/practice/results")  # clear session
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        client.get("/cards/practice")
        card = _answer_one(client, response_text="wrong")
        assert card.id == card_id
        assert card.times_practiced == 2
        assert card.times_correct == 1
        assert card.score == pytest.approx(0.5)

    def test_sampling_mode_stored_in_session(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "sampling_mode": "prioritized"},
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["sampling_mode"] == "prioritized"

    def test_sampling_mode_defaults_invalid_to_prioritized(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "sampling_mode": "nonsense"},
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["sampling_mode"] == "prioritized"
        # Missing field also falls back to prioritized.
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        with client.session_transaction() as sess:
            assert sess["card_practice"]["sampling_mode"] == "prioritized"

    def test_difficulty_stored_in_session(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "hardcore"},
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["difficulty"] == "hardcore"

    def test_difficulty_defaults_invalid_to_hardcore(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "nope"},
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["difficulty"] == "hardcore"
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        with client.session_transaction() as sess:
            assert sess["card_practice"]["difficulty"] == "hardcore"

    def test_hardcore_leaks_correct_answer_to_template(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "hardcore"},
        )
        response = client.get("/cards/practice")
        body = response.data.decode("utf-8")
        assert 'data-difficulty="hardcore"' in body
        assert 'data-correct-answer="table"' in body

    def test_advanced_does_not_leak_correct_answer(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "advanced"},
        )
        response = client.get("/cards/practice")
        body = response.data.decode("utf-8")
        assert 'data-difficulty="advanced"' in body
        assert "data-correct-answer" not in body

    def test_validate_api_disabled_in_hardcore(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "hardcore"},
        )
        client.get("/cards/practice")  # pin the current card
        response = client.post("/api/cards/validate", json={"input": "tab"})
        assert response.status_code == 400

    def test_prioritized_sampling_favors_low_score_cards(self, client):
        from flask import session as flask_session

        from app import _load_next_card

        high_id = make_card(SAMPLE_USER["sub"], "mastered", "card")
        low_id = make_card(SAMPLE_USER["sub"], "weak", "card")
        with flask_app.app_context():
            mastered = db.session.get(Card, high_id)
            mastered.times_practiced = 10
            mastered.times_correct = 10
            db.session.commit()

        # Weights: low card ≈ 1.1, high card ≈ 0.1 (11:1 expected).
        picks = []
        for _ in range(200):
            with flask_app.test_request_context():
                flask_session["user"] = SAMPLE_USER
                state = {
                    "direction": "front_to_back",
                    "sampling_mode": "prioritized",
                    "asked_ids": [],
                    "current_card_id": None,
                }
                card = _load_next_card(state)
                picks.append(card.id)
        low_count = picks.count(low_id)
        # 70% lower bound: well below the ~92% expectation but high enough
        # to fail a uniform-sampling regression (50%).
        assert low_count >= 140, f"low-score card was picked only {low_count}/200 times"
