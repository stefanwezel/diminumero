# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
uv sync

# Run development server (http://127.0.0.1:5000)
uv run flask --app app run --debug

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_quiz_logic.py

# Run a specific test
uv run pytest tests/test_quiz_logic.py::test_get_random_question_returns_valid_number

# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Create a new Alembic migration after model changes
uv run flask --app app db migrate -m "describe change"

# Apply pending migrations locally (prod runs this on container start)
uv run flask --app app db upgrade

# Generate pronunciation MP3s for the Listening quiz (needs API_KEY_11_LABS in .env)
uv run tools/generate_audio.py --lang es

# Regenerate the global Spanish verb-conjugation pool (uses the verbecc library;
# generation-only dependency, declared inline in the PEP-723 script header)
uv run tools/generate_conjugations.py

# Production deployment (uses .env.prod, not .env)
docker-compose -f docker-compose.prod.yml up --build
```

## Architecture

**diminumero** is a Flask-based web app for practicing number translations in multiple languages.

### Core Components

- **app.py**: Main Flask application with routes and session management. Wires up SQLAlchemy + Flask-Migrate, the Auth0 OIDC client (Authlib), and `ProxyFix` so `url_for(_external=True)` honors `X-Forwarded-Proto` from Coolify/Traefik (required for the Auth0 callback to match in prod). Imports `QUESTIONS_PER_QUIZ` and `DEFAULT_UI_LANGUAGE` from `config.py`, and `TEXTS` from `translations.py`.

- **config.py** (project root): Defines `QUESTIONS_PER_QUIZ = 10`, `DEFAULT_UI_LANGUAGE = "en"`, `SUPPORTED_UI_LANGUAGES`/`RTL_UI_LANGUAGES`, and the per-mode speed-bonus thresholds `SPEED_BONUS_TIME_EASY = 25`, `SPEED_BONUS_TIME_ADVANCED = 45`, `SPEED_BONUS_TIME_HARDCORE = 45` (seconds; the audio mode reuses the advanced threshold).

- **translations.py** (project root): Contains the `TEXTS` dict used by `get_text()` in `app.py` for the multilingual UI.

- **models.py**: SQLAlchemy models. Five entities:
  - `Card(user_sub, front, back, times_practiced, times_correct, recent_results, created_at, updated_at)` — user-owned vocabulary card, free-form text on both sides (no per-card language). `recent_results` is a 10-char `'1'`/`'0'` string; the `score` property is `recent_results.count('1') / len(recent_results)` or `None` if unpracticed. `record_attempt(correct)` appends and trims.
  - `VerbCard(user_sub, infinitive, times_practiced, times_correct, recent_results, created_at, updated_at)` — a Spanish verb a user added to their conjugation-practice pool. Holds only the infinitive (conjugations come from the committed global pool, validated at add time). Same `score`/`record_attempt` scoring as `Card`.
  - `ConjugationStat(user_sub, tense_key, person_index, times_practiced, times_correct, created_at, updated_at)` — per-(tense, person) practice tally, one row per `(user_sub, tense_key, person_index)` (unique constraint `uq_conjstat_dim`). `VerbCard` already scores the verb dimension; this table adds the other two so the `/conjugate` insights dashboard can rank which tenses and pronouns to practice. Lifetime counters only; `score` = `times_correct/times_practiced` or `None`.
  - `DeckShare(token, owner_sub, owner_name, cards_json, created_at)` — frozen snapshot of one user's deck used by the share-link import flow. The snapshot is set at share time so later owner edits don't affect imports.
  - `PollResponse(user_sub, color_scheme_pref, cards_aware, device, freeform, user_agent, created_at)` — single submission of the in-app feedback poll. `user_sub` is nullable (anonymous responses allowed).

- **migrations/**: Alembic migrations managed by Flask-Migrate. `flask db upgrade` is run on container start (see `Dockerfile`); add new revisions with `uv run flask --app app db migrate -m "..."`.

- **quiz_logic.py**: Quiz engine with weighted random selection, multiple choice generation using `secrets` module, and language-aware answer validation. Key functions:
  - `get_random_question(numbers_dict, exclude_numbers, magnitude_level)` — weighted selection with configurable magnitude level (1-5). `MAGNITUDE_DECAY_FACTORS` maps each level to a decay factor; weight per number = `(1/decay)^band` where band 0=<100 through band 4=100K+
  - `generate_multiple_choice()` — 4 options using `secrets` for randomization
  - `check_answer()` — exact string comparison (easy mode multiple choice)
  - `check_answer_advanced()` — normalized comparison via `normalize_text()` (advanced/hardcore text input; also reused by the cards practice endpoint)
  - `validate_partial_answer()` — word-by-word live feedback, returns `{'is_complete', 'is_correct', 'words': [{'text', 'status'}]}`

- **languages/**: Multi-language subsystem
  - `config.py`: Language registry (`AVAILABLE_LANGUAGES`) with metadata, validation strategies, and helper functions (`get_language_numbers()`, `get_validation_strategy()`, `get_component_decomposer()`, `get_languages_with_learn_materials()`, `get_languages_with_audio_mode()`, etc.). Per-language flags include `ready`, `has_learn_materials`, and `has_audio_mode`.
  - Each language directory (es/, de/, fr/, ne/, da/, it/, ja/, ko/, zh/, pt/, tr/, sv/, no/, cy/, ga/) contains `numbers.py` (number→translation dict) and `generate_numbers.py`

- **conjugation_config.py** (project root): Config for the Spanish verb-conjugation section — `CONJ_TENSES` (the usefulness-ranked tense checklist; each `key` matches `languages/es/conjugations.json`), `CONJ_PERSONS` (the six pronoun slots; `vosotros` is `optional` and user-toggleable), `CONJ_QUESTIONS_DEFAULT = 10`, and the `tense_label()`/`person_label()` helpers.

- **languages/es/conjugations.json** + **languages/es/conjugations.py**: The committed global Spanish verb pool (~840 popular verbs × the curated tenses; each tense → a 6-element list aligned to [yo, tú, él/ella/usted, nosotros, vosotros, ellos], `null` where a person has no form). The JSON is kept in frequency order so autocomplete ranks common verbs first. `conjugations.py` is the lazy loader exposing `verb_exists()`, `get_verb_forms()`, `search_verbs(prefix, limit, exclude)`, and (via PEP 562 `__getattr__`) `GLOBAL_VERBS`.

- **tools/generate_conjugations.py**: PEP-723 script (`uv run tools/generate_conjugations.py`) that conjugates a frequency-ranked list of popular verbs with the `verbecc` library and writes `languages/es/conjugations.json`. `verbecc` is a **generation-only** dependency (declared inline, never in `pyproject.toml` — the app reads the committed JSON). The script monkeypatches a verbecc voseo bug and rebuilds a few verbecc-defective regular verbs (`pasar`, `resultar`, `suceder`) from a regular proxy; verbs verbecc can't conjugate correctly are auto-dropped.

- **tools/generate_audio.py**: PEP-723 script (`uv run tools/generate_audio.py --lang <code>`) that synthesizes one MP3 per number with ElevenLabs' `eleven_turbo_v2_5` cloud model into `static/audio/<lang>/<n>.mp3`. Each number is voiced by a speaker drawn at random from the language's `VOICE_POOLS` entry so a deck mixes voices. Needs `API_KEY_11_LABS` in `.env`. Languages currently shipping audio (1000 MP3s each): es, de, fr, ja, pt, sv.

### Quiz Modes

1. **Easy**: Multiple choice with 4 options; answer checked with `check_answer()` (exact match)
2. **Advanced**: Text input with live word-by-word validation via `/api/validate`; final check uses `check_answer_advanced()` (normalized)
3. **Hardcore**: Same as Advanced with stricter scoring
4. **Listening** (`mode == "audio"`): Plays a pre-generated MP3 of a number and the user types the digits. Only offered for languages with `has_audio_mode: True` and pre-generated audio; the playable pool is the intersection of the number deck with `_available_audio_numbers()` (the MP3s actually present under `static/audio/<lang>/`). The answer is normalized to digits (`re.sub(r"\D", "", ...)`) and compared to the number.

### Data Flow

User selects language → mode selection (+ magnitude dial) → `start_quiz()` initializes session (including `magnitude_level`) → quiz route serves questions from `get_random_question(magnitude_level=...)` → answers validated → after 10 questions → results page

### URL Route Structure

Quiz:
- `/` — Language selection page
- `/<lang_code>` — Mode selection page
- `/<lang_code>/start` — POST to initialize quiz session
- `/<lang_code>/quiz/easy` — Easy mode quiz (GET/POST)
- `/<lang_code>/quiz/advanced` — Advanced mode quiz (GET/POST)
- `/<lang_code>/quiz/hardcore` — Hardcore mode quiz (GET/POST)
- `/<lang_code>/listen/start` — POST to initialize a Listening session (audio-enabled languages only)
- `/<lang_code>/listen` — Listening mode quiz (GET/POST): plays the number's MP3, accepts a typed digit answer, supports reveal/next
- `/<lang_code>/results` — Results page
- `/<lang_code>/learn` — Numbers Learn page (languages with `has_learn_materials`)
- `/<lang_code>/learn/conjugations` — Verb-conjugation Learn page (languages with `has_conjugation_materials`; Spanish only today). Explains the `-ar/-er/-ir` patterns, tenses, stem-changers, and irregular verbs. The mode-selection page shows the numbers and conjugation Learn pages as two side-by-side cards.
- `/api/validate` — POST, JSON: live word-by-word validation for advanced/hardcore modes

Auth (Auth0 OIDC):
- `/login` — Redirect to Auth0 Universal Login
- `/callback` — OIDC callback; stores `userinfo` on the session under `user`
- `/logout` — Clear local session, then bounce through `https://<AUTH0_DOMAIN>/v2/logout`

