"""Tests for the English verb-conjugation practice section.

The generic conjugation mechanics are covered by tests/test_conjugate.py
(Spanish) and the multi-language plumbing by tests/test_conjugate_de.py; this
file covers what English does differently: five person slots instead of six,
cells with no form (stative verbs, modals), a second accepted form where British
usage has two, American forms marked wrong, and infinitives cited with "to".
The index-card side lives in tests/test_card_verb_sync.py.
"""

import json
import re
from pathlib import Path

import pytest

from app import _build_conjugation_hint
from app import app as flask_app
from config import SUPPORTED_UI_LANGUAGES
from conjugation_config import conj_hint_model_verbs, conj_persons, conj_tense_keys
from languages.en import conjugations as en_conjugations
from models import ConjugationStat, VerbCard, db
from tools.generate_conjugations_en import POPULAR_VERBS, build_pool, build_variants

LEARN_UI_LANGUAGES = ["en", "de", "es", "it", "fr", "pt", "ar", "uk"]
POOL_PATH = Path(en_conjugations.__file__).parent / "conjugations.json"
VARIANTS_PATH = Path(en_conjugations.__file__).parent / "conjugation_variants.json"


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


def login(client, user=SAMPLE_USER):
    with client.session_transaction() as sess:
        sess["user"] = user


def add_verb(user_sub, infinitive, lang="en"):
    with flask_app.app_context():
        verb = VerbCard(user_sub=user_sub, lang=lang, infinitive=infinitive)
        db.session.add(verb)
        db.session.commit()
        return verb.id


def start(client, **overrides):
    data = {
        "tenses": "present-simple",
        "difficulty": "hardcore",
        "sampling_mode": "random",
        "count": "3",
    }
    data.update(overrides)
    return client.post("/en/conjugate/practice/start", data=data)


def force_question(client, verb_id, infinitive, tense, person, difficulty="hardcore"):
    """Start a drill and pin its current question."""
    start(client, tenses=tense, difficulty=difficulty)
    with client.session_transaction() as sess:
        state = sess["conjugate_practice"]
        state["current"] = {
            "verb_id": verb_id,
            "infinitive": infinitive,
            "tense_key": tense,
            "person_index": person,
            "correct_answer": en_conjugations.get_verb_forms(infinitive)[tense][person],
        }
        sess["conjugate_practice"] = state


def session_score(client):
    with client.session_transaction() as sess:
        return sess["conjugate_practice"]["score"]


# ----- The committed English pool ---------------------------------------------


