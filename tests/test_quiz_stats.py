"""Tests for the usage counts: drills people answered and finished."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import SQLAlchemyError

import quiz_stats
from app import app as flask_app
from config import QUESTIONS_PER_QUIZ
from models import QuizRun, db


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


QUIZ_PATHS = {
    "easy": "/es/quiz/easy",
    "advanced": "/es/quiz/advanced",
    "hardcore": "/es/quiz/hardcore",
}


def _answer(client, path, times=1, answer="x"):
    """Load the question and submit an answer (right or wrong doesn't matter)."""
    response = None
    for _ in range(times):
        client.get(path)
        response = client.post(path, data={"answer": answer})
    return response


def _runs():
    return db.session.execute(db.select(QuizRun)).scalars().all()


class TestStarted:
    def test_starting_a_drill_counts_nothing(self, client):
        client.post("/es/start", data={"mode": "advanced"})
        client.get("/es/quiz/advanced")
        assert _runs() == []

    @pytest.mark.parametrize("mode", ["easy", "advanced", "hardcore"])
    def test_first_answer_counts_the_drill(self, client, mode):
        client.post("/es/start", data={"mode": mode})
        _answer(client, QUIZ_PATHS[mode])

        [run] = _runs()
        assert (run.lang, run.mode, run.source) == ("es", mode, "form")
        assert run.finished_at is None

    def test_later_answers_add_no_rows(self, client):
        client.post("/es/start", data={"mode": "easy"})
        _answer(client, "/es/quiz/easy", times=5)
        assert len(_runs()) == 1

    def test_reveal_counts_as_an_answer(self, client):
        client.post("/es/start", data={"mode": "advanced"})
        client.get("/es/quiz/advanced")
        client.post("/es/quiz/advanced", data={"reveal": "1"})
        assert len(_runs()) == 1

    def test_each_new_drill_is_counted_separately(self, client):
        for _ in range(2):
            client.post("/es/start", data={"mode": "easy"})
            _answer(client, "/es/quiz/easy")
        runs = _runs()
        assert len(runs) == 2
        assert runs[0].token != runs[1].token

    def test_numeral_system_is_recorded(self, client):
        client.get("/cy/numbers?system=traditional")
        client.post("/cy/start", data={"mode": "advanced", "system": "traditional"})
        _answer(client, "/cy/quiz/advanced")
        [run] = _runs()
        assert (run.lang, run.number_system) == ("cy", "traditional")


class TestSharedLinks:
    """A preset link seeds a drill on GET, so crawlers that follow it must
    not be counted; a person answering it must be."""

    def test_opening_a_shared_link_counts_nothing(self, client):
        response = client.get("/es/numbers?mode=advanced&range=1-20")
        assert response.status_code == 200
        client.get("/es/quiz/advanced")
        assert _runs() == []

    def test_answering_a_shared_link_counts_as_link(self, client):
        client.get("/es/numbers?mode=advanced&range=1-20")
        _answer(client, "/es/quiz/advanced")
        [run] = _runs()
        assert (run.mode, run.source) == ("advanced", "link")

    def test_shared_listening_link(self, client):
        client.get("/es/listening?range=1-20")
        _answer(client, "/es/listen", answer="1")
        [run] = _runs()
        assert (run.mode, run.source) == ("audio", "link")


class TestListening:
    def test_listening_drill_counts_and_finishes(self, client):
        client.post("/es/listen/start", data={"magnitude_level": "1"})
        response = _answer(client, "/es/listen", times=QUESTIONS_PER_QUIZ, answer="1")
        assert "/es/results" in response.headers["Location"]
        [run] = _runs()
        assert (run.mode, run.source) == ("audio", "form")
        assert run.finished_at is not None


class TestFinished:
    def test_last_answer_marks_the_drill_finished(self, client):
        client.post("/es/start", data={"mode": "easy"})
        _answer(client, "/es/quiz/easy", times=QUESTIONS_PER_QUIZ - 1)
        assert _runs()[0].finished_at is None

        response = _answer(client, "/es/quiz/easy")
        assert "/es/results" in response.headers["Location"]
        assert _runs()[0].finished_at is not None

    def test_resubmitting_after_the_end_does_not_refinish(self, client):
        client.post("/es/start", data={"mode": "advanced"})
        _answer(client, "/es/quiz/advanced", times=QUESTIONS_PER_QUIZ)
        first_finish = _runs()[0].finished_at

        # The back button and a resubmit go through _results_redirect again.
        client.post("/es/quiz/advanced", data={"answer": "x"})
        [run] = _runs()
        assert run.finished_at == first_finish

    def test_abandoned_drill_stays_unfinished(self, client):
        client.post("/es/start", data={"mode": "easy"})
        _answer(client, "/es/quiz/easy", times=3)
        client.post("/restart")
        [run] = _runs()
        assert run.finished_at is None


class TestRobustness:
    def test_session_from_before_the_counter_is_not_counted(self, client):
        """A drill already running at deploy time has no token: skip it."""
        client.post("/es/start", data={"mode": "easy"})
        with client.session_transaction() as sess:
            del sess["quiz_run"]
        response = _answer(client, "/es/quiz/easy", times=QUESTIONS_PER_QUIZ)
        assert "/es/results" in response.headers["Location"]
        assert _runs() == []

    def test_duplicate_first_answer_counts_once(self, app):
        """A double click can send the first answer twice with the same cookie."""
        token = quiz_stats.new_run_token()
        with app.test_request_context():
            for _ in range(2):
                quiz_stats.record_started(token, "es", "easy", "default", "form")
        assert len(_runs()) == 1

    def test_database_error_does_not_break_the_drill(self, client, monkeypatch):
        def broken_commit():
            raise SQLAlchemyError("database is down")

        monkeypatch.setattr(db.session, "commit", broken_commit)
        client.post("/es/start", data={"mode": "easy"})
        response = _answer(client, "/es/quiz/easy", times=QUESTIONS_PER_QUIZ)
        assert response.status_code == 302
        assert "/es/results" in response.headers["Location"]
        monkeypatch.undo()
        assert _runs() == []


def _add_run(
    started_at, finished=True, lang="es", mode="easy", system="default", source="form"
):
    db.session.add(
        QuizRun(
            token=quiz_stats.new_run_token(),
            lang=lang,
            mode=mode,
            number_system=system,
            source=source,
            started_at=started_at,
            finished_at=started_at + timedelta(minutes=2) if finished else None,
        )
    )
    db.session.commit()


class TestReport:
    def test_language_label(self):
        assert quiz_stats.language_label("es", "default") == "es"
        assert quiz_stats.language_label("es", None) == "es"
        assert quiz_stats.language_label("cy", "traditional") == "cy (traditional)"

    def test_summary_counts_by_day_and_dimension(self):
        now = datetime.now(timezone.utc)
        _add_run(now)
        _add_run(now, finished=False, mode="audio", source="link")
        _add_run(now - timedelta(days=1), lang="cy", system="traditional")
        _add_run(now - timedelta(days=40))  # outside the window

        stats = quiz_stats.summarize(30)

        assert stats["total"] == (3, 2)
        assert len(stats["by_day"]) == 30
        assert stats["by_day"][-1] == (now.date(), 2, 1)
        assert stats["by_day"][-2] == ((now - timedelta(days=1)).date(), 1, 1)
        assert stats["by_language"] == [("es", 2, 1), ("cy (traditional)", 1, 1)]
        assert dict((k, (s, f)) for k, s, f in stats["by_mode"]) == {
            "easy": (2, 2),
            "listening": (1, 0),
        }
        assert dict((k, (s, f)) for k, s, f in stats["by_source"]) == {
            "form": (2, 2),
            "link": (1, 0),
        }

    def test_cli_report(self, app):
        _add_run(datetime.now(timezone.utc))
        result = app.test_cli_runner().invoke(args=["quiz-stats", "--days", "7"])
        assert result.exit_code == 0, result.output
        assert "total: 1 started, 1 finished (100% finished)" in result.output
        assert "language" in result.output and "started from" in result.output

    def test_cli_report_with_no_data(self, app):
        result = app.test_cli_runner().invoke(args=["quiz-stats"])
        assert result.exit_code == 0, result.output
        assert "total: 0 started, 0 finished" in result.output
        assert "started from" not in result.output