Cards (login required; ownership enforced by `Card.user_sub == session["user"]["sub"]`):
- `/cards` — List + create form + foldable performance dashboard (GET); `?edit=<id>` opens an edit row. Dashboard stats (totals, accuracy, buckets, weak/strong tops) are built server-side by `_build_cards_dashboard_stats()` and also embedded as JSON for Chart.js.
- `/cards` (POST), `/cards/<id>/edit`, `/cards/<id>/delete` — Form-based CRUD (used as fallbacks)
- `/api/cards` (POST), `/api/cards/<id>` (PATCH/DELETE) — JSON CRUD used by `static/js/cards.js` for in-place updates
- `/api/cards/share` — POST: mint a `DeckShare` token containing a JSON snapshot of the current deck; returns the shareable URL
- `/cards/import/<token>` — GET shows the import preview (owner, count, dedup warning); POST applies the import. Dedup uses `normalize_text()` on the (front, back) pair so existing cards aren't duplicated.
- `/cards/practice/start` — POST: starts a session with `direction` (`front_to_back`/`back_to_front`/`random`), `sampling_mode` (`prioritized`/`random`), `difficulty` (`advanced`/`hardcore`), `count`, and optional `weak_only=1` (auto-sizes the session to the weak pool). Defaults: back→front, prioritized, hardcore.
- `/cards/practice` — GET shows the next prompt; POST submits an answer or `reveal`. Each attempt updates the card's `times_practiced`, `times_correct`, and `recent_results` via `record_attempt()`.
- `/cards/practice/results` — Final score; clears practice state
- `/api/cards/validate` — POST, JSON: word-by-word validation for the active practice card (forces word-based strategy regardless of card language)

