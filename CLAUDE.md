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

# Batch-generate the printable worksheet corpus for OER portals
uv run tools/generate_worksheets.py --out build/worksheets

# Verify a BUILT IMAGE can draw every worksheet character (CJK/Devanagari fonts)
docker run --rm <image> python tools/check_worksheet_fonts.py

# Regenerate the rule-derived traditional Welsh numbers (no dependencies).
# Writes languages/cy/numbers_traditional_generated.py; aborts if the rule stops
# reproducing a speaker-confirmed form.
uv run languages/cy/generate_numbers_traditional.py

# Dump every number form no speaker has confirmed, as a markdown review table
uv run tools/export_unconfirmed_forms.py --source single
uv run tools/export_unconfirmed_forms.py --include-notes

# Regenerate the global Spanish verb-conjugation pool (uses the verbecc library;
# generation-only dependency, declared inline in the PEP-723 script header)
uv run tools/generate_conjugations.py

# Regenerate the global German verb-conjugation pool (self-contained rule
# engine — verbecc has no German support; no dependencies)
uv run tools/generate_conjugations_de.py

# Regenerate the global Italian verb-conjugation pool (verbecc-based, like
# the Spanish one; generation-only dependency)
uv run tools/generate_conjugations_it.py

# Production deployment (uses .env.prod, not .env)
docker-compose -f docker-compose.prod.yml up --build
```

## Architecture

**diminumero** is a Flask-based web app for practicing number translations in multiple languages.

### Core Components

- **app.py**: Main Flask application with routes and session management. Wires up SQLAlchemy + Flask-Migrate, the Auth0 OIDC client (Authlib), and `ProxyFix` so `url_for(_external=True)` honors `X-Forwarded-Proto` from Coolify/Traefik (required for the Auth0 callback to match in prod). Imports `QUESTIONS_PER_QUIZ` and `DEFAULT_UI_LANGUAGE` from `config.py`, and `TEXTS` from `translations.py`.

- **config.py** (project root): Defines `QUESTIONS_PER_QUIZ = 10`, `DEFAULT_UI_LANGUAGE = "en"`, `SUPPORTED_UI_LANGUAGES`/`RTL_UI_LANGUAGES`/`PARTIAL_UI_LANGUAGES` (locales still being translated — they are selectable and fall back to English per key, and every page says so; `cy` is one today), and the per-mode speed-bonus thresholds `SPEED_BONUS_TIME_EASY = 25`, `SPEED_BONUS_TIME_ADVANCED = 45`, `SPEED_BONUS_TIME_HARDCORE = 45` (seconds; the audio mode reuses the advanced threshold).

- **translations.py** (project root): Contains the `TEXTS` dict used by `get_text()` in `app.py` for the multilingual UI.

- **models.py**: SQLAlchemy models. Five entities:
  - `Card(user_sub, front, back, times_practiced, times_correct, recent_results, created_at, updated_at)` — user-owned vocabulary card, free-form text on both sides (no per-card language). `recent_results` is a 10-char `'1'`/`'0'` string; the `score` property is `recent_results.count('1') / len(recent_results)` or `None` if unpracticed. `record_attempt(correct)` appends and trims.
  - `VerbCard(user_sub, lang, infinitive, times_practiced, times_correct, recent_results, created_at, updated_at)` — a verb a user added to their conjugation-practice pool for one language (`lang`, server-default `"es"`). Holds only the infinitive (conjugations come from that language's committed global pool, validated at add time). Same `score`/`record_attempt` scoring as `Card`.
  - `ConjugationStat(user_sub, lang, tense_key, person_index, times_practiced, times_correct, created_at, updated_at)` — per-(lang, tense, person) practice tally, one row per `(user_sub, lang, tense_key, person_index)` (unique constraint `uq_conjstat_dim`). `VerbCard` already scores the verb dimension; this table adds the other two so the `/conjugate` insights dashboard can rank which tenses and pronouns to practice, per language. Lifetime counters only; `score` = `times_correct/times_practiced` or `None`.
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
  - `config.py`: Language registry (`AVAILABLE_LANGUAGES`) with metadata, validation strategies, and helper functions (`get_language_numbers()`, `get_validation_strategy()`, `get_component_decomposer()`, `get_languages_with_learn_materials()`, `get_languages_with_audio_mode()`, etc.). Per-language flags include `ready`, `has_learn_materials`, `has_audio_mode`, and the optional `number_systems` list (see "Numeral systems" below).
  - Each language directory (es/, de/, fr/, ne/, da/, it/, ja/, ko/, zh/, pt/, tr/, sv/, no/, cy/, ga/) contains `numbers.py` (number→translation dict) and `generate_numbers.py`. A language with a second numeral system has a second deck module beside it (`cy/numbers_traditional.py`), and a language with notes has `notes.toml`.
  - **Every deck starts at 0** (`cero`, `Null`, 零, 영, `dim`, `náid`, शून्य …), taken from each generator's own `n == 0` branch. The generators build their set with `range(0, 101)`, so a regeneration keeps it. Listening mode is the deliberate exception: there is no `0.mp3`, and `_available_audio_numbers()` intersects the deck with the MP3s actually on disk, so zero drops out with no special-casing.
  - `provenance.py`: per-form provenance for decks assembled from public review — see "Form provenance" below.
  - `notes_loader.py`: per-number notes (the lightbulb) — TOML parsing, scope matching, locale overrides, `get_notes()` for requests and `validate_notes()` for CI. See "Per-number notes" below and ADD_NOTES.md.

- **Numeral systems** (`number_systems` in `languages/config.py`): a language may declare more than one way of saying its numbers. Welsh is the first — `decimal` (what schools teach, the deck that has always been there) and `traditional` (vigesimal; obligatory for the time, dates and age, per the r/learnwelsh review). Design notes:
  - `get_language_numbers(lang_code, system=None)` takes an **optional** system; omitted means the language's default, so all pre-existing call sites are untouched. A language that declares nothing reports one implicit system (`DEFAULT_NUMBER_SYSTEM = "default"`) and behaves exactly as before — the 14 other languages have no idea the feature exists.
  - **The completeness gate is derived from data, not a flag** (same principle as `_available_audio_numbers()`): a system declaring `requires_complete: (1, 100)` is offered only when every number in that range has a word. `None` entries in a deck mean "not verified yet" and are dropped at load. Welsh traditional gates on `(1, 21)` — the block speakers have given us in full — so the toggle **is** live, drilling 1-21 plus the round numbers; rule-derived forms cannot open a gate because they are not served. Raising the gate as more forms are confirmed is a one-line change. This is what lets the control (phase 2) and the data (phase 4) land in either order.
  - `resolve_number_system()` never raises: an unknown system, another language's system, or an incomplete one all fall back to the default — the same discipline as `_parse_magnitude()`.
  - Carried through a drill as `session["number_system"]`, preserved across `_seed_quiz_session()` like the login is. `_session_numbers()` resolves it on every question.
  - **`system` is deliberately NOT in `PRESET_PARAM_KEYS`**: `/cy/numbers?system=traditional` must render the config screen (and stay indexable), not drop into a drill. `_parse_preset_system()` still reads it so a shared link can carry a system, degrading with `preset_notice_system` when it can't be honoured.
  - The worksheet PDF cache key includes the system — two systems are different documents, and serving one from the other's cache entry would print the wrong sheet.
  - The toggle is rendered **only** when a language has two *ready* systems, as plain links so it works with no JS; single-system languages get no markup at all, not a disabled control. It appears twice: full-size on the number-practice config screen (`templates/numbers.html`) and as pills on the Number-practice tile of the language menu (`templates/index.html`), both pointing at `?system=<key>` on their own page — so the choice is made where a learner first sees the language, not one screen later. The menu tile is a `<div>` with a stretched CTA link, because an `<a>` may not contain the option links; a language whose second system isn't ready keeps the plain anchor tile and the `menu-tile-badge` naming the only system there is. Labels come from `number_system_name_<label_key>` / `number_system_desc_<label_key>`, where a system may override `label_key` to scope its strings by language — Welsh does, so its buttons read `Degol` / `Ugeiniol` (untranslated in all 8 UI languages: a learner meeting the traditional system needs the Welsh word for it) without claiming the generic `decimal` key for a future Korean system. A deck that is sparse inside its range gets `number_system_sparse_note` with the count, because "covers 1-100" would overstate a 30-number deck.
  - A correct answer in the language's *other* system is flagged as such (`number_system_wrong_system_flash`) rather than marked plainly wrong — it is correct Welsh, just not the Welsh this drill asked for.
  - Same shape would fit Korean (Sino vs native), Japanese (Sino vs wago) and Belgian/Swiss French. Full plan: `docs/plans/welsh-traditional-numbers.md`.

- **Form provenance** (`languages/provenance.py`, `config.SERVE_RECONSTRUCTED`): the Welsh traditional deck is being assembled from a public review thread, so every form records *who says so* — `confirmed` (two or more speakers), `single` (one, uncorroborated), or `reconstructed` (derived from a grammatical rule by a script or an LLM; **nobody has checked it**).
  - **Reconstructed forms are never served** while `SERVE_RECONSTRUCTED` is False (the default). A number whose only forms are reconstructed is *absent from the deck*: the drill skips it, does not fall back to the other system, and does not render a blank. They are committed for exactly two reasons — so they can be exported for review, and so they can be switched on in one line once confirmed.
  - The deck module derives a plain `NUMBERS` dict via `build_numbers()`, so the loader and every caller still see `dict[int, str]`. Gender is carried in the data (`m`/`f`) and the bare-digit drill takes masculine; the feminine series exists for the Learn page and any future noun-attached mode. The split propagates into compounds — 84 is `pedwar`/`pedair a phedwar ugain`, with only the *unit* gendered and the score untouched.
  - **Two files on purpose**: `languages/cy/numbers_traditional.py` is hand-edited and no script ever writes it; `numbers_traditional_generated.py` is machine-owned and entirely reconstructed. A speaker's form always wins; the generated file is rebuilt around it.
  - `languages/cy/generate_numbers_traditional.py` encodes the rules (41-99 = `[unit] + connective + [score]`, 21-39 = `[unit] ar hugain`). `TENS_CONNECTIVE` is the one unresolved value and it decides 54 forms; the connective and the mutation it triggers are one choice (aspirate after `a`, soft after `ar`). The generator **aborts** if the rule stops reproducing a confirmed form, and **reports** rather than resolves disagreements with a speaker (Welsh 45 is a live one). Its checks are re-asserted in `tests/test_cy_traditional.py` so a refactor that never reruns the script still fails.
  - `tools/export_unconfirmed_forms.py` dumps unconfirmed forms (and optionally unreviewed notes) as a markdown table. Withholding is only half a policy; the other half is making the forms cheap to check. `--source single` is the staged ask — those forms are already being drilled.

- **Per-number notes** (`languages/<code>/notes.toml`, loaded by `languages/notes_loader.py`): short factual asides attached to a number, a list, a range, or a whole system/language via one `applies_to` string (`"20"`, `"11-19"`, `"11-19,30"`, `"all"`), optionally filtered by `systems`. TOML because it is stdlib (`tomllib`, no dependency), comment-friendly and safe for non-programmers to edit; the text is plain (a validation rule rejects `<`) so contributors cannot inject markup.
  - **The answer-leak rule is the reason this has a schema.** A note beside the prompt "10" saying "`deg` becomes `deng`" gives the answer away. `get_notes(..., when="prompt")` returns only notes that declare `reveals_answer = false` **and** are `reviewed = true`; every other surface (reveal modal, results page, worksheet answer key) gets all of them. `reveals_answer` defaults to `true` — the safe direction — and `validate_notes()` mechanically rejects a `false` on a note that spells out a scoped deck word. The `reviewed` requirement is the human half: the mechanical check cannot catch "literally two nines" next to `deunaw`.
  - Authored in one language (`authored_in`), translated optionally via sibling `notes.<ui_lang>.toml` files holding just `id` + text/glosses. An untranslated note is **shown** with a marker, never hidden — the same fallback philosophy as `get_text()` and the `learn_<lang>_en.html` fallback.
  - Runtime is forgiving (a broken file costs the notes, not the drill); strictness lives in `tests/test_notes.py`, because CI runs pytest and nothing else.
  - Ships with seed content for `cy`, `de`, `es`, `fr`, `da` — all `reviewed = false` until a native speaker confirms them.
  - The lightbulb is a real `<button>` with `aria-expanded`/`aria-controls`, tap-first, Esc to close (`static/js/number_notes.js`, `templates/_number_notes.html`); hover is never the only way in. On the worksheet answer key it renders open (`notes_static`) since paper has nothing to click.
  - `tools/check_worksheet_fonts.py` now derives its character set from note text too — notes print, and free-form prose is exactly where an unrenderable character sneaks in.

- **conjugation_config.py** (project root): Per-language config for the verb-conjugation section — `CONJ_LANGS` keyed by language (`es`, `it`, `de`), each with `tenses` (the usefulness-ranked checklist; each `key` matches that language's `conjugations.json`), `persons` (the six pronoun slots), `optional_person_index` (the user-toggleable slot: 4/vosotros for Spanish, `None` for Italian and German), and `hint_model_verbs`. Plus `CONJ_QUESTIONS_DEFAULT = 10` and the lang-aware helpers `conj_tenses()`/`conj_persons()`/`tense_label()`/`tense_hint()`/`person_label()`.

- **languages/{es,it,de}/conjugations.json**: The committed global verb pools (Spanish ~840 verbs, slots [yo, tú, él/ella/usted, nosotros, vosotros, ellos]; Italian ~250 verbs, slots [io, tu, lui/lei, noi, voi, loro]; German ~215 verbs, slots [ich, du, er/sie/es, wir, ihr, sie/Sie]). Each tense → a 6-element list, `null` where a person has no form; composite tenses are full multi-word strings ("habe gemacht", "sono andato") and German separable verbs split in finite forms ("stehe auf"). Both JSONs are kept in frequency order so autocomplete ranks common verbs first. `languages/conjugation_loader.py` holds the shared `ConjugationPool` class (lazy load, `verb_exists()`, `get_verb_forms()`, `search_verbs(prefix, limit, exclude)` with accent folding); `languages/<code>/conjugations.py` are thin per-language modules instantiating it, mapped in `app.py`'s `CONJ_POOLS`.

- **tools/generate_conjugations.py**: PEP-723 script (`uv run tools/generate_conjugations.py`) that conjugates a frequency-ranked list of popular verbs with the `verbecc` library and writes `languages/es/conjugations.json`. `verbecc` is a **generation-only** dependency (declared inline, never in `pyproject.toml` — the app reads the committed JSON). The script monkeypatches a verbecc voseo bug and rebuilds a few verbecc-defective regular verbs (`pasar`, `resultar`, `suceder`) from a regular proxy; verbs verbecc can't conjugate correctly are auto-dropped.

- **tools/generate_conjugations_de.py**: PEP-723 script (`uv run tools/generate_conjugations_de.py`, no dependencies) that writes `languages/de/conjugations.json` from a self-contained German conjugation engine — weak verbs by rule, strong/mixed verbs from the `IRREGULAR` table, sein/haben/werden/modals/wissen from `FULL_OVERRIDES`, separable verbs from `SEPARABLE`, sein-auxiliary verbs from `SEIN_VERBS`. Ends with ~65 hard-coded form self-checks that abort on any regression.

- **tools/generate_conjugations_it.py**: PEP-723 script (`uv run tools/generate_conjugations_it.py`) that writes `languages/it/conjugations.json` via `verbecc` (generation-only dependency, like the Spanish generator). Italian-specific extraction: strips the congiuntivo's "che " lead-in, maps the imperative's "-" placeholder to null, keeps the first of slash-joined alternatives (faccio/fo), prefers the masculine gender variant, and force-rebuilds the composite tenses of `ESSERE_VERBS` (verbecc wrongly gives avere to piacere/riuscire). ~29 form self-checks.

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
- `/<lang_code>/numbers` — Number-practice config screen (easy/advanced/hardcore + magnitude dial + share-link builder, plus the numeral-system toggle for a language that has two ready systems). Also accepts shareable preset params — see "Shareable drill presets" below — and `?system=<key>`, which selects a numeral system **without** starting a drill (it is deliberately not a preset param).
- `/<lang_code>/start` — POST to initialize quiz session (form: `mode`, `magnitude_level`, optional `range`)
- `/<lang_code>/quiz/easy` — Easy mode quiz (GET/POST)
- `/<lang_code>/quiz/advanced` — Advanced mode quiz (GET/POST)
- `/<lang_code>/quiz/hardcore` — Hardcore mode quiz (GET/POST)
- `/<lang_code>/listen/start` — POST to initialize a Listening session (audio-enabled languages only)
- `/<lang_code>/listen` — Listening mode quiz (GET/POST): plays the number's MP3, accepts a typed digit answer, supports reveal/next
- `/<lang_code>/results` — Results page
- `/<lang_code>/learn` — Numbers Learn page (languages with `has_learn_materials`)
- `/<lang_code>/learn/conjugations` — Verb-conjugation Learn page (languages with `has_conjugation_materials`; Spanish, Italian and German today). Explains the regular patterns, tenses, and irregular verbs (Spanish: `-ar/-er/-ir`, stem-changers; Italian: `-are/-ere/-ire`, -isc- verbs, avere/essere; German: weak/strong verbs, separable prefixes). The mode-selection page shows the numbers and conjugation Learn pages as two side-by-side cards.
- `/<lang_code>/worksheet` — Printable worksheet generator. Bare URL = the setup form; with any of `count`/`direction`/`format`/`range` (or `min`+`max`)/`seed` it renders the sheet itself, as HTML or (with `format=pdf`) as a server-rendered PDF download — see "Printable worksheets" below. Anonymous GET, no login, no session state.
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

Verb conjugation (login required; Spanish, Italian and German today; the page/practice routes are namespaced under `/<lang_code>/` and 404 for languages without `has_conjugation` via `_require_conjugation_lang()`; ownership enforced by `VerbCard.user_sub`, pool scoping by `VerbCard.lang`). The context processor exposes `conjugation_lang` for globally-rendered links — the session's learn language when it has a conjugation section, else `DEFAULT_CONJUGATION_LANG` (`"es"`). The `/api/verbs*` JSON endpoints stay un-namespaced but take a `lang` parameter (query/body, default `"es"`); `/api/conjugate/validate` reads the language from the active practice session:
- `/<lang_code>/conjugate` — manage page: add-verb form with autocomplete, a foldable insights dashboard (shown once any attempt exists), the user's verb list for that language, and practice settings (tense checklist, optional-person toggle where the language has one, difficulty, sampling, count) + Start. Wired by `static/js/conjugate.js` (which reads the page language from the add-section's `data-lang`). The dashboard is built by `_build_conjugate_dashboard_stats()` — three weakest-first panels (tenses, verbs, pronouns) each rendered with the shared `progress_ring` macro; verb scores come from `VerbCard`, tense/pronoun scores are aggregated from `ConjugationStat` rows (filtered by lang) recorded per attempt by `_record_conjugation_stat()`.
- `/api/verbs/search?q=&lang=` — GET: autocomplete from that language's pool, excluding owned verbs.
- `/api/verbs` (POST, JSON `{infinitive, lang}`) — add a verb; rejects verbs not in that language's pool with `{"unsupported": true}` (JS shows a popup). `/api/verbs/<id>` (DELETE) and `/<lang_code>/conjugate/<id>/delete` (POST fallback) remove a verb.
- `/api/verbs/import-from-cards` (POST) — bulk-add every index-card verb (a card whose front/back is a pool infinitive in any conjugation language) the user doesn't own yet; an optional `lang` in the body restricts it to one pool (the `/<lang>/conjugate` page passes its own). Part of the additive, value-based index-card ↔ conjugation sync (see ADD_CONJUGATING_PRACTICE.md): cards→verbs is offered on `/cards` (per-card + batch) and during cards practice, with the detected language carried in `data-verb-lang` attributes; verbs→cards is a translation walk-through on `/<lang_code>/conjugate` that reuses `POST /api/cards`. Detection helpers `_card_verb_match` / `_importable_card_verbs` / `_verbs_missing_from_cards` / `_importable_verb_for_card` live in `app.py`; no DB link is stored, so deleting one side never affects the other.
- `/<lang_code>/conjugate/practice/start` — POST: builds a session from selected `tenses`, `include_vosotros` (ignored for languages without an optional person), `difficulty` (advanced/hardcore), `sampling_mode`, `count` (default 10). Question space = user's verbs × selected tenses × selected persons; the session state records its `lang`, and practice/results requests for another language leave it untouched.
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
- **No ads, no consent banner**: AdSense was removed (never approved) along with the cookie-consent banner. The site sets only the Flask session cookie, plus Auth0's own cookies for users who log in — both strictly necessary for a service the user requested, so § 25(2) TDDDG needs no consent and there is nothing to click away. `base.html` renders a standing `.site-note` footer line (`footer_cookie_note`) linking to `/privacy`, which carries the GDPR Art. 13 detail: the session cookie, the Auth0 login cookies, the GoatCounter analytics (cookieless, but it processes IP/user-agent), and what an account stores. **GoatCounter analytics is deliberately kept** — which is why neither the footer note nor the homepage subheading claims "no tracking"; that would contradict the privacy policy. The overlay geometry the banner used now lives in `.modal-overlay` (both stylesheets), carried in the markup by `_poll_modal.html` and `_conjugate_lang_modal.html`; `.poll-modal` keeps only its own deltas.
- **Shareable drill presets**: `GET /<lang_code>/numbers?mode=&range=&magnitude=` renders a fully configured drill in that same response — no session round-trip, no redirect through a config screen — so a link pasted into Moodle/Teams works for a student with no prior state. `mode` accepts `easy`/`advanced`/`hardcore`/`listening` (the public alias for the internal `audio`), `range` is `min-max` validated against the language's actual (sparse) deck, `magnitude` is 1-5. Anything invalid falls back to a default and adds an inline notice via `templates/_preset_notice.html` (never a 500, never a blank quiz); listening on a language without playable MP3s degrades to the advanced drill with a notice. `_start_preset_drill()` seeds the session with `_seed_quiz_session()` and delegates to the matching quiz view; the range persists as `session["number_range"]` and is re-applied to every later question by `_session_numbers()`. The builder on the config screen (`static/js/preset_link.js`) constructs the URL from the current selections and feeds the same range into the Start forms. SEO: `canonical_url` already drops the query string and `base.html` emits `noindex` whenever `has_quiz_params` is set, so parameterised URLs don't fragment the index (deliberately *not* blocked in robots.txt — a crawler must be able to read the noindex).
- **Printable worksheets**: `/<lang_code>/worksheet` generates a paper sheet with its answer key for a class with no devices. The sheet is a pure function of the URL — language, `range` (or the form's `min`/`max`), `count`, `direction` (`digits_to_words`/`words_to_digits`), `seed` — so re-opening the link reprints the identical sheet, which is why the seed is mandatory: a request without a usable one is redirected to the same URL with a freshly minted sheet ID. The draw is `random.Random(sha256(seed))` shuffling the sorted in-range deck and taking the first `count`, so `count` only decides how much of a fixed sequence is printed; `_worksheet_rng()` hashes the seed itself rather than trusting CPython's text seeding. **Words are only ever read out of `NUMBERS`** — nothing constructs a number word — so a sheet can only contain human-checked data. Bad params clamp/fall back with a screen-only notice (`.no-print`), never a 500. `templates/worksheet_sheet.html` is standalone and deliberately does *not* extend `base.html` (no nav, no analytics chrome, no theme); `static/css/worksheet.css` holds the whole document, prints black-on-white with `@page` margins that suit A4 and Letter, and puts the answer key on its own page via `break-before: page`. Column counts are decided server-side from the longest answer so long number words don't get squeezed. Every sheet *and* the answer key carry `templates/_worksheet_footer.html` — the reprint URL plus the CC BY-SA attribution — which is the feature's whole distribution mechanism and must not be dropped. The setup form is a plain GET form (no JS) and is listed in `sitemap.xml`; generated sheets carry `noindex`.
- **Worksheet PDFs (`?format=pdf`)**: rendered server-side by WeasyPrint from the *same* template and print CSS the browser prints, so the page and the PDF can't drift. `_worksheet_pdf_bytes()` imports WeasyPrint lazily (a machine without pango still boots and serves everything else) and hands it `static/css/worksheet.css` from disk rather than leaving the `<link>` in place — otherwise a worker would HTTP-fetch its own static file. `pdf_mode` drops the toolbar, analytics and favicon from the template. PDFs are byte-identical across runs (WeasyPrint embeds no timestamp), which is what lets the batch tool below be reproducible; a test pins this. If rendering raises, the route logs it and falls back to the HTML sheet with a notice — never a 500.
- **Worksheet PDF cache & render budget**: rendering one sheet costs ~0.8s (10 exercises) to ~6.5s (the 60 max) of CPU — the multi-column balancing in `worksheet.css` dominates, and every cheaper layout either breaks the page or changes the bytes, so the fix is to render *less often*, not faster. Prod runs three **sync** gunicorn workers and the route is anonymous, so without this a few concurrent renders serve nothing else on the site. Two mechanisms: (1) `_worksheet_pdf_cached()`/`_worksheet_pdf_store()` cache finished PDFs under `instance/worksheet_pdf/` (bind-mounted in prod, so all three workers share one cache across restarts; temp-file + `os.replace` so a reader never catches a partial write; trimmed to `WORKSHEET_PDF_CACHE_MAX_FILES`). The key hashes everything the bytes depend on **including the UI language** — the sheet's chrome is rendered in it, so en and de are different documents. (2) `_worksheet_pdf_budget_ok()` is a rolling per-process token bucket (`WORKSHEET_PDF_BUDGET`, default 10/min, env-overridable); past it the route serves the printable HTML sheet with the existing notice rather than queueing CPU. Both are `app.config` so callers can opt out, and **two must**: `tests/conftest.py` sets `WORKSHEET_PDF_CACHE_DIR = None` (a cache hit would let the render-failure test pass on an earlier test's bytes) and `tools/generate_worksheets.py` sets `WORKSHEET_PDF_BUDGET = 0` (it renders 120 sheets in a loop and treats an HTML response as a hard failure). A cache hit also makes a corpus re-run near-instant. Deterministic output means a served PDF gets `max-age=31536000, immutable` — keyed off the response mimetype in `set_cache_headers`, so an HTML fallback is never marked immutable.
- **Worksheet fonts (the production trap)**: `python:3.12-slim` ships **no fonts and no fontconfig**, and a PDF rendered without them still comes back as a valid 200 `application/pdf` with a correct text layer — only the glyphs are empty boxes. Nothing in the response reveals it. The Dockerfile therefore installs `libpango-1.0-0`/`libpangoft2-1.0-0`/`libharfbuzz-subset0` plus `fonts-dejavu-core` (Latin, incl. the Latin Extended-A that Turkish ğşı and the Nordic æøå need), `fonts-noto-cjk` (ja/ko/zh, ~91 MB — the bulk of the image growth) and `fonts-lohit-deva` (Nepali Devanagari), then runs `fc-cache -f`. `tools/check_worksheet_fonts.py` is the gate: it derives the required character set from the data (every word in every ready deck + every worksheet string in every UI language, so Arabic/Ukrainian chrome counts too) and fails naming any character fontconfig can't serve. Run it against a *built image*, not the dev checkout: `docker run --rm <image> python tools/check_worksheet_fonts.py`. Because fontconfig in the image has no per-language preferences, all four Noto CJK faces match a Han run equally and Japanese wins by family order — so the target-language text carries `lang=` and `worksheet.css` pins `[lang="zh"]`/`[lang="ja"]`/`[lang="ko"]` to the right regional face (the zh deck is Simplified). Note `worksheet-screen.css` is split out and linked only by the HTML page: WeasyPrint supports no media *features*, so a `(max-width: …)` query in the main sheet would log a warning on every PDF and drown out genuine font warnings.
- **Batch worksheet corpus**: `uv run tools/generate_worksheets.py` writes the standard set (every ready language × four ranges × both directions = 120 sheets; the beginner shape is the full 21 numbers of 0–20, so the block a learner should know completely is never printed with one of its numbers randomly missing) into `build/worksheets/<lang>/` plus a `manifest.csv` for OER portal uploads. Seeds are derived from each sheet's own settings (`sheet_seed()`), so re-running regenerates the identical corpus rather than minting new sheets; `--salt` deliberately mints a different one. It drives the real route through the Flask test client, so a batch PDF is byte-for-byte what `?format=pdf` serves, and it treats an HTML fallback response as a failure — writing a degraded sheet into a `.pdf` destined for a portal is exactly the outcome to catch.
- **Static asset cache-busting**: an `@app.url_defaults` hook (`add_static_cache_bust` in `app.py`) appends `?v=<file-mtime>` to every `url_for('static', …)` URL, so an edited CSS/JS file is fetched immediately (no template changes needed). `set_cache_headers` then serves *versioned* `/static/` hits with `Cache-Control: public, max-age=31536000, immutable` and unversioned direct hits with the short `max-age=600`. Net effect: edits show up on a normal reload, while unchanged assets cache for a year.

### Tests

Tests live in `tests/` with a shared `tests/conftest.py` that:
- forces `DATABASE_URL` to a temp SQLite file *before* `app.py` is imported (so dev `instance/` is never touched);
- sets dummy `AUTH0_*` env vars so `oauth.register("auth0", ...)` runs in CI (otherwise auth tests would hit `No such client: auth0`);
- creates/drops all tables around every test via an autouse fixture.

Test files: `test_app.py` (quiz routes/session), `test_quiz_logic.py` (engine in isolation), `test_auth.py` (Auth0 login/callback/logout, mocked), `test_cards.py` (card CRUD, practice flow, scoring, sharing/import dedup, dashboard stats), `test_conjugate.py` (verb add/validate-against-pool/reject-unknown, autocomplete, practice flow + scoring, vosotros toggle, validate API, insights dashboard + `ConjugationStat` recording — against Spanish), `test_conjugate_de.py` (the German pool's forms incl. separable verbs/modals, `lang` scoping of the verbs API, es/de pool isolation, per-language sessions and dashboards), `test_conjugate_it.py` (the Italian pool's forms incl. -isc- verbs and avere/essere auxiliaries, it-pool scoping), `test_card_verb_sync.py` (index-card ↔ conjugation sync incl. language detection), `test_poll.py` (feedback poll endpoint and storage), `test_presets.py` (shareable drill links: valid params, out-of-range/garbage fallbacks, listening degraded on no-audio languages, cold no-session access, canonical/noindex), `test_worksheet.py` (printable worksheets: seed determinism incl. a pinned draw, seed minting/redirect, answer key matching the sheet, words drawn only from the verified deck, both directions, range/count fallbacks, print-only output, the required footer, the `?format=pdf` path — byte-identical output, answer key on its own PDF page, warning-free rendering, degradation when the PDF stack breaks — and the batch generator's seed stability), `test_number_systems.py` (languages with two numeral systems: single-system languages unaffected, the completeness gate, `?system=` on the config screen and in shared links, session carry-over, the wrong-system nudge, partial ranges, sparse-deck multiple choice, worksheet cache-key separation, and an allow-list assertion that the Welsh traditional deck contains no invented forms), `test_notes.py` (per-number notes: every committed notes file validates, scope grammar, system scoping, translations and fallback, and the answer-leak rule from both ends — no note beside an unanswered prompt, and a mistaken `reveals_answer = false` fails the build), `test_cy_traditional.py` (form provenance: reconstructed forms never served and their numbers absent entirely, the flag flipping them on, gender propagation into compounds, the generator reproducing confirmed forms, the connective switch failing loudly against them, and disagreements reported not resolved), `test_translations.py` (locale key parity, orphan keys, placeholder counts, and that `PARTIAL_UI_LANGUAGES` agrees with actual coverage). Each test file still defines its own `app`/`client` fixtures.

The PDF tests need WeasyPrint's native libraries and poppler (`pdftotext`); CI installs both, and they skip cleanly on a machine without them. Font/glyph coverage is deliberately *not* asserted in pytest — CI has no CJK fonts — that check is `tools/check_worksheet_fonts.py` against a built image.

## Contributor Guides

Each kind of content has a dedicated top-level guide. Point to these (and keep them in sync) rather than duplicating their detail here:
- **ADD_NUMBERS.md** — add number practice for a new language (the most common recurring task; the starting point for any new language), including languages with more than one numeral system.
- **ADD_LISTENING_EXERCISES.md** — add the spoken-number Listening quiz to a language.
- **ADD_LEARNING_MATERIALS.md** — add Learn/tutorial pages for a language.
- **ADD_NOTES.md** — add a per-number note (the lightbulb): schema, the answer-leak rule, translations.
- **ADD_CONJUGATING_PRACTICE.md** — the verb-conjugation section (Spanish, Italian + German; regenerating the pools, tense checklists, adding a language).
- **ADD_UI_LANGUAGE.md** — add a new UI/interface translation, including partial locales (`PARTIAL_UI_LANGUAGES`).

Plans and open questions live under `docs/`:
- **docs/plans/welsh-traditional-numbers.md** — the design behind numeral systems and notes, phase by phase, with the rejected alternatives.
- **docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md** — what we still don't know about traditional Welsh, written to be handed to speakers. The toggle is live (gated on the complete 1–21 block); what the open questions still hold back is the *deck*, chiefly the 41–99 connective, which decides 54 forms at once and keeps them unserved until someone confirms it.

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

See ADD_CONJUGATING_PRACTICE.md for the complete guide. The conjugation section (Spanish, Italian and German) reads committed global pools (`languages/<code>/conjugations.json`); regenerate offline with `uv run tools/generate_conjugations.py` (Spanish) / `uv run tools/generate_conjugations_it.py` (Italian) — both verbecc-based, `verbecc` is a generation-only dependency — or `uv run tools/generate_conjugations_de.py` (German; self-contained rule engine). Tenses/pronouns are configured per language in `conjugation_config.py` (`CONJ_LANGS`).
