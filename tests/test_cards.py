"""Tests for the index-card CRUD and practice flow."""

import json

import pytest

from app import _build_cards_dashboard_stats, app as flask_app
from models import Card, DeckShare, db


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

    def test_duplicate_create_is_skipped(self, client):
        make_card(SAMPLE_USER["sub"], "silla", "chair")
        login(client)
        response = client.post(
            "/cards",
            data={"front": "silla", "back": "chair"},
            follow_redirects=True,
        )
        body = response.data.decode("utf-8")
        assert "already in your deck" in body
        with flask_app.app_context():
            assert db.session.query(Card).count() == 1

    def test_duplicate_create_is_normalized(self, client):
        make_card(SAMPLE_USER["sub"], "Silla", "chair")
        login(client)
        client.post(
            "/cards",
            data={"front": "  silla ", "back": "Chair"},
            follow_redirects=True,
        )
        with flask_app.app_context():
            assert db.session.query(Card).count() == 1


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

    def test_edit_into_duplicate_is_rejected(self, client):
        a_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        make_card(SAMPLE_USER["sub"], "silla", "chair")
        login(client)
        response = client.post(
            f"/cards/{a_id}/edit",
            data={"front": "silla", "back": "chair"},
            follow_redirects=True,
        )
        body = response.data.decode("utf-8")
        assert "Another card already matches" in body
        with flask_app.app_context():
            unchanged = db.session.get(Card, a_id)
            assert unchanged.front == "mesa"
            assert unchanged.back == "table"
            matches = (
                db.session.query(Card)
                .filter_by(user_sub=SAMPLE_USER["sub"], front="silla", back="chair")
                .count()
            )
            assert matches == 1

    def test_edit_no_self_collision(self, client):
        # A card whose new sides match its own current sides (after normalization)
        # must still save — the dedup helper excludes the row being edited.
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            f"/cards/{card_id}/edit",
            data={"front": "  Mesa ", "back": "table"},
        )
        with flask_app.app_context():
            card = db.session.get(Card, card_id)
            assert card.front == "Mesa"
            assert card.back == "table"


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

    def test_api_create_duplicate_returns_duplicate_flag(self, client):
        existing_id = make_card(SAMPLE_USER["sub"], "silla", "chair")
        login(client)
        response = client.post(
            "/api/cards", json={"front": "  Silla", "back": "Chair "}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["duplicate"] is True
        assert data["card"]["id"] == existing_id
        with flask_app.app_context():
            assert db.session.query(Card).count() == 1

    def test_api_update_duplicate_returns_duplicate_flag(self, client):
        a_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        make_card(SAMPLE_USER["sub"], "silla", "chair")
        login(client)
        response = client.patch(
            f"/api/cards/{a_id}", json={"front": "silla", "back": "chair"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["duplicate"] is True
        # Returned card payload is the unchanged original.
        assert data["card"]["id"] == a_id
        assert data["card"]["front"] == "mesa"
        assert data["card"]["back"] == "table"
        with flask_app.app_context():
            unchanged = db.session.get(Card, a_id)
            assert unchanged.front == "mesa"
            assert unchanged.back == "table"

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
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "reveal_mode": "click"},
        )
        client.get("/cards/practice")
        with client.session_transaction() as sess:
            pinned_card_id = sess["card_practice"]["current_card_id"]

        # Reveal records the attempt but keeps the card mounted so the
        # answer-display page can render.
        client.post("/cards/practice", data={"reveal": "1"})
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["current_revealed"] is True
        assert state["current_card_id"] == pinned_card_id
        assert state["total"] == 1
        assert state["score"] == 0
        assert pinned_card_id not in state["asked_ids"]

        # Explicit Next advances and clears the revealed flag.
        client.post("/cards/practice", data={"next": "1"})
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["current_revealed"] is False
        assert state["current_card_id"] is None
        assert pinned_card_id in state["asked_ids"]

        results = client.get("/cards/practice/results")
        body = results.data.decode("utf-8")
        assert "0 / 1" in body

    def test_answer_post_after_reveal_does_not_double_count(self, client):
        # Regression: a revealed card already recorded its attempt. A stray
        # answer POST without `next` (e.g. the type-to-continue retype form
        # auto-submitting via form.submit(), which drops the Next button) must
        # not advance the card nor count it a second time — otherwise a
        # 10-question session would end after 5 cards.
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "reveal_mode": "type"},
        )
        client.get("/cards/practice")
        client.post("/cards/practice", data={"reveal": "1"})
        with client.session_transaction() as sess:
            pinned = sess["card_practice"]["current_card_id"]

        # Buggy client: retyped answer submitted WITHOUT `next`.
        client.post("/cards/practice", data={"answer": "table"})
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["total"] == 1  # not 2
        assert state["score"] == 0
        assert state["current_revealed"] is True
        assert state["current_card_id"] == pinned
        assert pinned not in state["asked_ids"]

        # The correct `next` POST (with the retyped answer) advances exactly once.
        client.post("/cards/practice", data={"answer": "table", "next": "1"})
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["total"] == 1
        assert state["current_revealed"] is False
        assert pinned in state["asked_ids"]

    def test_reveal_renders_answer_and_next_form(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "tablecloth-distinct-answer")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "reveal_mode": "click"},
        )
        client.get("/cards/practice")
        client.post("/cards/practice", data={"reveal": "1"})

        page = client.get("/cards/practice")
        body = page.data.decode("utf-8")
        # Answer is rendered prominently (in the reveal modal) and a
        # Next-submit form is present.
        assert "tablecloth-distinct-answer" in body
        assert "reveal-modal" in body
        assert 'name="next"' in body
        # The input form and Reveal button are hidden while revealed.
        assert 'id="answerInput"' not in body
        assert 'name="reveal"' not in body

        # Posting Next loads a fresh card view (or redirects to results when
        # the deck/count is exhausted).
        client.post("/cards/practice", data={"next": "1"})
        page = client.get("/cards/practice", follow_redirects=False)
        # Either the session is done (302 to results) or we're on a new card
        # with the input form back. Both are valid; the key invariant is that
        # we're no longer in the revealed state.
        with client.session_transaction() as sess:
            state = sess.get("card_practice")
        if state is not None:
            assert state["current_revealed"] is False

    def test_reveal_mode_defaults_to_type(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        with client.session_transaction() as sess:
            assert sess["card_practice"]["reveal_mode"] == "type"

    def test_type_mode_reveal_input_rendered(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "reveal_mode": "type"},
        )
        client.get("/cards/practice")
        client.post("/cards/practice", data={"reveal": "1"})
        body = client.get("/cards/practice").data.decode("utf-8")
        # Type mode shows a retype input inside the reveal modal.
        assert 'id="revealInput"' in body
        assert "cards_practice_reveal.js" in body

    def test_type_mode_next_requires_correct_answer(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "reveal_mode": "type"},
        )
        client.get("/cards/practice")
        with client.session_transaction() as sess:
            pinned_card_id = sess["card_practice"]["current_card_id"]
        client.post("/cards/practice", data={"reveal": "1"})

        # Next with a blank/wrong answer must NOT advance: the card stays
        # mounted and revealed.
        client.post("/cards/practice", data={"next": "1"})
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["current_revealed"] is True
        assert state["current_card_id"] == pinned_card_id
        assert pinned_card_id not in state["asked_ids"]

        client.post("/cards/practice", data={"next": "1", "answer": "wrong"})
        with client.session_transaction() as sess:
            assert sess["card_practice"]["current_revealed"] is True

        # The correct typed answer advances. Reveal already recorded the
        # attempt, so retyping does not add to the score.
        client.post("/cards/practice", data={"next": "1", "answer": "table"})
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["current_revealed"] is False
        assert state["current_card_id"] is None
        assert pinned_card_id in state["asked_ids"]
        assert state["total"] == 1
        assert state["score"] == 0

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


