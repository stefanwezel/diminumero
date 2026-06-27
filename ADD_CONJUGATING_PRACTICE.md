# Verb-Conjugation Practice in diminumero

This guide explains how the Spanish verb-conjugation practice section works and how
to maintain or extend it: regenerating the global verb pool, adjusting the tense
checklist, and what it would take to support a second language.

Related guides:
- [ADD_NUMBERS.md](ADD_NUMBERS.md) — add a new language's number deck.
- [ADD_LISTENING_EXERCISES.md](ADD_LISTENING_EXERCISES.md) — add the Listening quiz.
- [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) — add the *numbers* Learn page (a
  sibling of the conjugation Learn page described below).

## Overview

The conjugation section (login required, Spanish only today) lets a user build a
personal pool of Spanish verbs and drill conjugations across a curated set of
tenses and the six pronoun slots. The question space for a practice session is
**user's verbs × selected tenses × selected persons**.

Conjugations are **not** computed at runtime. They come from a committed global
pool generated offline with the `verbecc` library; the app only reads the committed
JSON.

## Moving Parts

| File | Role |
|------|------|
| `conjugation_config.py` (project root) | `CONJ_TENSES` (usefulness-ranked tense checklist; each `key` matches the JSON), `CONJ_PERSONS` (six pronoun slots; `vosotros` is `optional`/user-toggleable, `VOSOTROS_INDEX = 4`), `CONJ_QUESTIONS_DEFAULT = 10`, and the `tense_label()`/`person_label()` helpers. |
| `languages/es/conjugations.json` | The committed global pool (~840 popular verbs × the curated tenses). Each tense → a 6-element list aligned to `[yo, tú, él/ella/usted, nosotros, vosotros, ellos]`, with `null` where a person has no form. Kept in frequency order so autocomplete ranks common verbs first. |
| `languages/es/conjugations.py` | Lazy loader over the JSON. Exposes `verb_exists()`, `get_verb_forms()`, `search_verbs(prefix, limit, exclude)`, and (via PEP 562 `__getattr__`) `GLOBAL_VERBS`. |
| `tools/generate_conjugations.py` | PEP-723 generator that (re)builds `conjugations.json`. |
| `models.py` | `VerbCard` (a user's verb + rolling score) and `ConjugationStat` (per-`(tense, person)` tally for the insights dashboard). |
| `static/js/conjugate.js` | Wires the `/<lang>/conjugate` manage page (autocomplete, settings, start). Reads the lang-aware delete endpoint from the add-section's `data-delete-base`. |

## Data Model

- **`VerbCard(user_sub, infinitive, times_practiced, times_correct, recent_results, ...)`** —
  one Spanish verb a user added to their pool. Holds only the infinitive;
  conjugations come from the global pool (validated at add time). Same
  `score`/`record_attempt` scoring as `Card` (rolling 10-attempt history).
- **`ConjugationStat(user_sub, tense_key, person_index, times_practiced, times_correct, ...)`** —
  per-`(tense, person)` practice tally, one row per `(user_sub, tense_key, person_index)`
  (unique constraint `uq_conjstat_dim`). `VerbCard` already scores the *verb*
  dimension; this table adds the other two so the insights dashboard can rank which
  tenses and pronouns to practice. Lifetime counters only; `score` =
  `times_correct/times_practiced` or `None`. Rows are recorded per attempt by
  `_record_conjugation_stat()`.

## Routes

The page/practice routes are namespaced under `/<lang_code>/` (e.g. `/es/conjugate`)
and `_require_conjugation_lang(lang_code)` 404s any language without `has_conjugation`
(`get_languages_with_conjugation()` in `languages/config.py`). Templates link to them
via `url_for(..., lang_code=...)`; globally-rendered templates (nav, home, language
cards) use the `conjugation_lang` context-processor variable (= `CONJUGATION_LANG`).
The `/api/verbs*` and `/api/conjugate/validate` JSON endpoints stay un-namespaced
because the verb pool is per-user, not per-language, today.

- `/<lang_code>/conjugate` — manage page: add-verb form with autocomplete, a foldable insights
  dashboard (shown once any attempt exists), the user's verb list, and practice
  settings (tense checklist, vosotros toggle, difficulty, sampling, count) + Start.
  The dashboard is built by `_build_conjugate_dashboard_stats()` — three
  weakest-first panels (tenses, verbs, pronouns), each rendered with the shared
  `progress_ring` macro.
- `/api/verbs/search?q=` — autocomplete from the global pool, excluding owned verbs.
- `/api/verbs` (POST) — add a verb; rejects verbs not in the global pool with
  `{"unsupported": true}` (JS shows a popup). `/api/verbs/<id>` (DELETE) and
  `/<lang_code>/conjugate/<id>/delete` (POST fallback) remove a verb.
- `/<lang_code>/conjugate/practice/start` (POST) — builds a session from selected `tenses`,
  `include_vosotros`, `difficulty` (advanced/hardcore), `sampling_mode`, `count`
  (default 10).
- `/<lang_code>/conjugate/practice` (GET/POST) — prompt is verb + pronoun + tense; typed answer
  checked with `check_answer_advanced`; reveal/next with type-to-continue (reuses
  `cards_practice_reveal.js`); advanced mode highlights words live. Each attempt
  updates the owning `VerbCard` and the matching `ConjugationStat`.
- `/<lang_code>/conjugate/practice/results` — final score, clears state.
- `/api/conjugate/validate` (POST) — word-by-word feedback (disabled in hardcore).
- `/<lang_code>/learn/conjugations` — the **conjugation Learn page** (a reference page that
  explains the regular `-ar/-er/-ir` patterns, the tenses you practice, stem-changers, and the
  irregular verbs). See [Conjugation Learn Page](#conjugation-learn-page) below.

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
| `has_conjugation_materials` flag in `languages/config.py` | Marks a language as having a conjugation Learn page. `get_languages_with_conjugation_materials()` derives the enabled list (combined with `ready: True`); the `learn_conjugations()` route, `mode_selection()`, and `sitemap_xml()` all read from it — no hardcoded `"es"`. |
| `learn_conjugations()` route in `app.py` | Serves `templates/learn_conjugations_<lang>_<ui_lang>.html`, falling back to `_en` (same UI-language pattern as the numbers `learn()` route). |
| `templates/learn_conjugations_es_<ui>.html` | The page itself (`_en` required; `_es`/`_de` provided, others fall back). Reuses the `learn-*` CSS classes and the `_learn_conjugations_jsonld.html` include. The footer CTA links to `/<lang>/conjugate` (`conjugate_start_btn`). |
| Translation keys | `learn_nav_conjugations_button` / `learn_nav_conjugations_desc` (the index card) and `seo_title_learn_conj` / `meta_desc_learn_conj` (page + JSON-LD), in `translations.py`. |

To add a new UI-language variant, copy `templates/learn_conjugations_es_en.html` to
`learn_conjugations_es_<ui>.html` and translate the prose (keep the Spanish verb forms unchanged).
Extending the page to a second language would also require the broader work in
[Extending to Another Language](#extending-to-another-language) plus a
`has_conjugation_materials: True` flag and a `learn_conjugations_<code>_en.html` template.

## Regenerating the Global Verb Pool

The pool is generated offline and committed; the app only reads it.

```bash
uv run tools/generate_conjugations.py
```

This conjugates a frequency-ranked list of popular verbs with the `verbecc` library
and writes `languages/es/conjugations.json`.

Notes:
- **`verbecc` is a generation-only dependency.** It is declared inline in the
  script's PEP-723 header, **never** in `pyproject.toml` — the running app reads the
  committed JSON and does not import `verbecc`.
- The script monkeypatches a `verbecc` voseo bug and rebuilds a few
  verbecc-defective regular verbs (`pasar`, `resultar`, `suceder`) from a regular
  proxy. Verbs `verbecc` can't conjugate correctly are auto-dropped.
- The JSON is kept in frequency order so autocomplete ranks common verbs first.
- After regenerating, run `uv run pytest tests/test_conjugate.py` and spot-check a
  few verbs in the app.

## Adjusting the Tense Checklist

Edit `CONJ_TENSES` in `conjugation_config.py`. Each entry needs:
- `key` — must match a tense key present in `conjugations.json` (e.g.
  `"indicativo/presente"`). If you add a tense whose key isn't generated into the
  JSON, the generator must be updated to emit it first.
- `label_es` / `label_en` — display labels.
- `default_on` — whether the checkbox starts ticked on the settings page.

The pronoun slots live in `CONJ_PERSONS`; `vosotros` (index 4) is the only
`optional` one, toggled by the user and controlled via `VOSOTROS_INDEX`.

## Extending to Another Language

The section is Spanish-only today and several pieces hardcode that assumption (the
`es` JSON path, `verbecc` Spanish conjugation, the `CONJ_PERSONS` Spanish pronoun
set, and the per-user `VerbCard` pool which carries no language). The page/practice
routes are already namespaced under `/<lang_code>/` and gated by `has_conjugation`,
so the URL space is ready; adding another language would require, at minimum:
1. A generator + committed `conjugations.json` for that language (a verbecc-style
   source or another conjugation engine).
2. A language-aware loader (parameterize `languages/<code>/conjugations.py`).
3. A language-specific person/tense config (the current `CONJ_PERSONS`/`CONJ_TENSES`
   are Spanish).
4. Giving `VerbCard` (and the `/api/verbs*` + `/api/conjugate/validate` endpoints) a
   language so each user's pool is scoped per language.

This is a larger change than adding numbers or audio; open an issue to scope it
before starting.

## Index-card ↔ conjugation sync

Index cards and the conjugation pool are linked purely **by value** (no DB link,
no migration) — the sync is **additive only**, so deleting one side never touches
the other. A card matches a verb when its front *or* back is an exact pool
infinitive (`_card_verb_infinitive` in `app.py`); the matching side becomes the
stored infinitive.

- **Cards → conjugation:** importable cards (verb side in the pool, not yet owned)
  are surfaced on `/cards` (per-card badge + "add to conjugation" button, plus a
  batch "add all" button) and during cards practice (`cards_practice.html`'s inline
  button, wired by `static/js/cards_practice_verb_add.js`). All paths POST to the
  existing `POST /api/verbs`; the batch button uses `POST /api/verbs/import-from-cards`.
- **Conjugation → cards:** verbs missing from the deck (`_verbs_missing_from_cards`)
  are offered on `/conjugate` via a walk-through modal that prompts for a translation
  per verb and creates each card with the existing `POST /api/cards`.

Detection helpers live in `app.py` (`_card_verb_infinitive`,
`_importable_card_verbs`, `_verbs_missing_from_cards`); the JS lives in
`static/js/cards.js` and `static/js/conjugate.js`.

## Tests

`tests/test_conjugate.py` covers verb add / validate-against-pool / reject-unknown,
autocomplete, the practice flow + scoring, the vosotros toggle, the validate API,
and the insights dashboard + `ConjugationStat` recording.
`tests/test_card_verb_sync.py` covers the index-card ↔ conjugation sync
(detection, import-from-cards, page/practice exposure, additive-only deletes). Run:

```bash
uv run pytest tests/test_conjugate.py tests/test_card_verb_sync.py
```

## Questions?

Check `conjugation_config.py`, `languages/es/conjugations.py`, and
`tools/generate_conjugations.py` for reference, or contact the maintainer.