Verb conjugation (login required; Spanish only today; the page/practice routes are namespaced under `/<lang_code>/` and 404 for languages without `has_conjugation` via `_require_conjugation_lang()`; ownership enforced by `VerbCard.user_sub`). The shared lang is exposed to templates as `conjugation_lang` (= `CONJUGATION_LANG`, `"es"`) by the context processor; the `/api/verbs*` and `/api/conjugate/validate` JSON endpoints stay un-namespaced (the verb pool is per-user, not per-language, today):
- `/<lang_code>/conjugate` — manage page: add-verb form with autocomplete, a foldable insights dashboard (shown once any attempt exists), the user's verb list, and practice settings (tense checklist, vosotros toggle, difficulty, sampling, count) + Start. Wired by `static/js/conjugate.js`. The dashboard is built by `_build_conjugate_dashboard_stats()` — three weakest-first panels (tenses, verbs, pronouns) each rendered with the shared `progress_ring` macro; verb scores come from `VerbCard`, tense/pronoun scores are aggregated from `ConjugationStat` rows recorded per attempt by `_record_conjugation_stat()`.
- `/api/verbs/search?q=` — GET: autocomplete from the global pool, excluding owned verbs.
- `/api/verbs` (POST) — add a verb; rejects verbs not in the global pool with `{"unsupported": true}` (JS shows a popup). `/api/verbs/<id>` (DELETE) and `/<lang_code>/conjugate/<id>/delete` (POST fallback) remove a verb.
- `/api/verbs/import-from-cards` (POST) — bulk-add every index-card verb (a card whose front/back is a pool infinitive) the user doesn't own yet. Part of the additive, value-based index-card ↔ conjugation sync (see ADD_CONJUGATING_PRACTICE.md): cards→verbs is offered on `/cards` (per-card + batch) and during cards practice; verbs→cards is a translation walk-through on `/<lang_code>/conjugate` that reuses `POST /api/cards`. Detection helpers `_card_verb_infinitive` / `_importable_card_verbs` / `_verbs_missing_from_cards` live in `app.py`; no DB link is stored, so deleting one side never affects the other.
- `/<lang_code>/conjugate/practice/start` — POST: builds a session from selected `tenses`, `include_vosotros`, `difficulty` (advanced/hardcore), `sampling_mode`, `count` (default 10). Question space = user's verbs × selected tenses × selected persons.
- `/<lang_code>/conjugate/practice` — GET/POST: prompt is verb + pronoun + tense; typed answer checked with `check_answer_advanced`; reveal/next with type-to-continue (reuses `cards_practice_reveal.js`); advanced mode highlights words live. Per attempt updates the owning `VerbCard`.
- `/<lang_code>/conjugate/practice/results` — final score, clears state. `/api/conjugate/validate` — POST: word-by-word feedback (disabled in hardcore).