def _drive_one_attempt(client, response_text=None):
    """Start a single-card practice session, answer one question, then clear.

    Each practice session asks any card at most once, so multi-attempt tests
    on a single card need to start a fresh session per attempt.
    """
    client.post("/cards/practice/start", data={"direction": "front_to_back"})
    client.get("/cards/practice")
    card = _answer_one(client, response_text=response_text)
    client.get("/cards/practice/results")
    return card


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
        # Reveal is graded as a wrong attempt in the rolling window.
        assert card.recent_results == "0"

    def test_to_dict_exposes_score_fields(self, client):
        with flask_app.app_context():
            card = Card(
                user_sub=SAMPLE_USER["sub"],
                front="mesa",
                back="table",
                times_practiced=4,
                times_correct=3,
                recent_results="1110",
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

    def test_score_is_rolling_average_after_mixed_attempts(self, client):
        # A practice session asks each card at most once, so to exercise the
        # rolling window we drive a card across two separate sessions: one
        # correct, one wrong submission.
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        _drive_one_attempt(client)  # correct
        card = _drive_one_attempt(client, response_text="wrong")
        assert card.id == card_id
        assert card.times_practiced == 2
        assert card.times_correct == 1
        assert card.recent_results == "10"
        assert card.score == pytest.approx(0.5)

    def test_recent_results_caps_at_window_size(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        # First two attempts are wrong; the next 10 are correct. After 12
        # attempts the rolling window should only retain the last 10
        # (all "1"s), so the early wrongs have fallen out.
        _drive_one_attempt(client, response_text="wrong")
        _drive_one_attempt(client, response_text="wrong")
        for _ in range(10):
            _drive_one_attempt(client)
        with flask_app.app_context():
            card = db.session.get(Card, card_id)
        assert card.times_practiced == 12
        assert card.times_correct == 10
        assert card.recent_results == "1" * 10
        assert card.score == pytest.approx(1.0)

    def test_score_recovers_to_one_after_ten_correct(self, client):
        # Headline behaviour: a card that's been wrong many times can still
        # reach a 100% score if the last 10 attempts are all correct.
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        with flask_app.app_context():
            card = db.session.get(Card, card_id)
            card.times_practiced = 10
            card.times_correct = 0
            card.recent_results = "0" * 10
            db.session.commit()
        login(client)
        for _ in range(10):
            _drive_one_attempt(client)
        with flask_app.app_context():
            card = db.session.get(Card, card_id)
        assert card.recent_results == "1" * 10
        assert card.score == pytest.approx(1.0)
        # Lifetime counters keep accumulating past the window.
        assert card.times_practiced == 20
        assert card.times_correct == 10

    def test_lifetime_counters_unchanged_by_rolling_window(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        for _ in range(12):
            _drive_one_attempt(client)
        with flask_app.app_context():
            card = db.session.get(Card, card_id)
        assert card.times_practiced == 12
        assert card.times_correct == 12
        assert len(card.recent_results) == 10

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

    def test_difficulty_defaults_invalid_to_advanced(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "nope"},
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["difficulty"] == "advanced"
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        with client.session_transaction() as sess:
            assert sess["card_practice"]["difficulty"] == "advanced"

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
            mastered.recent_results = "1" * 10
            db.session.commit()

        # Weights: unpracticed card ≈ 2.1, mastered card ≈ 0.19 (~11:1).
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

    def test_prioritized_sampling_favors_rarely_practiced_cards(self, client):
        """Same score, different practice counts: the rarely practiced card
        must be sampled more often. Guards the scarcity term — without it a
        card answered correctly once would weigh the same as a 50-attempt
        veteran and effectively never resurface."""
        from flask import session as flask_session

        from app import _load_next_card

        veteran_id = make_card(SAMPLE_USER["sub"], "veteran", "card")
        rookie_id = make_card(SAMPLE_USER["sub"], "rookie", "card")
        with flask_app.app_context():
            veteran = db.session.get(Card, veteran_id)
            veteran.times_practiced = 50
            veteran.times_correct = 50
            veteran.recent_results = "1" * 10
            rookie = db.session.get(Card, rookie_id)
            rookie.times_practiced = 1
            rookie.times_correct = 1
            rookie.recent_results = "1"
            db.session.commit()

        # Both have score 1.0. Weights: rookie ≈ 0.6, veteran ≈ 0.12 (~5:1).
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
        rookie_count = picks.count(rookie_id)
        # ~83% expected; 65% bound is robust to variance but fails a
        # regression to score-only weighting (50%).
        assert rookie_count >= 130, (
            f"rarely-practiced card was picked only {rookie_count}/200 times"
        )


class TestPrioritizedSamplingHttp:
    """End-to-end check that prioritized sampling biases picks under the
    real HTTP/cookie round-trip.

    The unit test in TestCardScoring proves the weight math; this proves
    the Flask session plumbing (asked_ids persistence across redirects,
    re-fetching card.score between requests) actually applies it.
    """

    def _seed_deck(self):
        """Create 3 mastered + 3 weak cards. Returns (high_ids, low_ids)."""
        high_ids = []
        low_ids = []
        with flask_app.app_context():
            for i in range(3):
                card = Card(
                    user_sub=SAMPLE_USER["sub"],
                    front=f"hi{i}",
                    back=f"HI{i}",
                    times_practiced=10,
                    times_correct=10,
                    recent_results="1" * 10,
                )
                db.session.add(card)
                db.session.flush()
                high_ids.append(card.id)
            for i in range(3):
                card = Card(
                    user_sub=SAMPLE_USER["sub"],
                    front=f"lo{i}",
                    back=f"LO{i}",
                    times_practiced=10,
                    times_correct=0,
                    recent_results="0" * 10,
                )
                db.session.add(card)
                db.session.flush()
                low_ids.append(card.id)
            db.session.commit()
        return high_ids, low_ids

    def _reset_scores(self, high_ids, low_ids):
        """Restore the seeded scores so each session starts from the same
        weight distribution. Without this, repeated correct answers would
        drift low-score cards up toward 1.0 over the run."""
        with flask_app.app_context():
            for cid in high_ids:
                db.session.get(Card, cid).recent_results = "1" * 10
            for cid in low_ids:
                db.session.get(Card, cid).recent_results = "0" * 10
            db.session.commit()

    def test_low_score_cards_dominate_across_sessions(self, client):
        high_ids, low_ids = self._seed_deck()
        login(client)

        sessions = 30
        per_session = 3
        all_picks = []
        for _ in range(sessions):
            self._reset_scores(high_ids, low_ids)
            client.post(
                "/cards/practice/start",
                data={
                    "direction": "front_to_back",
                    "sampling_mode": "prioritized",
                    "count": str(per_session),
                },
            )
            picked_in_session = []
            for _ in range(per_session):
                response = client.get("/cards/practice", follow_redirects=False)
                if response.status_code == 302:
                    break
                with client.session_transaction() as sess:
                    state = sess["card_practice"]
                    cid = state["current_card_id"]
                    prompt_side = state["current_prompt_side"]
                with flask_app.app_context():
                    card = db.session.get(Card, cid)
                    answer = card.back if prompt_side == "front" else card.front
                client.post("/cards/practice", data={"answer": answer})
                picked_in_session.append(cid)
            client.get("/cards/practice/results")  # clear session

            assert len(set(picked_in_session)) == len(picked_in_session), (
                f"asked_ids did not exclude within session: {picked_in_session}"
            )
            all_picks.extend(picked_in_session)

        low_picks = sum(1 for cid in all_picks if cid in low_ids)
        high_picks = sum(1 for cid in all_picks if cid in high_ids)
        # Both groups start at 10 practices, so the scarcity terms cancel and
        # the weight ratio is ~1.19:0.19 (~6:1), drifting toward 11:1 as
        # times_practiced grows over the run. Assert a much weaker bound (3:1)
        # so the test is robust against random variance but still catches a
        # regression to uniform sampling (which would give 1:1).
        assert low_picks > high_picks * 3, (
            f"prioritized sampling not biased through HTTP: "
            f"low={low_picks} high={high_picks} of {len(all_picks)}"
        )


class TestSiblingAnswers:
    """Accept any sibling card's answer when multiple cards share a prompt.

    Real-world case: a user has both ("sometimes", "a veces") and
    ("sometimes", "algunas veces"). Regardless of which one the sampler
    pinned, either translation should be accepted at submit time, and live
    word-by-word feedback should follow the sibling that best matches what
    the user is typing.
    """

    def _start_and_pin(self, client, pinned_id, direction):
        """Start a practice session and overwrite current_card_id so the
        test knows exactly which sibling is being asked.

        Reassigns the top-level session key — Flask doesn't always detect
        deep mutations of nested dicts.
        """
        client.post("/cards/practice/start", data={"direction": direction})
        client.get("/cards/practice")  # populate state with some card
        prompt_side = "front" if direction == "front_to_back" else "back"
        with client.session_transaction() as sess:
            state = dict(sess["card_practice"])
            state["current_card_id"] = pinned_id
            state["current_prompt_side"] = prompt_side
            state["current_revealed"] = False
            sess["card_practice"] = state

    def test_sibling_answer_accepted_front_to_back(self, client):
        chosen_id = make_card(SAMPLE_USER["sub"], "sometimes", "a veces")
        sibling_id = make_card(SAMPLE_USER["sub"], "sometimes", "algunas veces")
        login(client)
        self._start_and_pin(client, chosen_id, "front_to_back")

        client.post("/cards/practice", data={"answer": "algunas veces"})

        with flask_app.app_context():
            chosen = db.session.get(Card, chosen_id)
            sibling = db.session.get(Card, sibling_id)
        # Score lands on the originally picked card, not the matched sibling.
        assert chosen.recent_results == "1"
        assert chosen.times_correct == 1
        assert chosen.times_practiced == 1
        assert sibling.recent_results == ""
        assert sibling.times_practiced == 0

    def test_sibling_answer_accepted_back_to_front(self, client):
        chosen_id = make_card(SAMPLE_USER["sub"], "morning", "day")
        sibling_id = make_card(SAMPLE_USER["sub"], "noon", "day")
        login(client)
        self._start_and_pin(client, chosen_id, "back_to_front")

        client.post("/cards/practice", data={"answer": "noon"})

        with flask_app.app_context():
            chosen = db.session.get(Card, chosen_id)
            sibling = db.session.get(Card, sibling_id)
        assert chosen.recent_results == "1"
        assert sibling.recent_results == ""

    def test_sibling_match_is_normalized(self, client):
        # Different casing on the prompts: they should still be siblings.
        chosen_id = make_card(SAMPLE_USER["sub"], "Sometimes", "a veces")
        make_card(SAMPLE_USER["sub"], "sometimes", "algunas veces")
        login(client)
        self._start_and_pin(client, chosen_id, "front_to_back")

        client.post("/cards/practice", data={"answer": "algunas veces"})

        with flask_app.app_context():
            chosen = db.session.get(Card, chosen_id)
        assert chosen.recent_results == "1"

    def test_no_siblings_unchanged(self, client):
        # Single-card path must still grade wrong answers as wrong.
        chosen_id = make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        self._start_and_pin(client, chosen_id, "front_to_back")

        client.post("/cards/practice", data={"answer": "chair"})

        with flask_app.app_context():
            chosen = db.session.get(Card, chosen_id)
        assert chosen.recent_results == "0"
        assert chosen.times_correct == 0
        assert chosen.times_practiced == 1

    def test_unrelated_answer_still_wrong(self, client):
        # Even with siblings, a totally unrelated answer is still wrong.
        chosen_id = make_card(SAMPLE_USER["sub"], "sometimes", "a veces")
        make_card(SAMPLE_USER["sub"], "sometimes", "algunas veces")
        login(client)
        self._start_and_pin(client, chosen_id, "front_to_back")

        client.post("/cards/practice", data={"answer": "completely-wrong"})

        with flask_app.app_context():
            chosen = db.session.get(Card, chosen_id)
        assert chosen.recent_results == "0"
        assert chosen.times_correct == 0

    def test_validate_api_picks_best_sibling(self, client):
        chosen_id = make_card(SAMPLE_USER["sub"], "sometimes", "a veces")
        make_card(SAMPLE_USER["sub"], "sometimes", "algunas veces")
        login(client)
        # Advanced mode is required: the validate endpoint refuses hardcore.
        client.post(
            "/cards/practice/start",
            data={"direction": "front_to_back", "difficulty": "advanced"},
        )
        client.get("/cards/practice")
        with client.session_transaction() as sess:
            state = dict(sess["card_practice"])
            state["current_card_id"] = chosen_id
            state["current_prompt_side"] = "front"
            state["current_revealed"] = False
            sess["card_practice"] = state

        response = client.post("/api/cards/validate", json={"input": "algun"})
        assert response.status_code == 200
        data = response.get_json()
        # "algun" can't match "a veces" but is a valid prefix of
        # "algunas veces". The endpoint should pick the better-fitting
        # sibling so the user sees correct/incomplete feedback rather than
        # the all-wrong feedback they'd get against "a veces".
        assert data["words"][0]["status"] in ("correct", "incomplete")


def _make_card_with_history(front, back, recent_results, times_practiced=None):
    """Persist a card with a hand-set practice history.

    Lets dashboard tests bypass the practice loop and land cards in
    specific score buckets directly.
    """
    correct = recent_results.count("1")
    practiced = times_practiced if times_practiced is not None else len(recent_results)
    with flask_app.app_context():
        card = Card(
            user_sub=SAMPLE_USER["sub"],
            front=front,
            back=back,
            recent_results=recent_results,
            times_practiced=practiced,
            times_correct=correct,
        )
        db.session.add(card)
        db.session.commit()
        return card.id


class TestCardsDashboard:
    def test_dashboard_hidden_when_no_cards(self, client):
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert "cards-dashboard-section" not in body

    def test_dashboard_shown_with_zero_attempts_hint(self, client):
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert "cards-dashboard-section" in body
        assert "cards-dashboard-empty-hint" in body
        # No charts when there are no attempts yet.
        assert 'id="cards-distribution-chart"' not in body
        assert 'id="cards-weakest-chart"' not in body
        # Chart.js bundle should not be loaded yet either.
        assert "chart.umd.min.js" not in body

    def test_dashboard_renders_charts_after_practice(self, client):
        _make_card_with_history("weak1", "back1", "0000000000")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-distribution-chart"' in body
        assert 'id="cards-weakest-chart"' in body
        assert "chart.umd.min.js" in body
        assert "cards_dashboard.js" in body
        assert 'id="cards-stats-data"' in body

    def test_buckets_classify_scores_correctly(self, client):
        with flask_app.app_context():
            cards = [
                Card(  # weak: 0%
                    user_sub=SAMPLE_USER["sub"],
                    front="w",
                    back="W",
                    recent_results="0000000000",
                    times_practiced=10,
                    times_correct=0,
                ),
                Card(  # medium: 50% (>= 0.5, < 0.8)
                    user_sub=SAMPLE_USER["sub"],
                    front="m",
                    back="M",
                    recent_results="1111100000",
                    times_practiced=10,
                    times_correct=5,
                ),
                Card(  # strong: 80% (>= 0.8)
                    user_sub=SAMPLE_USER["sub"],
                    front="s",
                    back="S",
                    recent_results="1111111100",
                    times_practiced=10,
                    times_correct=8,
                ),
                Card(  # unpracticed
                    user_sub=SAMPLE_USER["sub"],
                    front="u",
                    back="U",
                    recent_results="",
                    times_practiced=0,
                    times_correct=0,
                ),
            ]
        stats, _ = _build_cards_dashboard_stats(cards)
        assert stats["buckets"] == {
            "weak": 1,
            "medium": 1,
            "strong": 1,
            "unpracticed": 1,
        }
        assert stats["unpracticed"] == 1

    def test_weakest_and_strongest_ordering(self, client):
        with flask_app.app_context():
            # Six practiced cards spanning the full score range, plus one
            # unpracticed (which should appear in none of the ranked lists).
            cards = []
            for i, (results, practiced) in enumerate(
                [
                    ("0000000000", 10),  # 0% — weakest
                    ("1000000000", 10),  # 10%
                    ("1110000000", 10),  # 30%
                    ("1111100000", 10),  # 50%
                    ("1111111100", 10),  # 80%
                    ("1111111111", 50),  # 100%
                ]
            ):
                cards.append(
                    Card(
                        user_sub=SAMPLE_USER["sub"],
                        front=f"c{i}",
                        back=f"C{i}",
                        recent_results=results,
                        times_practiced=practiced,
                        times_correct=results.count("1"),
                    )
                )
            cards.append(
                Card(
                    user_sub=SAMPLE_USER["sub"],
                    front="u",
                    back="U",
                    recent_results="",
                    times_practiced=0,
                    times_correct=0,
                )
            )
        stats, stats_json = _build_cards_dashboard_stats(cards)

        # The three dashboard lists are the three non-unpracticed buckets, so
        # each card lands in exactly one (order within a list is randomised).
        weak_scores = sorted(c.score for c in stats["weak_cards"])
        assert weak_scores == [0.0, 0.1, 0.3]  # score < 0.5
        needs_scores = sorted(c.score for c in stats["needs_work"])
        assert needs_scores == [0.5]  # 0.5 <= score < 0.8
        strong_scores = sorted(c.score for c in stats["strongest"])
        assert strong_scores == [0.8, 1.0]  # score >= 0.8
        # The unpracticed card is the sole member of the "new" list.
        assert [c.front for c in stats["new_cards"]] == ["u"]

        # JSON chart payload still ranks the genuine weakest, capped at 5.
        payload = json.loads(stats_json)
        assert set(payload.keys()) == {"buckets", "weakest"}
        assert len(payload["weakest"]) == 5
        assert payload["weakest"][0]["score"] == 0.0

    def test_stats_json_escapes_closing_script_tag(self, client):
        # A card front containing "</script>" must not be able to break out
        # of the <script type="application/json"> block.
        _make_card_with_history("</script><b>x</b>", "back", "0000000000")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        # Inside the JSON block, the slash should be escaped.
        json_block = body.split('id="cards-stats-data">', 1)[1].split("</script>", 1)[0]
        assert "</script" not in json_block
        assert "<\\/script" in json_block or "<\\/" in json_block

    def test_toggle_button_rendered_when_cards_exist(self, client):
        # Toggle sits in the "My Cards (n)" heading row and controls the
        # dashboard panel.
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-dashboard-toggle"' in body
        assert 'aria-controls="cards-dashboard-panel"' in body
        assert 'id="cards-dashboard-panel"' in body

    def test_dashboard_panel_expanded_by_default(self, client):
        # The panel renders expanded (no `hidden` attribute) so the stats are
        # visible without clicking the toggle.
        make_card(SAMPLE_USER["sub"], "mesa", "table")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        panel_open = body.find('id="cards-dashboard-panel"')
        assert panel_open != -1
        panel_tag = body[panel_open : body.find(">", panel_open) + 1]
        assert " hidden" not in panel_tag
        # And the toggle starts in the expanded (aria-expanded="true") state.
        assert 'aria-expanded="true"' in body

    def test_toggle_button_hidden_when_no_cards(self, client):
        # With no cards there's nothing to chart; the toggle should not show.
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-dashboard-toggle"' not in body
        assert 'id="cards-dashboard-panel"' not in body

    def test_recap_weak_button_hidden_without_weak_cards(self, client):
        # All-strong deck — no weak-section recap button. Other sections
        # (weakest/strongest) still render their own recap buttons.
        _make_card_with_history("strong", "STRONG", "1111111111")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'value="weak"' not in body

    def test_recap_buttons_rendered_per_section(self, client):
        _make_card_with_history("w1", "W1", "0000000000")  # weak
        _make_card_with_history("m1", "M1", "1111100000")  # medium → needs work
        _make_card_with_history("s1", "S1", "1111111111")  # strong
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        # One recap form per section (Weak / Needs work / Strongest).
        assert 'name="recap" value="weak"' in body
        assert 'name="recap" value="needs_work"' in body
        assert 'name="recap" value="strongest"' in body
        assert body.count('class="cards-dashboard-recap-form"') == 3

    def test_new_section_first_and_lists_unpracticed(self, client):
        # An unpracticed card surfaces in a "New" section that sorts ahead of
        # the practiced sections.
        make_card(SAMPLE_USER["sub"], "fresh", "FRESH")  # unpracticed → new
        _make_card_with_history("w", "W", "0000000000")  # weak
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'name="recap" value="new"' in body
        # "New" section renders before "Weak".
        assert body.index('value="new"') < body.index('value="weak"')

    def test_strongest_hidden_when_all_earlier_sections_present(self, client):
        make_card(SAMPLE_USER["sub"], "fresh", "FRESH")  # new
        _make_card_with_history("w", "W", "0000000000")  # weak
        _make_card_with_history("m", "M", "1111100000")  # needs work
        _make_card_with_history("s", "S", "1111111111")  # strong
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'name="recap" value="new"' in body
        assert 'name="recap" value="weak"' in body
        assert 'name="recap" value="needs_work"' in body
        # All three earlier sections are present, so strongest is suppressed.
        assert 'name="recap" value="strongest"' not in body

    def test_strongest_shown_when_an_earlier_section_missing(self, client):
        # No "new" cards → strongest is allowed to show.
        _make_card_with_history("w", "W", "0000000000")  # weak
        _make_card_with_history("m", "M", "1111100000")  # needs work
        _make_card_with_history("s", "S", "1111111111")  # strong
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'name="recap" value="strongest"' in body

    def test_weak_cards_column_lists_only_sub_50_percent(self, client):
        # Strictly under-50% cards land in the Weak column; cards at exactly
        # 50% (medium bucket) do NOT, even though they'd show up in the
        # broader "Needs work" (weakest) column.
        _make_card_with_history("noche", "nacht", "0000000000")  # 0% → weak
        _make_card_with_history("examen", "exam", "1111100000")  # 50% → medium
        _make_card_with_history("libro", "book", "1111111111")  # 100% → strong
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        # The Weak column renders with its strict count.
        assert "cards-dashboard-toplist-weak" in body
        weak_col = body.split("cards-dashboard-toplist-weak", 1)[1].split("</ul>", 1)[0]
        assert "noche" in weak_col
        assert "examen" not in weak_col  # 50% is medium, not weak
        assert "libro" not in weak_col

    def test_weak_cards_column_hidden_when_no_weak_cards(self, client):
        # Only medium/strong/unpracticed cards → the Weak column should not
        # render at all.
        _make_card_with_history("examen", "exam", "1111100000")  # 50% medium
        _make_card_with_history("libro", "book", "1111111111")  # strong
        make_card(SAMPLE_USER["sub"], "untouched", "card")  # unpracticed
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert "cards-dashboard-toplist-weak" not in body


class TestPracticeWeakOnly:
    def test_weak_only_practice_only_serves_weak_cards(self, client):
        weak_id = _make_card_with_history("w", "W", "0000000000")
        strong_id = _make_card_with_history("s", "S", "1111111111")
        login(client)
        client.post(
            "/cards/practice/start",
            data={
                "weak_only": "1",
                "direction": "back_to_front",
                "sampling_mode": "prioritized",
                "difficulty": "hardcore",
            },
        )
        client.get("/cards/practice")
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["weak_only"] is True
        # Only the weak card may appear.
        assert state["current_card_id"] == weak_id
        assert state["current_card_id"] != strong_id

    def test_weak_only_count_matches_weak_pool_size(self, client):
        # Three weak cards + a strong one → session count clamps to 3.
        for i in range(3):
            _make_card_with_history(f"w{i}", f"W{i}", "0000000000")
        _make_card_with_history("s", "S", "1111111111")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"weak_only": "1", "direction": "back_to_front"},
        )
        with client.session_transaction() as sess:
            assert sess["card_practice"]["count"] == 3

    def test_weak_only_redirects_with_flash_when_no_weak_cards(self, client):
        _make_card_with_history("s", "S", "1111111111")
        login(client)
        response = client.post(
            "/cards/practice/start",
            data={"weak_only": "1", "direction": "back_to_front"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/cards")
        # No practice session was created.
        with client.session_transaction() as sess:
            assert "card_practice" not in sess

    def test_weak_only_excludes_unpracticed_cards(self, client):
        # Unpracticed cards aren't "weak" — they're untouched. With only an
        # unpracticed card present, the CTA should bail out.
        make_card(SAMPLE_USER["sub"], "untouched", "card")
        login(client)
        response = client.post(
            "/cards/practice/start",
            data={"weak_only": "1", "direction": "back_to_front"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert "card_practice" not in sess


class TestRecapModes:
    def test_recap_new_samples_unpracticed_cards(self, client):
        # The "new" recap pool is exactly the unpracticed cards.
        new_ids = [make_card(SAMPLE_USER["sub"], f"n{i}", f"N{i}") for i in range(3)]
        practiced_id = _make_card_with_history("w", "W", "0000000000")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"recap": "new", "direction": "back_to_front", "count": "2"},
        )
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["sampling_mode"] == "random"
        assert state["count"] == 2
        assert sorted(state["allowed_card_ids"]) == sorted(new_ids)
        assert practiced_id not in state["allowed_card_ids"]

    def test_recap_new_redirects_when_no_unpracticed_cards(self, client):
        _make_card_with_history("w", "W", "0000000000")  # everything practiced
        login(client)
        response = client.post(
            "/cards/practice/start",
            data={"recap": "new", "direction": "back_to_front"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert "card_practice" not in sess

    def test_recap_needs_work_samples_medium_bucket(self, client):
        # The "needs work" recap pool is exactly the medium bucket (0.5–0.8);
        # weak and strong cards are excluded. The session size comes from the
        # "Cards per round" count, not the pool size.
        medium_ids = [
            _make_card_with_history(f"m{r}", "x", r)
            for r in ("1111100000", "1111110000", "1111111000")  # 50/60/70%
        ]
        weak_id = _make_card_with_history("w", "W", "0000000000")
        strong_id = _make_card_with_history("s", "S", "1111111111")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"recap": "needs_work", "direction": "back_to_front", "count": "2"},
        )
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["sampling_mode"] == "random"
        assert state["count"] == 2  # taken from "Cards per round"
        assert sorted(state["allowed_card_ids"]) == sorted(medium_ids)
        assert weak_id not in state["allowed_card_ids"]
        assert strong_id not in state["allowed_card_ids"]

    def test_recap_weakest_is_alias_for_needs_work(self, client):
        # Legacy callers may still POST recap=weakest.
        medium_id = _make_card_with_history("m", "M", "1111100000")  # 50%
        login(client)
        client.post(
            "/cards/practice/start",
            data={"recap": "weakest", "direction": "back_to_front"},
        )
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["allowed_card_ids"] == [medium_id]

    def test_recap_strongest_samples_strong_bucket(self, client):
        # The "strongest" recap pool is exactly the strong bucket (>=0.8); the
        # count clamps down to the pool size when it would otherwise overshoot.
        strong_ids = [
            _make_card_with_history(f"s{r}", "x", r)
            for r in ("1111111100", "1111111110", "1111111111")  # 80/90/100%
        ]
        weak_id = _make_card_with_history("w", "W", "0000000000")
        medium_id = _make_card_with_history("m", "M", "1111100000")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"recap": "strongest", "direction": "back_to_front", "count": "50"},
        )
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["sampling_mode"] == "random"
        assert state["count"] == 3  # clamped to pool size
        assert sorted(state["allowed_card_ids"]) == sorted(strong_ids)
        assert weak_id not in state["allowed_card_ids"]
        assert medium_id not in state["allowed_card_ids"]

    def test_recap_only_serves_snapshotted_cards(self, client):
        medium_id = _make_card_with_history("m", "M", "1111100000")  # 50% → needs work
        _make_card_with_history("s", "S", "1111111111")  # strong, excluded
        login(client)
        client.post(
            "/cards/practice/start",
            data={"recap": "needs_work", "direction": "back_to_front"},
        )
        client.get("/cards/practice")
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["current_card_id"] == medium_id

    def test_recap_weak_samples_weak_bucket(self, client):
        weak_id = _make_card_with_history("w", "W", "0000000000")
        _make_card_with_history("s", "S", "1111111111")
        login(client)
        client.post(
            "/cards/practice/start",
            data={"recap": "weak", "direction": "back_to_front"},
        )
        with client.session_transaction() as sess:
            state = sess["card_practice"]
        assert state["weak_only"] is True
        assert state["sampling_mode"] == "random"
        assert state["allowed_card_ids"] == [weak_id]
        assert state["count"] == 1  # clamped to the single weak card

    def test_recap_needs_work_redirects_when_bucket_empty(self, client):
        # Only an unpracticed card → the medium bucket is empty → bail out.
        make_card(SAMPLE_USER["sub"], "untouched", "card")
        login(client)
        response = client.post(
            "/cards/practice/start",
            data={"recap": "needs_work", "direction": "back_to_front"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert "card_practice" not in sess


class TestDeckShareCreate:
    def test_share_requires_login(self, client):
        response = client.post("/api/cards/share")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_share_rejects_empty_deck(self, client):
        login(client)
        response = client.post("/api/cards/share")
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        with flask_app.app_context():
            assert db.session.query(DeckShare).count() == 0

    def test_share_snapshots_deck(self, client):
        make_card(SAMPLE_USER["sub"], "uno", "one")
        make_card(SAMPLE_USER["sub"], "dos", "two")
        login(client)
        response = client.post("/api/cards/share")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["count"] == 2
        assert "/cards/import/" in data["url"]
        with flask_app.app_context():
            share = db.session.query(DeckShare).one()
            assert share.owner_sub == SAMPLE_USER["sub"]
            assert share.owner_name == SAMPLE_USER["name"]
            pairs = {(c["front"], c["back"]) for c in share.cards}
            assert pairs == {("uno", "one"), ("dos", "two")}

    def test_share_does_not_leak_other_users_cards(self, client):
        make_card(OTHER_USER["sub"], "secret", "hidden")
        make_card(SAMPLE_USER["sub"], "uno", "one")
        login(client)
        response = client.post("/api/cards/share")
        assert response.status_code == 200
        with flask_app.app_context():
            share = db.session.query(DeckShare).one()
            pairs = {(c["front"], c["back"]) for c in share.cards}
            assert pairs == {("uno", "one")}

    def test_share_snapshot_unaffected_by_later_edits(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "uno", "one")
        login(client)
        client.post("/api/cards/share")
        # Owner edits the card after sharing — snapshot must not change.
        client.patch(f"/api/cards/{card_id}", json={"front": "uno", "back": "ONE!"})
        with flask_app.app_context():
            share = db.session.query(DeckShare).one()
            pairs = {(c["front"], c["back"]) for c in share.cards}
            assert pairs == {("uno", "one")}


def _make_share(owner_sub, owner_name, cards):
    with flask_app.app_context():
        share = DeckShare(
            token="t" + "0" * 31,
            owner_sub=owner_sub,
            owner_name=owner_name,
            cards_json=json.dumps([{"front": f, "back": b} for f, b in cards]),
        )
        db.session.add(share)
        db.session.commit()
        return share.token


class TestDeckImportPreview:
    def test_preview_redirects_logged_out_user_to_login(self, client):
        token = _make_share(OTHER_USER["sub"], "Grace", [("uno", "one")])
        response = client.get(f"/cards/import/{token}")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        with client.session_transaction() as sess:
            assert sess.get("pending_import_token") == token

    def test_preview_renders_when_logged_in(self, client):
        token = _make_share(
            OTHER_USER["sub"], "Grace", [("uno", "one"), ("dos", "two")]
        )
        login(client)
        response = client.get(f"/cards/import/{token}")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        # Owner name and count both surface on the page.
        assert "Grace" in body
        assert "2" in body

    def test_preview_unknown_token_404s(self, client):
        login(client)
        response = client.get("/cards/import/does-not-exist")
        assert response.status_code == 404


class TestDeckImportApply:
    def test_import_requires_login(self, client):
        token = _make_share(OTHER_USER["sub"], "Grace", [("uno", "one")])
        response = client.post(f"/cards/import/{token}")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_import_copies_cards_into_recipient(self, client):
        token = _make_share(
            OTHER_USER["sub"], "Grace", [("uno", "one"), ("dos", "two")]
        )
        login(client)
        response = client.post(f"/cards/import/{token}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/cards")
        with flask_app.app_context():
            mine = db.session.query(Card).filter_by(user_sub=SAMPLE_USER["sub"]).all()
            pairs = {(c.front, c.back) for c in mine}
            assert pairs == {("uno", "one"), ("dos", "two")}

    def test_import_skips_duplicates(self, client):
        # Recipient already has "uno"→"one"; import has 2 cards, one is dup.
        make_card(SAMPLE_USER["sub"], "uno", "one")
        token = _make_share(
            OTHER_USER["sub"], "Grace", [("uno", "one"), ("dos", "two")]
        )
        login(client)
        client.post(f"/cards/import/{token}")
        with flask_app.app_context():
            mine = db.session.query(Card).filter_by(user_sub=SAMPLE_USER["sub"]).all()
            pairs = {(c.front, c.back) for c in mine}
            # No duplicate "uno"→"one" — count stays at 2 total.
            assert pairs == {("uno", "one"), ("dos", "two")}
            assert len(mine) == 2

    def test_import_dedupe_is_normalized(self, client):
        # Recipient has "Uno" with trailing whitespace; share has "uno".
        make_card(SAMPLE_USER["sub"], " Uno ", "One")
        token = _make_share(OTHER_USER["sub"], "Grace", [("uno", "one")])
        login(client)
        client.post(f"/cards/import/{token}")
        with flask_app.app_context():
            mine = db.session.query(Card).filter_by(user_sub=SAMPLE_USER["sub"]).all()
            assert len(mine) == 1  # the import was skipped as a duplicate

    def test_import_within_share_dedupes(self, client):
        # The shared deck itself contains duplicates — only one copy lands.
        token = _make_share(
            OTHER_USER["sub"],
            "Grace",
            [("uno", "one"), ("uno", "one"), ("dos", "two")],
        )
        login(client)
        client.post(f"/cards/import/{token}")
        with flask_app.app_context():
            mine = db.session.query(Card).filter_by(user_sub=SAMPLE_USER["sub"]).all()
            pairs = {(c.front, c.back) for c in mine}
            assert pairs == {("uno", "one"), ("dos", "two")}

    def test_import_unknown_token_redirects_with_flash(self, client):
        login(client)
        response = client.post("/cards/import/does-not-exist", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/cards")
        with flask_app.app_context():
            assert db.session.query(Card).count() == 0

    def test_share_button_rendered_when_cards_exist(self, client):
        make_card(SAMPLE_USER["sub"], "uno", "one")
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-share-btn"' in body

    def test_share_button_hidden_when_no_cards(self, client):
        login(client)
        body = client.get("/cards").data.decode("utf-8")
        assert 'id="cards-share-btn"' not in body