class TestPool:
    def test_committed_files_match_the_generator(self):
        """A hand edit to the JSON would be lost on the next regeneration."""
        pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
        variants = json.loads(VARIANTS_PATH.read_text(encoding="utf-8"))
        assert pool == build_pool(POPULAR_VERBS)
        assert variants == build_variants(POPULAR_VERBS)

    def test_every_cell_has_one_slot_per_person_and_every_tense(self):
        pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
        slots = len(conj_persons("en"))
        assert slots == 5
        assert all(
            set(tenses) == conj_tense_keys("en")
            and all(len(forms) == slots for forms in tenses.values())
            for tenses in pool.values()
        )

    def test_hint_models_have_every_form(self):
        """The hint table must never render a blank for its own example verbs."""
        for verb in conj_hint_model_verbs("en"):
            forms = en_conjugations.get_verb_forms(verb)
            assert all(all(cell) for cell in forms.values()), verb

    @pytest.mark.parametrize(
        "verb, tense, person, form",
        [
            ("be", "present-simple", 0, "am"),
            ("be", "present-simple", 2, "is"),
            ("be", "past-simple", 2, "was"),
            ("be", "past-simple", 4, "were"),
            ("be", "present-perfect", 2, "has been"),
            ("have", "present-simple", 2, "has"),
            ("have", "present-continuous", 0, "am having"),
            ("do", "present-simple", 2, "does"),
            ("go", "present-simple", 2, "goes"),
            ("go", "past-simple", 0, "went"),
            ("go", "present-perfect", 2, "has gone"),
            ("go", "future-going-to", 4, "are going to go"),
            ("work", "future-will", 2, "will work"),
            ("work", "conditional", 3, "would work"),
            ("work", "past-perfect", 1, "had worked"),
            ("work", "past-continuous", 2, "was working"),
            ("work", "present-perfect-continuous", 2, "has been working"),
            ("study", "present-simple", 2, "studies"),
            ("study", "past-simple", 0, "studied"),
            ("stop", "past-simple", 0, "stopped"),
            ("stop", "present-continuous", 0, "am stopping"),
            ("die", "present-continuous", 0, "am dying"),
            ("make", "present-continuous", 0, "am making"),
            ("see", "present-continuous", 0, "am seeing"),
            ("visit", "past-simple", 0, "visited"),
            ("panic", "past-simple", 0, "panicked"),
            # British forms
            ("travel", "past-simple", 0, "travelled"),
            ("cancel", "present-continuous", 0, "am cancelling"),
            ("get", "present-perfect", 0, "have got"),
            ("learn", "past-simple", 0, "learnt"),
            ("fit", "past-simple", 0, "fitted"),
        ],
    )
    def test_form(self, verb, tense, person, form):
        assert en_conjugations.get_verb_forms(verb)[tense][person] == form

    def test_stative_verbs_have_no_continuous(self):
        know = en_conjugations.get_verb_forms("know")
        assert know["present-continuous"] == [None] * 5
        assert know["past-continuous"] == [None] * 5
        assert know["present-perfect-continuous"] == [None] * 5
        assert know["present-simple"][2] == "knows"
        # A verb with a common dynamic sense keeps them.
        think = en_conjugations.get_verb_forms("think")
        assert think["present-continuous"][0] == "am thinking"

    def test_modals_only_exist_where_they_have_a_form(self):
        can = en_conjugations.get_verb_forms("can")
        assert can["present-simple"] == ["can"] * 5
        assert can["past-simple"] == ["could"] * 5
        assert can["present-perfect"] == [None] * 5
        assert can["future-will"] == [None] * 5

    def test_search_ranks_frequency_order(self):
        assert en_conjugations.search_verbs("wa")[0] == "want"


# ----- Adding verbs -----------------------------------------------------------


class TestAddEnglishVerb:
    def test_add_verb_with_lang(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "write", "lang": "en"})
        assert resp.status_code == 200
        assert resp.get_json()["verb"]["lang"] == "en"

    @pytest.mark.parametrize("typed", ["to go", "To Go", "  to go ", "GO"])
    def test_verb_cited_with_to_is_found(self, client, typed):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": typed, "lang": "en"})
        assert resp.status_code == 200
        assert resp.get_json()["verb"]["infinitive"] == "go"

    def test_verb_cited_with_to_through_the_form_fallback(self, client):
        login(client)
        client.post("/en/conjugate/add", data={"infinitive": "to go"})
        with flask_app.app_context():
            assert db.session.query(VerbCard).one().infinitive == "go"

    def test_to_is_only_stripped_for_english(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "to comer", "lang": "es"})
        assert resp.status_code == 400

    def test_search_understands_to(self, client):
        login(client)
        results = client.get("/api/verbs/search?q=to+wr&lang=en").get_json()["results"]
        assert results[0] == "write"

    def test_english_verb_rejected_in_other_pools(self, client):
        login(client)
        for lang in ("es", "it", "de"):
            resp = client.post("/api/verbs", json={"infinitive": "write", "lang": lang})
            assert resp.status_code == 400, lang
            assert resp.get_json()["unsupported"] is True

    def test_foreign_verbs_rejected_in_english_pool(self, client):
        login(client)
        for verb in ("hablar", "machen", "parlare"):
            resp = client.post("/api/verbs", json={"infinitive": verb, "lang": "en"})
            assert resp.status_code == 400, verb

    def test_american_spelling_of_an_infinitive_is_not_a_second_verb(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "practice", "lang": "en"})
        assert resp.status_code == 400