Feedback poll:
- `/api/poll` — POST, JSON: stores a `PollResponse` row (anonymous allowed). The modal is rendered by `templates/_poll_modal.html` and wired by `static/js/poll.js`.

Misc:
- `/set_language/<lang>` — Switch UI language
- `/restart` — POST, restart quiz
- `/privacy`, `/about`, `/imprint` — Static info pages
- `/robots.txt`, `/sitemap.xml` — SEO; `/cards*`, `/login`, `/callback`, `/logout` are disallowed and `no-store` cached

### Session State

Two separate language keys coexist in the session:
- `language` — UI display language (e.g. `"en"`, `"de"`)
- `learn_language` — Language being practiced (e.g. `"es"`, `"de"`, `"fr"`, `"ne"`, `"da"`, `"it"`, …)

Quiz state keys: `score`, `total_questions`, `asked_numbers`, `mode` (`"easy"`/`"advanced"`/`"hardcore"`/`"audio"`), `magnitude_level`, `current_number`, `correct_answer`, `current_options` (easy mode only), `current_revealed` (listening mode reveal flag), `quiz_start_time` (for the speed bonus), and `show_perfect_splash`/`show_speed_splash` (one-shot results overlays).

Auth/cards state keys:
- `user` — Auth0 `userinfo` dict (presence == logged in; preserved across `start_quiz()` and `/restart` so quizzing doesn't log the user out)
- `card_practice` — Practice session: `{direction, sampling_mode, difficulty, count, weak_only, asked_ids, score, total, current_card_id, current_prompt_side, current_revealed}`

### Key Design Decisions

- **Weighted randomization**: Controlled by a user-facing magnitude dial (levels 1-5) on the mode selection page. Level 1 (default, decay=10) strongly favors small numbers; level 5 (decay=1) is uniform. The setting persists in the session so it carries across quizzes. Formula: `weight = (1/decay)^band` where bands are 0 (<100) through 4 (100K+).
- **Validation strategies**: Each language in `AVAILABLE_LANGUAGES` must declare `validation_strategy`: `"word_based"` (space-separated, e.g. Spanish/French) or `"component_based"` (compound words, e.g. German). Component-based languages also need a `decompose_<language>_number()` function in their `__init__.py`.
- **German normalization**: Umlauts converted (ü→ue, ö→oe, ä→ae, ß→ss) in `normalize_text()`, allowing ASCII input for German compound numbers.
- **Session-based state**: Quiz progress, scores, and preferences stored in Flask session.
- **Auth ownership**: All card routes use the `@login_required` decorator and `_user_card_or_404()` helper — never query `Card` without filtering by `user_sub == session["user"]["sub"]`. Auth0 client registration is skipped when `AUTH0_DOMAIN` is unset, so the dev server still boots without credentials but `/login` will fail.
- **Database**: SQLite at `instance/diminumero.db` by default (gitignored); set `DATABASE_URL` (e.g. `postgresql+psycopg://...`) to switch. The prod compose file bind-mounts `./data:/app/instance` for SQLite persistence and adds `host.docker.internal:host-gateway` so the container can reach a host-exposed Postgres (Coolify pattern).
- **Learn pages**: Driven by the `has_learn_materials: True` flag in each entry of `AVAILABLE_LANGUAGES` (`languages/config.py`). Both `mode_selection()` and `learn()` look up the language via `get_languages_with_learn_materials()` — no per-language hardcoding in `app.py`. Templates are named `learn_<lang>_<ui_lang>.html` and the `learn()` route falls back to `learn_<lang>_en.html` if the UI-language variant doesn't exist. The verb-conjugation Learn page is a parallel system: the `has_conjugation_materials` flag + `get_languages_with_conjugation_materials()` drive the `learn_conjugations()` route (`/<lang_code>/learn/conjugations`) and `learn_conjugations_<lang>_<ui_lang>.html` templates (same `_en` fallback). See ADD_CONJUGATING_PRACTICE.md.
- **Card scoring**: Each `Card` keeps a 10-char `recent_results` history (most recent attempt last). `score` is the share of `'1'`s; `None` until first attempt. Cards with `0 ≤ score < 0.5` are "weak" and surface in the dashboard's weak-cards CTA. `_pick_weighted_card()` in `app.py` biases the prioritized sampling mode toward weak, unpracticed, and rarely practiced cards (weight = `(1 - score) + 1/(1 + times_practiced) + 0.1`); `_load_next_card()` enforces the no-repeat-within-session rule via `asked_ids`.
- **Deck sharing**: `DeckShare.cards_json` is a frozen JSON snapshot taken at share time. Import dedup compares each incoming `(front, back)` pair to the recipient's existing cards after `normalize_text()` on both sides — duplicates are silently skipped and reported in a flash message.
- **Themes**: Two stylesheets — `static/css/style.css` (default dark-purple Floatworks-inspired) and `static/css/style-classic.css`. The choice is read from `localStorage.theme` in `templates/base.html` before first paint to avoid a flash, and toggled via a header button.
- **Listening mode / audio**: Driven by the `has_audio_mode` flag in `AVAILABLE_LANGUAGES`; both `mode_selection()` and the index language cards consult `get_languages_with_audio_mode()` and surface a "New · Listening" sticker. Audio is static MP3s under `static/audio/<lang>/<n>.mp3` (gitignored from regeneration but committed), generated by `tools/generate_audio.py`. The route never trusts the deck blindly — it intersects with `_available_audio_numbers()` so a half-generated deck still works. `quiz_listen.js` handles autoplay (with a small lag) and the reveal flow.
- **Speed bonus & splash overlays**: After a quiz, `_results_redirect()` compares elapsed time (`quiz_start_time`) against the per-mode `SPEED_BONUS_TIME_*` thresholds. A perfect run (100%) sets `show_perfect_splash`; a fast run (under the threshold and >80%) sets `show_speed_splash`. The `results` page renders these as one-shot overlays.
- **Cookie consent / AdSense**: `templates/base.html` renders a cookie banner wired by `static/js/cookie-banner.js`, which stores consent under `localStorage.diminumero_cookie_consent`. The banner and the `/privacy` page disclose Google AdSense usage.
- **Static asset cache-busting**: an `@app.url_defaults` hook (`add_static_cache_bust` in `app.py`) appends `?v=<file-mtime>` to every `url_for('static', …)` URL, so an edited CSS/JS file is fetched immediately (no template changes needed). `set_cache_headers` then serves *versioned* `/static/` hits with `Cache-Control: public, max-age=31536000, immutable` and unversioned direct hits with the short `max-age=600`. Net effect: edits show up on a normal reload, while unchanged assets cache for a year.

### Tests

Tests live in `tests/` with a shared `tests/conftest.py` that:
- forces `DATABASE_URL` to a temp SQLite file *before* `app.py` is imported (so dev `instance/` is never touched);
- sets dummy `AUTH0_*` env vars so `oauth.register("auth0", ...)` runs in CI (otherwise auth tests would hit `No such client: auth0`);
- creates/drops all tables around every test via an autouse fixture.

Test files: `test_app.py` (quiz routes/session), `test_quiz_logic.py` (engine in isolation), `test_auth.py` (Auth0 login/callback/logout, mocked), `test_cards.py` (card CRUD, practice flow, scoring, sharing/import dedup, dashboard stats), `test_conjugate.py` (verb add/validate-against-pool/reject-unknown, autocomplete, practice flow + scoring, vosotros toggle, validate API, insights dashboard + `ConjugationStat` recording), `test_poll.py` (feedback poll endpoint and storage). Each test file still defines its own `app`/`client` fixtures.

## Contributor Guides

Each kind of content has a dedicated top-level guide. Point to these (and keep them in sync) rather than duplicating their detail here:
- **ADD_NUMBERS.md** — add number practice for a new language (the most common recurring task; the starting point for any new language).
- **ADD_LISTENING_EXERCISES.md** — add the spoken-number Listening quiz to a language.
- **ADD_LEARNING_MATERIALS.md** — add Learn/tutorial pages for a language.
- **ADD_CONJUGATING_PRACTICE.md** — the Spanish verb-conjugation section (regenerating the pool, tense checklist, extending it).
- **ADD_UI_LANGUAGE.md** — add a new UI/interface translation.

## Adding Number Practice (a new language)

This is the most common recurring task in this repository. See ADD_NUMBERS.md for the complete guide. Key steps:
1. Create `languages/{code}/` directory with `numbers.py` and `generate_numbers.py`
2. Register in `languages/config.py` with `ready: False` initially; add import to `get_language_numbers()`
3. Update SEO strings in `translations.py` and JSON-LD in `templates/language_selection.html`
4. Set `ready: True` after testing

## Adding Learning Materials

See ADD_LEARNING_MATERIALS.md for the complete guide. Key steps:
1. Create `templates/learn_{code}_<ui_lang>.html` per UI language (the `learn()` route falls back to `_en.html`)
2. Set `has_learn_materials: True` on the language's entry in `languages/config.py` — no `app.py` edits needed (both `mode_selection()` and `learn()` consult `get_languages_with_learn_materials()`)

## Adding Listening Exercises

See ADD_LISTENING_EXERCISES.md for the complete guide. Key steps:
1. Add the language's `VOICE_POOLS` entry in `tools/generate_audio.py` (a list of ElevenLabs voice IDs, sampled at random per number).
2. Run `uv run tools/generate_audio.py --lang <code>` with `API_KEY_11_LABS` set in `.env` to render `static/audio/<code>/<n>.mp3`.
3. Set `has_audio_mode: True` on the language's entry in `languages/config.py` — both the index language cards and `mode_selection()` consult `get_languages_with_audio_mode()`.

## Verb-Conjugation Practice

See ADD_CONJUGATING_PRACTICE.md for the complete guide. The Spanish conjugation section reads a committed global pool (`languages/es/conjugations.json`); regenerate it offline with `uv run tools/generate_conjugations.py` (`verbecc` is a generation-only dependency). Tenses/pronouns are configured in `conjugation_config.py`.
