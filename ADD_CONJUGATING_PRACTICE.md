# Verb-Conjugation Practice in diminumero

This guide explains how the verb-conjugation practice section works and how to
maintain or extend it: regenerating the global verb pools, adjusting a language's
tense checklist, and how to add another conjugation language. The section
supports **Spanish and German** today.

Related guides:
- [ADD_NUMBERS.md](ADD_NUMBERS.md) — add a new language's number deck.
- [ADD_LISTENING_EXERCISES.md](ADD_LISTENING_EXERCISES.md) — add the Listening quiz.
- [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) — add the *numbers* Learn page (a
  sibling of the conjugation Learn page described below).

## Overview

The conjugation section (login required) lets a user build a personal pool of
verbs **per language** and drill conjugations across a curated set of tenses
and the six pronoun slots. The question space for a practice session is
**user's verbs × selected tenses × selected persons**, all scoped to one
language.

Conjugations are **not** computed at runtime. They come from a committed global
pool per language generated offline; the app only reads the committed JSON.

## Moving Parts

| File | Role |
|------|------|
| `conjugation_config.py` (project root) | `CONJ_LANGS` — one entry per conjugation language with `tenses` (usefulness-ranked checklist; each `key` matches the language's JSON), `persons` (six pronoun slots), `optional_person_index` (the user-toggleable slot: vosotros/4 for Spanish, `None` for German), and `hint_model_verbs`. Plus `CONJ_QUESTIONS_DEFAULT = 10` and the lang-aware helpers `conj_tenses()`, `conj_persons()`, `tense_label()`, `tense_hint()`, `person_label()`. |
| `languages/es/conjugations.json` | The committed Spanish pool (~840 popular verbs × the curated tenses). Each tense → a 6-element list aligned to `[yo, tú, él/ella/usted, nosotros, vosotros, ellos]`, with `null` where a person has no form. Kept in frequency order so autocomplete ranks common verbs first. |
| `languages/de/conjugations.json` | The committed German pool (~215 popular verbs). Slots: `[ich, du, er/sie/es, wir, ihr, sie/Sie]`. Composite tenses are stored as full multi-word strings ("habe gemacht", "werde aufstehen"); separable verbs split in finite forms ("stehe auf"). |
| `languages/conjugation_loader.py` | Shared `ConjugationPool` class (lazy JSON load, `verb_exists`, `get_verb_forms`, `search_verbs` with accent-folding). |
| `languages/<code>/conjugations.py` | Thin per-language module instantiating `ConjugationPool` and re-exporting its methods. `app.py` maps lang → module in `CONJ_POOLS`. |
| `tools/generate_conjugations.py` | PEP-723 generator for the Spanish JSON (drives the `verbecc` library). |
| `tools/generate_conjugations_de.py` | PEP-723 generator for the German JSON. verbecc has no German support, so this is a **self-contained rule engine**: weak verbs by rule, strong/mixed/modal verbs from an explicit `IRREGULAR`/`FULL_OVERRIDES` table, separable verbs from `SEPARABLE`, sein-auxiliary verbs from `SEIN_VERBS`. Ends with ~65 hard-coded self-checks that abort generation on any wrong form. |
| `models.py` | `VerbCard` (a user's verb + `lang` + rolling score) and `ConjugationStat` (per-`(lang, tense, person)` tally for the insights dashboard). |
| `static/js/conjugate.js` | Wires the `/<lang>/conjugate` manage page (autocomplete, settings, start). Reads the page language from the add-section's `data-lang` and sends it on every `/api/verbs*` call; reads the delete endpoint from `data-delete-base`. |

## Data Model

- **`VerbCard(user_sub, lang, infinitive, times_practiced, times_correct, recent_results, ...)`** —
  one verb a user added to their pool for one language (`lang`, default/server-default
  `"es"`). Holds only the infinitive; conjugations come from that language's global
  pool (validated at add time). Same `score`/`record_attempt` scoring as `Card`
  (rolling 10-attempt history).
- **`ConjugationStat(user_sub, lang, tense_key, person_index, times_practiced, times_correct, ...)`** —
  per-`(lang, tense, person)` practice tally, one row per
  `(user_sub, lang, tense_key, person_index)` (unique constraint `uq_conjstat_dim`).
  `VerbCard` already scores the *verb* dimension; this table adds the other two so
  the insights dashboard can rank which tenses and pronouns to practice, per
  language. Lifetime counters only; `score` = `times_correct/times_practiced` or
  `None`. Rows are recorded per attempt by `_record_conjugation_stat()`.

## Routes

The page/practice routes are namespaced under `/<lang_code>/` (e.g. `/es/conjugate`,
`/de/conjugate`) and `_require_conjugation_lang(lang_code)` 404s any language without
`has_conjugation` (`get_languages_with_conjugation()` in `languages/config.py`).
Templates link to them via `url_for(..., lang_code=...)`; globally-rendered templates
(nav, home, language cards) use the `conjugation_lang` context-processor variable,
which follows the session's learn language when it has a conjugation section and
falls back to `DEFAULT_CONJUGATION_LANG` (`"es"`). The `/api/verbs*` endpoints stay
un-namespaced but take a `lang` parameter (query string on the search, JSON body
elsewhere) that defaults to `"es"`; `/api/conjugate/validate` reads the language
from the active practice session.

- `/<lang_code>/conjugate` — manage page: add-verb form with autocomplete, a foldable insights
  dashboard (shown once any attempt exists), the user's verb list for that language, and
  practice settings (tense checklist, optional-person toggle where the language has one,
  difficulty, sampling, count) + Start. The dashboard is built by
  `_build_conjugate_dashboard_stats()` — three weakest-first panels (tenses, verbs,
  pronouns) scoped to the page's language.
- `/api/verbs/search?q=&lang=` — autocomplete from that language's pool, excluding owned verbs.
- `/api/verbs` (POST, JSON `{infinitive, lang}`) — add a verb; rejects verbs not in that
  language's pool with `{"unsupported": true}` (JS shows a popup). `/api/verbs/<id>`
  (DELETE) and `/<lang_code>/conjugate/<id>/delete` (POST fallback) remove a verb.
- `/<lang_code>/conjugate/practice/start` (POST) — builds a session from selected `tenses`,
  `include_vosotros` (ignored for languages without an optional person), `difficulty`
  (advanced/hardcore), `sampling_mode`, `count` (default 10). The session state stores
  its `lang`; requests for another language's practice/results leave it untouched.
- `/<lang_code>/conjugate/practice` (GET/POST) — prompt is verb + pronoun + tense; typed answer
  checked with `check_answer_advanced`; reveal/next with type-to-continue (reuses
  `cards_practice_reveal.js`); advanced mode highlights words live. Each attempt
  updates the owning `VerbCard` and the matching `ConjugationStat`.
- `/<lang_code>/conjugate/practice/results` — final score, clears state.
- `/api/conjugate/validate` (POST) — word-by-word feedback (disabled in hardcore).
- `/<lang_code>/learn/conjugations` — the **conjugation Learn page**. See
  [Conjugation Learn Page](#conjugation-learn-page) below.

## Conjugation Learn Page

Separate from the *numbers* Learn page (`/<lang_code>/learn`, see
[ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md)), the conjugation section has its own
reference page at `/<lang_code>/learn/conjugations`. The mode-selection page (`templates/index.html`)
surfaces both as side-by-side cards in the `learn-cta` block — **"Learn numbers"**
(`learn_nav_button`, gated on `has_learn_materials`) and **"Learn conjugations"**
(`learn_nav_conjugations_button`, gated on `has_conjugation_materials`).

Moving parts:

| Piece | Role |
|------|------|
| `has_conjugation_materials` flag in `languages/config.py` | Marks a language as having a conjugation Learn page. `get_languages_with_conjugation_materials()` derives the enabled list (combined with `ready: True`); the `learn_conjugations()` route, `mode_selection()`, and `sitemap_xml()` all read from it — no hardcoded language. |
| `learn_conjugations()` route in `app.py` | Serves `templates/learn_conjugations_<lang>_<ui_lang>.html`, falling back to `_en` (same UI-language pattern as the numbers `learn()` route). |
| `templates/learn_conjugations_es_<ui>.html` / `learn_conjugations_de_<ui>.html` | The pages themselves (`_en` required; Spanish also has `_es`/`_de`, German has `_de`; others fall back). Reuse the `learn-*` CSS classes and the `_learn_conjugations_jsonld.html` include. The footer CTA links to `/<lang>/conjugate` (`conjugate_start_btn`). |
| Translation keys | `learn_nav_conjugations_button` / `learn_nav_conjugations_desc` (the index card) and the per-language `seo_title_learn_conj_<lang>` / `meta_desc_learn_conj_<lang>` (page + JSON-LD), in `translations.py`. |

To add a new UI-language variant, copy `learn_conjugations_<lang>_en.html` to
`learn_conjugations_<lang>_<ui>.html` and translate the prose (keep the verb forms unchanged).

## Regenerating the Global Verb Pools

The pools are generated offline and committed; the app only reads them.

```bash
uv run tools/generate_conjugations.py      # Spanish (verbecc-based)
uv run tools/generate_conjugations_de.py   # German (self-contained rule engine)
```

Spanish notes:
- **`verbecc` is a generation-only dependency.** It is declared inline in the
  script's PEP-723 header, **never** in `pyproject.toml` — the running app reads the
  committed JSON and does not import verbecc.
- The script monkeypatches a `verbecc` voseo bug and rebuilds a few
  verbecc-defective regular verbs (`pasar`, `resultar`, `suceder`) from a regular
  proxy. Verbs `verbecc` can't conjugate correctly are auto-dropped.

German notes:
- No third-party dependency. Weak verbs are conjugated by rule (including the
  linking `-e-` for `-t/-d` stems, du-contraction after `-s/-ß/-x/-z`, and the
  `-eln/-ern` contractions); strong/mixed verbs carry their stems in `IRREGULAR`;
  sein/haben/werden, the modals and wissen live in `FULL_OVERRIDES`.
- Adding a verb = append it to `POPULAR_VERBS` (frequency position matters for
  autocomplete ranking) and, if it isn't weak, add its `IRREGULAR` entry; if it's
  separable, add a `SEPARABLE` entry (its base must be conjugatable); if it takes
  *sein* in the Perfekt, add it to `SEIN_VERBS` (checked on the full verb, so
  `aufstehen` is listed even though `stehen` takes *haben*).
- The script ends with ~65 self-checks (`EXPECTED`); extend them when you touch
  the engine rules.

Both pools are kept in frequency order so autocomplete ranks common verbs first.
After regenerating, run `uv run pytest tests/test_conjugate.py tests/test_conjugate_de.py`
and spot-check a few verbs in the app.

## Adjusting a Tense Checklist

Edit the language's `tenses` list in `CONJ_LANGS` (`conjugation_config.py`). Each entry needs:
- `key` — must match a tense key present in that language's `conjugations.json`
  (e.g. `"indicativo/presente"`, `"indikativ/praesens"`). If you add a tense whose
  key isn't generated into the JSON, the generator must be updated to emit it first.
- `label_native` / `label_en` — display labels (native is shown when the UI language
  equals the conjugated language).
- `hint_native` / `hint_en` — the one-line pattern blurb for the practice Hint.
- `default_on` — whether the checkbox starts ticked on the settings page.

The pronoun slots live in the language's `persons` list; `optional_person_index`
names the one user-toggleable slot (Spanish vosotros, index 4) or is `None`
(German — the template then hides the toggle entirely).

## Extending to Another Language

With the per-language refactor in place, adding conjugation language number three
means:
1. A generator + committed `languages/<code>/conjugations.json` (verbecc covers
   ca/es/fr/it/pt/ro; otherwise write a rule engine like the German one).
2. A thin `languages/<code>/conjugations.py` (copy the German one) and an entry in
   `CONJ_POOLS` in `app.py`.
3. A `CONJ_LANGS["<code>"]` entry in `conjugation_config.py` (tenses, persons,
   optional person, hint model verbs).
4. `has_conjugation: True` (and optionally `has_conjugation_materials: True` +
   `learn_conjugations_<code>_en.html`) on the language in `languages/config.py`.
5. Per-language translation keys: `conjugate_title_<code>`,
   `conjugate_add_placeholder_<code>`, `conjugate_flash_unsupported_<code>` (and
   `seo_title_learn_conj_<code>` / `meta_desc_learn_conj_<code>` for the Learn page).
6. Tests mirroring `tests/test_conjugate_de.py` (pool spot-checks, lang scoping).

No model or route changes are needed — `VerbCard`/`ConjugationStat` already carry
`lang` and the routes are namespaced.

## Index-card ↔ conjugation sync

Index cards and the conjugation pools are linked purely **by value** (no DB link,
no migration) — the sync is **additive only**, so deleting one side never touches
the other. A card matches a verb when its front *or* back is an exact pool
infinitive in *any* conjugation language (`_card_verb_match` in `app.py` returns
`(lang, infinitive)`, trying the front first, then the back, languages in registry
order); the matching side becomes the stored infinitive.

- **Cards → conjugation:** importable cards (verb side in a pool, not yet owned in
  that pool) are surfaced on `/cards` (per-card badge + "add to conjugation" button,
  plus a batch "add all" button covering every language) and during cards practice
  (`cards_practice.html`'s inline button, wired by
  `static/js/cards_practice_verb_add.js`). All paths POST to the existing
  `POST /api/verbs` with the detected `lang` (carried in `data-verb-lang`
  attributes); the batch button uses `POST /api/verbs/import-from-cards`, which the
  `/<lang>/conjugate` page calls with a `lang` filter so it only imports its own
  language's verbs.
- **Conjugation → cards:** verbs missing from the deck (`_verbs_missing_from_cards`)
  are offered on `/<lang>/conjugate` via a walk-through modal that prompts for a
  translation per verb and creates each card with the existing `POST /api/cards`.

Detection helpers live in `app.py` (`_card_verb_match`, `_importable_card_verbs`,
`_verbs_missing_from_cards`, `_importable_verb_for_card`); the JS lives in
`static/js/cards.js` and `static/js/conjugate.js`.

## Tests

`tests/test_conjugate.py` covers the generic mechanics against Spanish: verb add /
validate-against-pool / reject-unknown, autocomplete, the practice flow + scoring,
the vosotros toggle, the validate API, and the insights dashboard +
`ConjugationStat` recording. `tests/test_conjugate_de.py` covers the German pool
(form spot-checks incl. separable verbs and modals) and everything
multi-language: `lang` scoping of the API endpoints, pool isolation, the missing
vosotros toggle, and per-language sessions/dashboards.
`tests/test_card_verb_sync.py` covers the index-card ↔ conjugation sync
(detection incl. language, import-from-cards, page/practice exposure,
additive-only deletes). Run:

```bash
uv run pytest tests/test_conjugate.py tests/test_conjugate_de.py tests/test_card_verb_sync.py
```

## Questions?

Check `conjugation_config.py`, `languages/conjugation_loader.py`, and the two
generators in `tools/` for reference, or contact the maintainer.