class TestManagePage:
    def test_renders_without_optional_person_toggle(self, client):
        add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        html = client.get("/en/conjugate").get_data(as_text=True)
        assert "Present perfect continuous" in html
        assert "include_vosotros" not in html

    def test_tense_label_is_not_printed_twice(self, client):
        """Its native label and its English one are the same words."""
        add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        html = client.get("/en/conjugate").get_data(as_text=True)
        assert 'name="tenses"' in html
        assert "conjugate-tense-en" not in html

    def test_other_languages_still_show_both_labels(self, client):
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        login(client)
        html = client.get("/de/conjugate").get_data(as_text=True)
        assert "conjugate-tense-en" in html

    def test_practice_form_names_its_language_for_the_saved_settings(self, client):
        """conjugate_practice_prefs.js keys localStorage by this."""
        add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        html = client.get("/en/conjugate").get_data(as_text=True)
        form = re.search(r"<form[^>]*conjugate-practice-form[^>]*>", html).group(0)
        assert 'data-lang="en"' in form

    def test_verb_lists_are_isolated_per_lang(self, client):
        add_verb(SAMPLE_USER["sub"], "write")
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        login(client)
        html = client.get("/en/conjugate").get_data(as_text=True)
        assert "write" in html
        assert "comer" not in html


# ----- Practice ---------------------------------------------------------------


class TestEnglishPractice:
    def test_start_records_lang_and_five_persons(self, client):
        add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        assert start(client).status_code == 302
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["lang"] == "en"
            assert state["persons"] == [0, 1, 2, 3, 4]

    def test_question_uses_english_pool_and_scores(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        start(client)
        assert client.get("/en/conjugate/practice").status_code == 200
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
        forms = en_conjugations.get_verb_forms("write")
        assert (
            current["correct_answer"]
            == forms[current["tense_key"]][current["person_index"]]
        )
        client.post(
            "/en/conjugate/practice", data={"answer": current["correct_answer"]}
        )
        with flask_app.app_context():
            verb = db.session.get(VerbCard, verb_id)
            assert (verb.times_practiced, verb.times_correct) == (1, 1)
            assert db.session.query(ConjugationStat).one().lang == "en"

    def test_a_drill_can_run_through_every_person(self, client):
        add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        start(client, count="5")
        asked = set()
        for _ in range(5):
            client.get("/en/conjugate/practice")
            with client.session_transaction() as sess:
                asked.add(sess["conjugate_practice"]["current"]["person_index"])
            client.post("/en/conjugate/practice", data={"answer": "x"})
        assert asked == {0, 1, 2, 3, 4}

    def test_stative_verb_never_asked_in_a_continuous_tense(self, client):
        add_verb(SAMPLE_USER["sub"], "know")
        login(client)
        client.post(
            "/en/conjugate/practice/start",
            data={
                "tenses": ["present-continuous", "present-simple"],
                "difficulty": "hardcore",
                "sampling_mode": "random",
                "count": "10",
            },
        )
        for _ in range(5):
            client.get("/en/conjugate/practice")
            with client.session_transaction() as sess:
                current = sess["conjugate_practice"].get("current")
            assert current["tense_key"] == "present-simple"
            client.post("/en/conjugate/practice", data={"answer": "x"})

    def test_a_selection_with_no_forms_ends_instead_of_asking_a_blank(self, client):
        add_verb(SAMPLE_USER["sub"], "must")
        login(client)
        start(client, tenses="past-perfect")
        resp = client.get("/en/conjugate/practice", follow_redirects=True)
        assert resp.status_code == 200
        assert "conjugate-prompt-verb" not in resp.get_data(as_text=True)

    def test_hint_rows_line_up_with_the_forms(self, client):
        """The template indexes forms by row, so a skipped slot would shift them."""
        with flask_app.test_request_context():
            hint = _build_conjugation_hint("en", "present-simple", 4, "en")
        assert [p["label"] for p in hint["persons"]] == [
            "I",
            "you",
            "he/she/it",
            "we",
            "they",
        ]
        assert [p["highlight"] for p in hint["persons"]] == [
            False,
            False,
            False,
            False,
            True,
        ]
        go = next(m for m in hint["models"] if m["infinitive"] == "go")
        assert go["forms"] == ["go", "go", "goes", "go", "go"]

    def test_hint_renders_in_advanced_mode(self, client):
        add_verb(SAMPLE_USER["sub"], "write")
        login(client)
        start(client, difficulty="advanced")
        html = client.get("/en/conjugate/practice").get_data(as_text=True)
        assert "<th>stop</th>" in html
        assert "<td>goes</td>" in html


class TestAcceptedForms:
    """British usage accepts two forms in places; American forms are wrong."""

    @pytest.mark.parametrize(
        "verb, tense, person, typed, score",
        [
            # What the pool stores.
            ("learn", "past-simple", 0, "learnt", 1),
            ("travel", "past-simple", 0, "travelled", 1),
            ("get", "present-perfect", 0, "have got", 1),
            # What British usage also accepts.
            ("learn", "past-simple", 0, "learned", 1),
            ("learn", "present-perfect", 2, "has learned", 1),
            ("burn", "past-perfect", 0, "had burned", 1),
            ("dream", "past-simple", 3, "dreamed", 1),
            ("show", "present-perfect", 0, "have showed", 1),
            ("prove", "present-perfect", 0, "have proven", 1),
            ("hang", "past-simple", 0, "hanged", 1),
            ("focus", "past-simple", 0, "focussed", 1),
            ("focus", "present-continuous", 0, "am focussing", 1),
            # "lie" is two verbs in one spelling.
            ("lie", "past-simple", 0, "lied", 1),
            ("lie", "present-perfect", 0, "have lied", 1),
            # -ize is British (Oxford) spelling too.
            ("realise", "past-simple", 0, "realized", 1),
            ("organise", "present-continuous", 0, "am organizing", 1),
            # A variant belongs to its tense, not to the verb.
            ("prove", "past-simple", 0, "proven", 0),
            ("show", "past-simple", 0, "shown", 0),
            # American forms are marked wrong, as in the number deck.
            ("get", "present-perfect", 0, "have gotten", 0),
            ("travel", "past-simple", 0, "traveled", 0),
            ("cancel", "present-continuous", 0, "am canceling", 0),
            ("fit", "past-simple", 0, "fit", 0),
            ("analyse", "past-simple", 0, "analyzed", 0),
            # -ise everywhere, so no -ize.
            ("advise", "past-simple", 0, "advized", 0),
            # Still wrong for every other reason.
            ("go", "past-simple", 0, "goed", 0),
            ("go", "present-perfect", 0, "have went", 0),
            ("know", "present-simple", 2, "know", 0),
            ("can", "present-simple", 2, "cans", 0),
        ],
    )
    def test_answer(self, client, verb, tense, person, typed, score):
        verb_id = add_verb(SAMPLE_USER["sub"], verb)
        login(client)
        force_question(client, verb_id, verb, tense, person)
        client.post("/en/conjugate/practice", data={"answer": typed})
        assert session_score(client) == score

    def test_answer_ignores_case(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "be")
        login(client)
        force_question(client, verb_id, "be", "present-simple", 0)
        client.post("/en/conjugate/practice", data={"answer": "AM"})
        assert session_score(client) == 1

    def test_hardcore_client_is_told_every_accepted_form(self, client):
        """Otherwise a right answer flashes red just before scoring as right."""
        verb_id = add_verb(SAMPLE_USER["sub"], "learn")
        login(client)
        force_question(client, verb_id, "learn", "past-simple", 0)
        html = client.get("/en/conjugate/practice").get_data(as_text=True)
        assert """data-accepted-answers='["learnt", "learned"]'""" in html

    def test_advanced_mode_leaks_no_answers(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "learn")
        login(client)
        force_question(
            client, verb_id, "learn", "past-simple", 0, difficulty="advanced"
        )
        html = client.get("/en/conjugate/practice").get_data(as_text=True)
        assert "data-accepted-answers" not in html
        assert "data-correct-answer" not in html

    def test_live_validation_accepts_a_variant(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "learn")
        login(client)
        force_question(
            client, verb_id, "learn", "present-perfect", 0, difficulty="advanced"
        )
        result = client.post(
            "/api/conjugate/validate", json={"input": "have learned"}
        ).get_json()
        assert result["is_correct"] is True
        assert result["is_complete"] is True

    def test_german_hardcore_client_also_gets_the_bare_form(self, client):
        """The same list carries the pronoun-less Sie-imperative."""
        verb_id = add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        login(client)
        client.post(
            "/de/conjugate/practice/start",
            data={"tenses": "imperativ", "difficulty": "hardcore", "count": "1"},
        )
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            state["current"] = {
                "verb_id": verb_id,
                "infinitive": "machen",
                "tense_key": "imperativ",
                "person_index": 5,
                "correct_answer": "machen Sie",
            }
            sess["conjugate_practice"] = state
        html = client.get("/de/conjugate/practice").get_data(as_text=True)
        assert """data-accepted-answers='["machen Sie", "machen"]'""" in html


# ----- Learn pages ------------------------------------------------------------


def learn_page(ui_lang):
    path = Path(flask_app.root_path) / "templates"
    return (path / f"learn_conjugations_en_{ui_lang}.html").read_text(encoding="utf-8")


def pool_words():
    """Every word the pool or its variants can produce, plus the pronouns."""
    words = {"i", "you", "he", "she", "it", "we", "they"}
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    variants = json.loads(VARIANTS_PATH.read_text(encoding="utf-8"))
    for verb, tenses in pool.items():
        words.add(verb)
        for forms in tenses.values():
            words.update(w for form in forms if form for w in form.split())
    for tenses in variants.values():
        for accepted in tenses.values():
            for others in accepted.values():
                words.update(w for form in others for w in form.split())
    return words


class TestLearnPages:
    @pytest.mark.parametrize("ui_lang", LEARN_UI_LANGUAGES)
    def test_english_on_the_page_matches_every_other_translation(self, ui_lang):
        """Translating the prose must never change a verb form."""
        pattern = r"<em>(.*?)</em>"
        forms = re.findall(pattern, learn_page(ui_lang))
        assert forms == re.findall(pattern, learn_page("en"))
        assert len(forms) > 60

    def test_every_word_shown_as_a_form_exists_in_the_pool(self):
        words = pool_words()
        shown = re.findall(r"<em>(.*?)</em>", learn_page("en"))
        unknown = {
            word
            for form in shown
            for word in re.findall(r"[a-z]+", form.lower())
            if word not in words
        }
        assert not unknown

    def test_worked_examples_are_forms_of_their_verb(self):
        examples = re.findall(r"<em>([a-z]+) → ([a-z]+)</em>", learn_page("en"))
        assert len(examples) > 10
        for verb, form in examples:
            cells = en_conjugations.get_verb_forms(verb).values()
            words = {w for forms in cells for f in forms if f for w in f.split()}
            assert form in words, (verb, form)

    def test_irregular_table_matches_the_pool(self):
        rows = re.findall(
            r"<strong>([a-z]+)</strong> → <em>([a-z]+)</em>, <em>([a-z]+)</em>",
            learn_page("en"),
        )
        assert len(rows) == 12
        for verb, past, participle in rows:
            forms = en_conjugations.get_verb_forms(verb)
            assert forms["past-simple"][0] == past, verb
            assert forms["present-perfect"][0] == f"have {participle}", verb

    @pytest.mark.parametrize(
        "ui_lang, heading",
        [
            ("en", "Learn English Verb Conjugations"),
            ("de", "Englische Verbkonjugation lernen"),
            ("es", "Aprende la conjugación de verbos en inglés"),
            ("it", "Impara la coniugazione dei verbi inglesi"),
            ("fr", "Apprendre la conjugaison des verbes anglais"),
            ("pt", "Aprenda a conjugação de verbos em inglês"),
            ("ar", "تعلّم تصريف الأفعال الإنجليزية"),
            ("uk", "Вивчаємо дієвідмінювання англійських дієслів"),
            # Welsh is a partial locale with no page of its own yet.
            ("cy", "Learn English Verb Conjugations"),
        ],
    )
    def test_learn_page_language(self, client, ui_lang, heading):
        client.get(f"/set_language/{ui_lang}")
        html = client.get("/en/learn/conjugations").get_data(as_text=True)
        assert f"<h1>{heading}</h1>" in html

    def test_sitemap_lists_the_learn_page(self, client):
        xml = client.get("/sitemap.xml").get_data(as_text=True)
        assert "/en/learn/conjugations" in xml

    @pytest.mark.parametrize("ui_lang", sorted(SUPPORTED_UI_LANGUAGES))
    def test_menu_offers_conjugation_in_every_ui_language(self, client, ui_lang):
        login(client)
        client.get(f"/set_language/{ui_lang}")
        html = client.get("/en").get_data(as_text=True)
        assert "/en/conjugate" in html
        assert "/en/learn/conjugations" in html
        assert "conjugate_title_en" not in html
