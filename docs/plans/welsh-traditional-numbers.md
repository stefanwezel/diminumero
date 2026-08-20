# Welsh traditional numbers — investigation and implementation plan

Status: **implemented.** Phases 0–5 are in the codebase; the plan below is kept as the
reasoning behind them, with the places the build departed from it recorded in
[Part 7](#part-7--implementation-notes) at the end.

Trigger: the r/learnwelsh review of `/cy`. The distilled verdict was *decimal-only is
not sufficient* — the traditional system is obligatory for time, dates and age, and it
arrives early in Dysgu Cymraeg courses (`ugain` at Mynediad, ordinals at Sylfaen).

Two of the three things this change needs are **not Welsh features**:

1. a language may have **more than one numeral system** (Korean and Japanese in this
   repo have exactly the same shape today and ship only one system each);
2. a number may carry **notes** — short factual asides, of which Welsh mutation is one
   instance and German `einundzwanzig` word order is another.

Only the traditional number data itself is Welsh-specific. The plan is built that way.

**Ground rule applied throughout: no Welsh form is invented here.** Forms not stated
verbatim in the review thread are recorded as gaps in
[`docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md`](../QUESTIONS-FOR-NATIVE-SPEAKERS.md), never
guessed into a data file.

---

## Part 1 — Findings

### 1. Number data model

**One flat lookup table per language, `dict[int, str]`.**

- `languages/cy/numbers.py:3` — `NUMBERS = {0: "dim", 1: "un", …}`. 1001 entries,
  keys `0 … 9990306`. Every language directory has the same file with the same shape
  (`languages/es/numbers.py`, `languages/de/numbers.py`, …).
- Coverage per language is *dense to 100, sparse above*: `languages/cy/generate_numbers.py:137-142`
  does `range(0, 101)` plus random samples of 200/300/200/100/100 from the higher bands.
  Measured for `cy`: 101 numbers ≤ 100, 90 two-digit, 200 three-digit.
- **Spelling is enumerated at runtime, generative offline.** Nothing composes a number
  word during a request. `number_to_welsh()` (`languages/cy/generate_numbers.py:26-130`)
  builds the strings once and rewrites `numbers.py` (`languages/cy/generate_numbers.py:148-153`).
  This is the reason a wrong rule can never surface mid-drill — and the reason the
  worksheet feature can promise that every printed word is human-checked data
  (`app.py:940-944`).
- Word-internal mutation is already baked into the stored strings and documented as
  such: `dau ddeg`, `tri chant`, `dwy fil` (`languages/cy/generate_numbers.py:6-10`).

There is **no room in the value for anything but the spelling** — no alternates, no
tags, no notes, no per-number metadata of any kind.

### 2. What adding a language actually requires

Registration is four edits, all documented in `ADD_NUMBERS.md`:

| Step | File | Reference |
|---|---|---|
| Deck | `languages/<code>/numbers.py` + `__init__.py` | `ADD_NUMBERS.md:75-121` |
| Registry entry | `languages/config.py` → `AVAILABLE_LANGUAGES` | `languages/config.py:4`; `cy` at `languages/config.py:409-438` |
| Loader branch | `get_language_numbers()` `elif` chain | `languages/config.py:508-560`; `cy` at `551-552` |
| SEO | `meta_desc_index`/`seo_title_index` in `translations.py`, `inLanguage` in `templates/language_selection.html` | `ADD_NUMBERS.md:154-166` |

The registry entry carries `ready`, `has_learn_materials`, `has_audio_mode`,
`has_conjugation*`, `validation_strategy`, `feedback_expression`, and `ui_names` /
`ui_descriptions` for all 8 UI languages.

**Does `ADD_NUMBERS.md` survive a language with two systems? No — not because it breaks,
but because it has no concept for it.** "3. Create Number Data" (`ADD_NUMBERS.md:75-93`)
speaks of *the* NUMBERS dict; the testing checklist (`ADD_NUMBERS.md:241-257`) has one
line for "Numbers dictionary is complete and accurate". The one-deck assumption is also
baked into five call sites of `get_language_numbers(lang_code)` (`app.py:393, 573, 595,
984, 1152`) and two tools (`tools/check_worksheet_fonts.py:46`, and
`tools/generate_worksheets.py` via the route). Any second system has to either fit
through that function or fork every consumer — which decides Phase 2's answer.

### 3. Precedent for registers / gender / ordinals / alternates

**For numerals: none. Plainly none.** No language in `AVAILABLE_LANGUAGES` declares a
register or system; no deck carries a gendered variant, an ordinal, or a second accepted
spelling. Even the data-integrity test assumes one canonical string per number
(`tests/test_quiz_logic.py:307-314` asserts >95 % of values are unique).

Four *structural* precedents elsewhere in the repo are directly extendable, and the
design below extends all four rather than inventing anything:

1. **Additive per-language capability flags** — `has_audio_mode`, `has_learn_materials`,
   read through `get_languages_with_*()` (`languages/config.py:472-506`), consumed by
   templates with `{% if has_audio_mode %}` (`templates/index.html:62`). Features appear
   for the languages that declare them and are structurally absent elsewhere.
2. **A set of accepted answers for one prompt** — already exists twice, both in typed
   drills: `_acceptable_answers()` (`app.py:2318-2335`, used at `app.py:2566-2569`) and
   `_conj_acceptable_answers()` (`app.py:3438-3457`, used at `app.py:3587, 3622, 3751`),
   with `_pick_best_validation()` (`app.py:2338-2355`) picking the best live-validation
   result across the set.
3. **Per-language config module + committed data file** — `conjugation_config.py:21`
   (`CONJ_LANGS`) alongside `languages/<code>/conjugations.json`, loaded lazily by the
   shared `languages/conjugation_loader.py`. This is the repo's existing answer to
   "structured content a contributor edits without touching app code".
4. **Readiness derived from data, not from a flag** — `_available_audio_numbers()`
   (`app.py:1552-1564`) intersects the deck with the MP3s actually on disk, so a
   half-generated audio deck degrades instead of 404-ing. The completeness gate in
   Phase 2 is a direct copy of this idea.

Also relevant, as the closest existing thing to a "lightbulb": the conjugation **Hint**
panel — `_build_conjugation_hint()` (`app.py:3253-3286`), markup at
`templates/conjugate_practice.html:73-96`, opened by a button, and explicitly reasoned
about for answer leakage in its own docstring ("no answer is leaked"). Using it costs
half a point (`app.py:3615-3641`). That is the precedent for both the disclosure UI and
the leak rule.

### 4. Exercise engine

- **Selection**: `get_random_question(numbers_dict, exclude_numbers, magnitude_level)`
  (`quiz_logic.py:30-70`) — weight `(1/decay) ** band`, bands 0 (<100) … 4 (100 K+)
  (`quiz_logic.py:13-27`).
- **Easy mode**: 4 options from the deck filtered to *the same digit length*
  (`quiz_logic.py:86-101`); the check is **exact string equality**
  (`check_answer()`, `quiz_logic.py:120-131`).
- **Advanced / hardcore**: `check_answer_advanced()` = `normalize_text()` equality
  (`quiz_logic.py:347-359`). `normalize_text` lowercases, collapses spaces, strips
  combining accents, and maps German umlauts/ß and Turkish dotless ı
  (`quiz_logic.py:134-174`). Welsh `ŵ`/`ŷ` therefore already fold to `w`/`y`.
- **Live feedback**: `validate_partial_answer()` (`quiz_logic.py:177-344`) via
  `POST /api/validate` (`app.py:1404`).
- **Can one prompt have several correct answers today? In the number quiz, no.** The
  session holds a single `correct_answer` string (`app.py:1252, 1379`) and every check
  compares against it. The mechanism for a *set* exists and is proven — but only in the
  cards and conjugation drills (finding 3.2).

### 5. Per-number metadata, and existing disclosure components

- **No per-number metadata exists.** Not a note, not a tag, not an example, not an audio
  path — audio is resolved by filename convention (`static/audio/<lang>/<n>.mp3`,
  `app.py:1552-1564`), never stored against the number.
- **Components to extend rather than invent:**
  - the conjugation **Hint** panel — button + hidden panel + `hidden` toggle
    (`templates/conjugate_practice.html:73-96`, `static/js/conjugate_practice.js`);
  - foldable `<details>` dashboards (`templates/conjugate.html:151`,
    `templates/cards.html:99-180` with `aria-expanded` handling at `cards.html:339-378`);
  - the reveal modal (`templates/quiz_advanced.html`, `.reveal-modal`), which is exactly
    the moment a note is safe to show;
  - inline notice strip `.preset-notice` (`templates/_preset_notice.html`);
  - shared `.modal-overlay` geometry in both stylesheets.
- **There is no tooltip/popover primitive.** What exists is bare `title="…"` attributes
  (`templates/quiz_advanced.html:27`, `templates/conjugate_practice.html:23`) — hover-only,
  invisible on touch, unreliable for screen readers. That is *not* a base to build the
  lightbulb on; the Hint panel is.

### 6. UI i18n

- `translations.py` — one dict per locale under `TRANSLATIONS`: `en` (line 4), `de` (458),
  `es` (908), `it` (1339), `fr` (1769), `pt` (2199), `ar` (2629), `uk` (3059).
- **8 locales × 420 keys, currently at 100 % parity** (measured: every locale has all 420
  English keys, no locale has extras).
- Key structure: flat `snake_case` strings, positional `{}` for runtime values
  (`flash_correct`, `flash_incorrect`), and the literal token
  `LANGUAGE_NAME_PLACEHOLDER` substituted with the learning-language name
  (`app.py:343-346`).
- **Fallback**: per key, to English (`app.py:339-342`) — a missing key never leaks a raw
  key name to the page. `lang_<code>_name` / `lang_<code>_description` are resolved out of
  `languages/config.py` instead of `translations.py` (`app.py:329-334`). Learn pages fall
  back at template level to `learn_<lang>_en.html` (`app.py:1804-1812`).
- **Coverage check: none.** No test asserts key parity between locales. Parity today is
  maintained by hand.
- Dynamic key composition is an established pattern — `get_text('magnitude_level_' ~ n)`
  (`templates/numbers.html:66`), `get_text('conjugate_title_' + lang_code)`
  (`templates/index.html:86`), `_conj_text()` (`app.py:350-357`). A per-system label key
  can use the same trick.
- **A `cy` UI locale needs**: `SUPPORTED_UI_LANGUAGES` in `config.py:15`; a 420-key dict in
  `translations.py`; a `language_cy` key in all 8 existing dicts; `"cy"` entries in
  `ui_names` **and** `ui_descriptions` for all 15 learning languages
  (`languages/config.py`); a tuple in `templates/base.html:144-153`; and an
  `OG_LOCALE_MAP` entry (`app.py:259-268`) — **that last step is missing from
  `ADD_UI_LANGUAGE.md`**, which would leave a new locale emitting `og:locale=en_US`.

### 7. Routing and controls

- `/cy` → `mode_selection()` (`app.py:380-415`) through the catch-all `/<lang_code>`;
  `/cy/numbers` → `number_modes()` (`app.py:581-615`); the quiz routes take **only**
  `lang_code` and read everything else from the session (`app.py:1169, 1276, 1424, 1583`).
- The learning language is chosen by **navigation**, not by a control. The header
  (`templates/base.html:98-167`) holds the auth menu, the theme toggle and the UI-language
  globe — all global. A numeral-system control there would render on all 15 languages and
  be dead on 14. **Reject the header.**
- The place drill parameters already live is `/cy/numbers`: the magnitude dial
  (`templates/numbers.html:59-67`), the range inputs and the share-link builder
  (`templates/numbers.html:91-148`, `static/js/preset_link.js`). A sibling control there
  is a one-tile addition with no layout invention.
- **Shareable URLs already work by query param**, deliberately: `PRESET_PARAM_KEYS`
  (`app.py:424`), `_parse_preset()` (`app.py:509-541`), `_start_preset_drill()`
  (`app.py:1693-1713`), with the chosen range persisted as `session["number_range"]` and
  re-applied to every later question by `_session_numbers()` (`app.py:566-578`).
- **Trap to avoid**: `_has_preset_params()` (`app.py:450-455`) makes *any* recognised
  param render the drill instead of the config screen (`app.py:601-602`) and sets
  `noindex` via `has_quiz_params` (`app.py:313`). So `system` must **not** join
  `PRESET_PARAM_KEYS`, or `/cy/numbers?system=traditional` would skip the config screen
  and drop the page out of the index.

### 8. Tests

- `tests/test_quiz_logic.py:279-323` — `TestNumbersDataIntegrity`, **Spanish only**: keys
  are ints, values are non-empty strings, 1–10 present, >95 % unique values, no leading /
  trailing / double spaces, lowercase.
- Nothing validates any other language's deck. No schema test, no range-coverage test, no
  cross-language uniqueness test, no i18n parity test.
- `tests/conftest.py` forces a temp SQLite DB and dummy Auth0 env before `app.py` imports;
  every test file defines its own `app`/`client` fixtures.
- **CI runs `uv run pytest` and nothing else** (`.github/workflows/test.yml:32`). Any new
  validation must therefore be a *test*, not a standalone script, or it will never run.

---

## Part 2 — Recommended approach

### 2.1 Modelling: a system *within* `cy`

**Recommendation: (b) — a numeral system declared inside the `cy` language entry, with a
second deck file beside `numbers.py`.**

```python
# languages/config.py, inside the "cy" entry
"number_systems": [
    {"key": "decimal",     "module": "numbers",             "default": True},
    {"key": "traditional", "module": "numbers_traditional",
     "requires_complete": (0, 100), "has_audio": False},
],
```

```
languages/cy/numbers.py              # unchanged — the decimal deck
languages/cy/numbers_traditional.py  # new — same dict shape, gaps marked
```

`get_language_numbers(lang_code, system=None)` gains **one optional parameter** that
defaults to the language's default system, so all five existing call sites
(`app.py:393, 573, 595, 984, 1152`) and both tools keep working with no edit. A language
that declares no `number_systems` reports exactly one implicit system and behaves as today.

*Why:* it is the only option that keeps one Welsh in the language grid, one set of SEO
metadata, one `/cy` URL space and one learner mental model, while touching the engine in
exactly one function.

**Rejected:**

- **(a) a separate language entry (`cy-trad`).** Zero engine change, but it duplicates
  `ui_names` × 8 and `ui_descriptions` × 8, puts two "Welsh" cards on the landing page,
  splits SEO and sitemap entries, splits the shareable-link namespace, and tells the user
  that traditional Welsh is a different language — which is the one thing the thread was
  most emphatic it is not. It also doubles the metadata a future two-system language
  (Korean) would have to duplicate.
- **(c) per-number alternates (`NUMBERS[20] = ["dau ddeg", "ugain"]`).** Invasive: every
  consumer assumes `str` — `generate_multiple_choice()` (`quiz_logic.py:96`), the
  worksheet builder (`app.py:940-946`), `check_answer()` (`quiz_logic.py:131`), the font
  checker (`tools/check_worksheet_fonts.py:46`), the integrity test
  (`tests/test_quiz_logic.py:296-300`). Worse, it *loses the information that matters*: it
  cannot say which form is which system, cannot express "drill only traditional", and
  cannot express that traditional stops at ~120 while decimal runs to 10 million. It
  would also be a silent format change for the fork that already exists.

**Cost:** `languages/config.py` (one entry + ~4 helpers), `languages/cy/__init__.py`,
one new deck file, one new test file. `app.py` untouched in this phase.

### 2.2 The toggle

**Control and placement.** A two-option segmented control (radio group, no JS required
for correctness) on `/<lang>/numbers`, immediately above the magnitude dial — the section
that already owns drill parameters (`templates/numbers.html:59-67`). It writes a hidden
`system` input into the three Start forms exactly as the magnitude dial and the range
already do (`templates/numbers.html:24-25`, `static/js/preset_link.js:72-74`), and adds
`&system=` to the shareable link.

**Rendered only when the language declares more than one *available* system.** The
template condition is `{% if number_systems | length > 1 %}`, mirroring
`{% if has_audio_mode %}` (`templates/index.html:62`). A single-system language gets no
control, no disabled control and no empty fieldset — it does not exist in the DOM.

**Persistence.** `session["number_system"]`, resolved on every read through
`resolve_number_system(lang_code, requested)`, which falls back to the language's default
whenever the value is unknown, not declared for this language, or not gate-passing — same
never-raise discipline as `_parse_magnitude()` (`app.py:490-500`). It must also be
preserved by `_seed_quiz_session()` (`app.py:544-563`), which clears the session, in the
same way the UI language and login already are. Per-language by construction: a stale
`traditional` on Spanish resolves back to Spanish's only system.

**Completeness gate — the mechanism that lets code and data land in either order.** A
declared system is *offered* only when its deck passes a check derived from the data, not
from a hand-flipped flag (the `_available_audio_numbers()` pattern, `app.py:1552-1564`):

```python
def system_deck_ready(lang_code, system_key) -> bool:
    # module missing            -> False
    # any int in requires_complete range missing or None -> False
    # otherwise                 -> True
```

Gaps are written as `41: None` in the deck, so the traditional file can be committed with
its 30 verified forms and 70 holes, the gate stays shut, the toggle stays hidden, and the
first PR that fills the last hole turns the feature on with no code change. This is what
makes Phase 2 and Phase 4 order-independent.

**Default for `/cy`: decimal.** Argued, not assumed:

1. What this site drills is a bare digit → word conversion with no sentence around it.
   The thread put that context squarely in the decimal column ("arithmetic, counting
   aloud"; `beth yw un deg naw plys chwech?`).
2. The traditional forms are licensed *by context* — time, dates, age, small sums of
   money. A bare-number drill removes exactly the context that selects them, so drilling
   them by default would teach forms while hiding the rule for using them.
3. The decimal deck has had one reviewer say it looks accurate. The traditional deck will
   start life mostly `TODO`. Defaulting to the unreviewed one would put the weakest data
   in front of every visitor.
4. Course sequencing reported in the thread introduces decimal first, with traditional
   arriving incrementally from Mynediad onward.

The counter-argument is real and must be answered in copy, not by the default: a learner
who only ever meets decimal cannot tell the time. That is what Phase 0's label, the Learn
page section and (later) contextual drills are for.

**Not Welsh-specific.** The concept is "this language has N numeral systems". Languages
already in the repo that could adopt it, verified against their decks:

| Language | Second system | Deck today |
|---|---|---|
| **Korean `ko`** | native Korean `하나/둘/셋` (ages, hours, counting objects) vs Sino-Korean | ships Sino only: `일, 이, 삼, 십` — the strongest case in the repo |
| **Japanese `ja`** | native *wago* `ひとつ/ふたつ` vs Sino-Japanese | ships Sino only: `一, 二, 三, 十` |
| **French `fr`** | Belgian/Swiss `septante`, `huitante`, `nonante` | ships standard only: `soixante-dix`, `quatre-vingt-dix` |
| **Chinese `zh`** | financial/anti-fraud numerals `壹贰叁`, plus 两 vs 二 | ships `一, 二, 三` |
| **Irish `ga`** | counting vs personal numerals (`beirt`, `triúr`) | ships `a haon, a dó, a trí` |

**Which system is which is a per-system label key**, not a hardcoded "Decimal/Traditional"
pair — Korean's two systems are not "traditional" and Welsh's are not "native". Labels
resolve as `get_text("number_system_name_" + key)`, the same dynamic-key pattern as
`magnitude_level_<n>` (`templates/numbers.html:66`).

**New i18n keys — this is a translation ask in its own right.** Phase 2 adds these to
**all 8 locales**:

| Key | English | Purpose |
|---|---|---|
| `number_system_label` | "Number system" | control legend |
| `number_system_name_decimal` | "Decimal" | option label |
| `number_system_name_traditional` | "Traditional" | option label |
| `number_system_desc_decimal` | "Used for arithmetic, counting and larger amounts." | one-line helper |
| `number_system_desc_traditional` | "Used for telling the time, dates and age." | one-line helper |
| `number_system_only_note` | "This drill teaches the {} number system." | Phase 0 copy, reused after the toggle lands |
| `number_system_unavailable_note` | "The {} system isn't ready for practice yet." | Phase 0 + gate-closed state |
| `number_system_partial_range_note` | "The {} system is only available for {}–{}." | partial-range warning |
| `number_system_wrong_system_flash` | "That's the {} form — this drill is asking for the {} form." | §2.5 nudge |
| `preset_notice_system` | "That link asked for a number system this language doesn't have, so we started the usual one." | joins the existing `preset_notice_*` family (`app.py:520-538`) |
| `preset_share_system_label` | "Number system" | share-link builder |

= **11 keys × 8 locales = 88 strings.** Five of them (`number_system_label`,
`number_system_name_*`, `number_system_only_note`, `number_system_unavailable_note`) ship
in **Phase 0** and are reused verbatim by the toggle, so the honest-labelling copy is not
thrown away when the control arrives.

**Cost:** `languages/config.py` (helpers), `app.py` (~8 touch points, all additive),
`templates/numbers.html`, `templates/index.html` (label only), `static/js/preset_link.js`,
both stylesheets, `translations.py`, one test file.

### 2.3 Per-number notes ("lightbulb")

**File format: TOML, one file per language, sibling to the deck.**
`languages/cy/notes.toml`, parsed with the standard library's `tomllib` (Python ≥ 3.12 is
already required, `pyproject.toml:5`) — **no new dependency**. Chosen over JSON (the
`conjugations.json` precedent) because notes are prose written by non-programmers: TOML
allows comments, multi-line strings and unescaped apostrophes, and a trailing comma
cannot destroy the file. Chosen over YAML because that would add a dependency for one
feature.

**Schema — four attachment scopes, one field, no query language:**

```toml
# languages/cy/notes.toml
language = "cy"
authored_in = "en"          # the language the note text below is written in

[[note]]
id = "cy-deg-before-m"      # stable, unique within the file; the key translations use
applies_to = "10"           # "10" | "11-19" | "11,12,15" | "11-19,30" | "all"
systems = ["decimal", "traditional"]   # omit = every system of this language
reveals_answer = true       # default true; see the leak rule below
text = "Before a word starting with m-, deg becomes deng."
source = "r/learnwelsh thread, 2026-08"   # optional
reviewed = false            # optional; false renders an 'unreviewed' marker

  [[note.examples]]
  phrase = "deng munud"
  gloss = "ten minutes"

  [[note.examples]]
  phrase = "deng mil"
  gloss = "ten thousand"
```

- **Attachment scope** is the single `applies_to` string with a four-token grammar:
  a number (`"20"`), a range (`"11-19"`), a comma list of either (`"11-19,30"`), or
  `"all"`. `all` + `systems = ["traditional"]` is a system-wide note; `all` with `systems`
  omitted is a language-wide note. That covers all four required scopes without inventing
  a selector language.
- **System scoping** is the optional `systems` array. `deg → deng` applies to both Welsh
  systems; `ugain → hugain after ar` is `systems = ["traditional"]` and is inert until
  that system exists — which is exactly why Phase 3 does not depend on Phase 2.
- **Multiple notes per number**: `[[note]]` is an array of tables; several notes may match
  the same number and all of them render, in file order. Welsh 20 already has two.
- **Structure over prose — agreed, with no free-form markup.** `text` is plain text
  rendered escaped; examples are `phrase`/`gloss` pairs rendered in a fixed layout. No
  HTML, no Markdown, no interpolation. A contributor cannot break the page, and every note
  looks the same everywhere it appears. (A validation rule rejects `<` in any string, so
  the intent is enforced rather than merely documented.)

**The answer-leak rule — a blocker, treated as one.**

> **A note is never rendered on a screen where the number it is attached to is the
> unanswered prompt, unless the note is explicitly flagged `reveals_answer = false`.**

Three surfaces, three behaviours:

| Surface | Behaviour |
|---|---|
| Reference (Learn page, a future browse view, the worksheet **answer key**) | all matching notes always visible |
| Live drill prompt (easy options, advanced/hardcore input, listening player, worksheet **exercise** side) | only notes with `reveals_answer = false`, behind the lightbulb — never auto-opened |
| After the question is settled (reveal modal, post-answer flash/feedback, results page) | all matching notes visible |

`reveals_answer` **defaults to `true`** (the safe value), and `false` is not taken on
trust — CI rejects it when the note text or any example phrase contains, after
`normalize_text()` (`quiz_logic.py:134`), the deck word of any number in the note's scope,
for any system in its scope. For an `applies_to = "all"` note, `false` requires that the
text contain *no* deck word of that language at all.

Applied to the seed notes from the thread:

| Note | Scope | Contains a scoped answer? | Verdict |
|---|---|---|---|
| `deg` → `deng` before m- (`deng mil`, `deng munud`) | 10, both systems | yes — "deg" | **post-answer only** |
| `pymtheg` → `bymtheg` after `ar` | 15, traditional | yes — "pymtheg" | post-answer only |
| `deunaw` is literally "two nines" | 18, traditional | yes — "deunaw" | post-answer only |
| `ugain namyn un` exists but is older/rural | 19, traditional | no (19 = `pedwar ar bymtheg`) — but it hands over 20's word and is a near-synonym of the prompt | post-answer only; **flagged for human judgement** |
| `ugain` → `hugain` after `ar` | 20, traditional | yes — "ugain" | post-answer only |
| counted noun mutates: `ugain mlynedd` | 20, traditional | yes — "ugain" | post-answer only |
| `deugain` = "two twenties" | 40, traditional | yes | post-answer only |
| `hanner cant` = "half a hundred"; `hanner can punt` | 50, traditional | yes | post-answer only |
| `pedwar ugain` = "four twenties" | 80, traditional | yes | post-answer only |
| `cant` → `can` before a noun | 100, traditional | yes | post-answer only |
| cardinal `dau ar bymtheg` ≠ ordinal `ail ar bymtheg` (17th) | 17, traditional | yes | post-answer only |
| traditional is used for time, dates and age | `all`, traditional | no number words | **may show at the prompt** (`reveals_answer = false`) |
| money: traditional up to ~30, decimal above | `all`, traditional | no number words | may show at the prompt |

So **every single-number seed note is post-answer only**, and only the two system-wide
usage notes qualify as prompt-side. That is the correct outcome, and it is worth saying
plainly: the motivating example (`deg` → `deng`) is itself a leak, which is why the rule
had to come before the UI.

Two honesty caveats: the mechanical check is a **floor, not a ceiling** — "two nines" for
`deunaw` leaks semantically with no literal match — so `reveals_answer = false` should
additionally require `reviewed = true`. And a note is never *auto-opened*: even
post-answer it sits behind the lightbulb, so it cannot pre-empt the reveal modal.

**Notes are i18n content — authored once, translated optionally.**

- The note file is authored in one language (`authored_in = "en"` in the header). **No
  translation is required to contribute a note.**
- Per-locale overrides live in sibling files, one per UI language:
  `languages/cy/notes.de.toml`, containing only `id` plus the translated `text` and
  example `gloss`es. A translator never touches the authoritative file and cannot break a
  drill.
- Resolution: requested UI language → `authored_in` → English. This mirrors both existing
  fallbacks in the repo — `get_text`'s per-key English fallback (`app.py:339-342`) and
  `learn()`'s `_en` template fallback (`app.py:1804-1812`).
- **A note in a language the reader doesn't read is shown, not hidden**, with a quiet
  marker above it: *"Not available in your language yet — shown in English."*
  (`notes_untranslated`). Hiding it would silently withhold correct information from
  everyone but English readers; a marker is honest and costs one key.

**Touch and accessibility.** The lightbulb is a `<button type="button">` — not an icon
with `title=`, not a hover target:

- **tap/click is the primary interaction**; hover is at most a progressive enhancement and
  is never the only way in;
- keyboard reachable in tab order, activated by Enter/Space, closed by Esc;
- `aria-expanded` on the button and `aria-controls` pointing at the panel, following the
  existing dashboard toggles (`templates/cards.html:339-378`);
- an `aria-label` from `notes_toggle_label` so a screen reader announces a purpose, not
  "button";
- the panel is real text in the DOM (`hidden` when closed), so it is readable with CSS or
  JS unavailable — matching the Hint panel (`templates/conjugate_practice.html:73`).

**Correctness risk — attribution and review state.** `source` (free text: a thread link, a
grammar reference, a person's handle) and `reviewed = true|false` are part of the schema
from day one. An unreviewed note renders with a visible marker (`notes_unreviewed`), and
`reveals_answer = false` requires `reviewed = true`. Prose can teach something wrong with
more authority than a bare word list ever could — the schema should make an unreviewed
claim look unreviewed to the reader, not just to the maintainer.

**Validation (a pytest test, because CI runs only pytest — `.github/workflows/test.yml:32`).**
`tests/test_notes.py` fails the build when:

1. a notes file does not parse, or a `[[note]]` lacks `id` or `text`;
2. two notes share an `id` within a file;
3. `applies_to` does not match the grammar, or names a number **outside the deck** of every
   system it is scoped to;
4. `systems` names a system the language does not declare;
5. the file sits in a directory that is not a registered language;
6. a locale-override file references an `id` that does not exist in the source file;
7. any string contains `<`;
8. `reveals_answer = false` on a note whose text/examples contain a scoped deck word, or
   whose `reviewed` is not `true`.

**Generalisation beyond Welsh — languages in the repo that earn a note immediately:**

| Language | Note | Scope |
|---|---|---|
| `de` | units before tens: *einundzwanzig* is literally "one-and-twenty" | `21-99` |
| `fr` | `quatre-vingts` = "four twenties", a vigesimal survival | `80-99` |
| `fr` | `soixante-dix` = "sixty-ten"; Belgium/Switzerland say `septante`, `nonante` | `70-79,90-99` |
| `es` | 16–29 are written as one word (`dieciséis`, `veintiuno`) | `16-29` |
| `da` | `halvfjerds` is short for "half-fourth times twenty" | `50-99` |
| `cy` | the decimal-system notes (`pum`/`chwe` apocope, `dau ddeg` soft mutation) | `20-99`, decimal |

That list matters strategically: **the notes system earns its keep on five existing
languages before a single traditional Welsh form exists.**

**Cost:** one loader module, one notes file per contributing language, ~1 route helper,
one template partial + one JS file + CSS in both stylesheets, 5 i18n keys × 8 locales,
one test file.

### 2.4 Partial range

The traditional deck realistically covers 0–100, possibly 120. The engine does not assume
parity, but four things go subtly wrong and each needs a named fix:

| What breaks | Where | Fix |
|---|---|---|
| The magnitude dial becomes a no-op — with every number in band 0, levels 1–5 weight identically | `quiz_logic.py:13-27, 58-63` | render the dial only when the active deck spans more than one band; otherwise show `number_system_partial_range_note`. (Same "no dead controls" rule as the toggle.) |
| Easy mode can build a 1-option question: distractors are filtered to the same digit length, and a 0–100 deck has exactly one 3-digit number (`100`) | `quiz_logic.py:86-101` | top up from the rest of the deck when fewer than 3 same-length candidates exist — a small language-agnostic fix that also protects any future sparse deck |
| A shared link's range may fall outside the system's coverage (`?system=traditional&range=500-900`) | `_parse_range` (`app.py:466-487`) | already safe: below `MIN_PRESET_DECK` it falls back to the full deck with a notice (`app.py:484-486`). Add `number_system_partial_range_note` so the fallback is explained, and clamp the config screen's range inputs to the active system's `deck_min`/`deck_max` (already plumbed: `app.py:612-613`, `templates/numbers.html:95-96`) |
| Listening: there are no traditional MP3s | `_available_audio_numbers` (`app.py:1552`) is per-language, not per-system | the system declares `has_audio: false`; the listening tile and the share-builder's listening radio are hidden for it, and a `?system=traditional&mode=listening` link degrades through the existing no-audio path (`app.py:530-538`) |

**Switching system while a range is set**: re-clamp the range to the new system's deck and
notify. `_session_numbers()` already refuses to hand back an empty deck
(`app.py:577-578`), so the worst case is a silently widened drill — which is precisely
what the notice is for.

**Worksheets**: the PDF cache key must include the system. `_worksheet_pdf_cache_key()`
(`app.py:735`) already hashes everything the bytes depend on including the UI language; a
system that is not in the key would serve a decimal PDF for a traditional URL. This is a
one-line change and a hard requirement.

### 2.5 Multiple accepted answers

**Yes, the checker needs a set — and the smallest change is small, because the pattern
already exists twice.**

1. store `session["accepted_answers"]` alongside `session["correct_answer"]` where the
   question is minted (`app.py:1252, 1379`, and the hardcore equivalent);
2. check with `any(check_answer_advanced(user, a) for a in accepted)` — literally
   `app.py:2566-2569` / `app.py:3622-3625`;
3. route `/api/validate` (`app.py:1404`) through `_pick_best_validation()`
   (`app.py:2338`), as `cards_validate_api()` already does (`app.py:2681-2704`);
4. easy mode is unaffected — it presents one canonical string and compares exactly
   (`quiz_logic.py:131`).

**No alternates go into the Welsh data now.** The only alternate the thread produced is
`ugain namyn un` for 19, explicitly described as older/rural and *not* the default; and
`deuddeg`/`deudeg` is an unresolved spelling question, not a second form. Both are
questions, not data (see the questions doc).

**Interaction with the toggle — the important case.** In traditional mode, a correct
*decimal* answer should be **marked incorrect but not called wrong**. The user chose to
practise traditional; accepting decimal would make the mode meaningless. But the answer
*is* correct Welsh, and telling a learner it is wrong teaches something false. So: when
the submitted answer matches the same number's word in the other system (one dict lookup,
no new data), replace the generic incorrect flash with
`number_system_wrong_system_flash` — *"That's the decimal form — this drill is asking for
the traditional form."* Costs one lookup, one key, and no scoring change. Numbers 1–10 are
identical in both systems, so they never reach this branch.

### 2.6 Mutations

**Confirmed — the separate mutations page is the wrong shape; notes are the right one.**
Mutation facts are short, number-attached and context-bound; a page would put them
somewhere a learner never is at the moment they matter, and would duplicate content that
belongs on the Learn page anyway.

Holding the line, stated as a rule a contributor can apply without asking:

> **If the mutation depends on what comes *after* the number, it is a note. If it is
> inside the number word itself, it is the spelling.**

- **Spelling** (already the practice, `languages/cy/generate_numbers.py:6-10`):
  `dau ddeg`, `tri chant`, `dwy fil` — and in traditional, `un ar hugain`,
  `deg a thrigain`, `un ar bymtheg`, because the mutation is internal to the compound.
- **Note, never spelling**: `cant → can` before a noun (`hanner can punt`); the counted
  noun mutating (`blynedd → ugain mlynedd`); `deg → deng` before `m-`. A bare-number drill
  has no following noun, so the deck cannot honestly encode these — and if it tried, the
  drill would start marking correct answers wrong.

The Learn page keeps a prose overview (it already gestures at this,
`templates/learn_cy_en.html:21-26`); the notes carry the point-of-use reminder. No third
surface.

### 2.7 Gender

**Masculine default is defensible — but only with the note present, and the note is the
condition, not a nicety.**

The repo already takes a position on this: the decimal deck ships `dwy fil`, `tair mil`,
`pedair mil` (`languages/cy/generate_numbers.py:78-80`) because the noun (`mil`, feminine)
is *inside* the number word. That is consistent with §2.6 and should stay.

For bare 2 / 3 / 4, the citation form is masculine (`dau`, `tri`, `pedwar`) and that is
what the deck has. Shipping it silently teaches "2 = dau" as unconditional, which is
wrong. Shipping it with a note on 2, 3 and 4 — *"Welsh numbers 2, 3 and 4 agree with the
noun's gender: `dau/dwy`, `tri/tair`, `pedwar/pedair`. This drill shows the masculine
form."* — is honest and is exactly the burden the notes system was designed to carry.

If the notes system were not shipping, the correct answer would be different: state it on
the Learn page and in the config-screen label instead, and do not pretend a bare deck is
neutral. **Whether the drill should ever ask for feminine forms is a question for the
sub**, not a decision to make here.

### 2.8 Ordinals

**Confirmed out of scope, and scoped out explicitly.**

Ordinals are **a separate axis, not a third value of the system toggle.** A toggle value
answers "which words for this number"; ordinals change *the question being asked* —
prompt "13th", not "13". They also drag in their own gender agreement
(`trydydd`/`trydedd`), their own written forms (`22ain`), and their own inventory in both
systems (`trydydd ar ddeg` is a traditional ordinal; a decimal ordinal set exists too).

Future shape, recorded so it is not re-litigated: a `drill_type` selector on the config
screen (`cardinal` | `ordinal`) sitting *beside* the system toggle, backed by an
`ORDINALS` deck per (language, system) with the same `dict[int, str]` shape. Not in this
change; not blocked by it.

### 2.9 Honest labelling (ships first, alone)

Minimal, and built so the copy survives the toggle:

1. **Language card** — reword `cy`'s `ui_descriptions` (8 strings, an existing field in
   `languages/config.py:427-436`, **no new keys**): *"Learn modern decimal Welsh numbers
   from 0 to 10 million"*.
2. **Config screen and mode-selection page** — one notice line rendered whenever a
   language declares more than one system and only one of them is available:
   *"This drill teaches the **decimal** number system. The **traditional** system isn't
   ready for practice yet — read about both."* Built from
   `number_system_only_note` + `number_system_name_*` + `number_system_unavailable_note`,
   **the same keys the toggle will use**, so nothing is thrown away.
3. **Learn page** — the Welsh Learn page *already* says the quiz teaches decimal and that
   traditional survives for time, dates and age (`templates/learn_cy_en.html:21-26`). So
   the honest statement exists in the one place a learner may never visit, and is absent
   from every screen where they actually drill — that is the real gap Phase 0 closes.
   Extend it with a section in `templates/learn_cy_en.html` (English-only content in an
   English-fallback template ⇒ **zero translation debt**) titled "Two ways to count in
   Welsh", carrying the thread's usage table: decimal for arithmetic and counting;
   traditional always for the time and for dates; traditional for age and durations;
   money traditional up to ~30 and decimal above. Items the thread disagreed on
   (50 in money) are stated as disputed or omitted, never resolved by us.

This ships as one commit with no data work and no engine change.

---

## Part 3 — Phased plan

| Phase | What | Depends on | Ships without |
|---|---|---|---|
| **0** | Honest labelling + Learn explainer | nothing | any data or engine work |
| **1** | Data model: more than one numeral system per language | nothing | any UI change |
| **2** | The system toggle: control, state, routing, completeness gate, i18n | Phase 1 | **Phase 4** (gate keeps it hidden) |
| **3** | Per-number notes: schema, file, lightbulb, reveal rule, validation | nothing | Phases 1, 2, 4 |
| **4** | Traditional deck skeleton with gaps marked, filled by native speakers | Phase 1 | **Phase 2** (data can precede the control) |
| **5** | `cy` UI locale skeleton | nothing | everything else |
| **6+** | Ordinals, traditional audio, contextual usage drills | 1–4 | — |

**Independence, stated plainly:**

- **Phase 3 does not depend on Phase 2.** Its first content includes German word-order,
  French `quatre-vingts`, Spanish `dieciséis`, Danish `halvfjerds` and decimal-Welsh
  mutation notes — none of which need a second system to exist. Welsh traditional notes
  sit in the same file, scoped `systems = ["traditional"]`, and are simply inert until
  that deck exists.
- **Phases 2 and 4 may land in either order.** That is the whole purpose of the
  completeness gate: the code depends on the maintainer, the data depends on volunteers,
  and neither should block the other.
- **Phase 5 is independent of all of it** and can be started by any Welsh speaker today.

### Phase 0 — honest labelling (no data work)

| File | Change |
|---|---|
| `languages/config.py` | reword `cy` → `ui_descriptions` (8 strings) to say "modern decimal Welsh" |
| `translations.py` | +5 keys × 8 locales: `number_system_label`, `number_system_name_decimal`, `number_system_name_traditional`, `number_system_only_note`, `number_system_unavailable_note` |
| `app.py` | pass a small `number_system_notice` dict into `mode_selection()` and `number_modes()` renders (no session, no engine change) |
| `templates/numbers.html`, `templates/index.html` | render the notice line (a `.preset-notice`-style strip) |
| `templates/learn_cy_en.html` | new section: "Two ways to count in Welsh" + usage table |
| `tests/test_app.py` | assert `/cy/numbers` names the decimal system and `/cy/learn` contains the explainer |
| `README.md`, `CLAUDE.md` | one line each |

### Phase 1 — multi-system data model (no user-visible change)

| File | Change |
|---|---|
| `languages/config.py` | `number_systems` on the `cy` entry; new helpers `get_number_systems()`, `get_default_number_system()`, `resolve_number_system()`, `system_deck_ready()`; `get_language_numbers(lang_code, system=None)` — **optional** param, existing signature preserved |
| `languages/cy/__init__.py` | export the traditional deck lazily; tolerate the module being absent |
| `languages/cy/numbers_traditional.py` | **new** (may be absent in this phase; the loader treats missing as "system not ready") |
| `tests/test_number_systems.py` | **new**: one-arg call is unchanged for all 15 languages; unknown system falls back to default; undeclared language reports one implicit system; gate returns False for a missing/incomplete deck |
| `ADD_NUMBERS.md` | new section "Languages with more than one numeral system" |
| `CLAUDE.md` | architecture bullet |

### Phase 2 — the toggle

| File | Change |
|---|---|
| `app.py` | `_session_number_system()`; thread the system through `mode_selection`, `number_modes`, `start_quiz`, `_seed_quiz_session` (**carry the key across the clear**), `_session_numbers`, `_parse_preset` (accept `?system=`, **do not add it to `PRESET_PARAM_KEYS`**), `worksheet` + `_worksheet_pdf_cache_key` (**system must be in the key**), `listen_start`/`listen_quiz` (refuse systems with `has_audio: false`) |
| `quiz_logic.py` | `generate_multiple_choice()` tops up distractors when fewer than 3 same-length candidates exist (sparse-deck fix, §2.4) |
| `templates/numbers.html` | system control above the magnitude dial; `system` hidden input in the three Start forms; dial hidden when the active deck spans one band |
| `templates/index.html` | show the active system in the number-practice tile |
| `static/js/preset_link.js` | add `system` to the built URL and to the hidden inputs (mirrors `rangeHiddenInputs`, lines 22, 72-74) |
| `static/css/style.css`, `static/css/style-classic.css` | `.number-system-toggle` — **both** stylesheets |
| `translations.py` | +6 further keys × 8 locales (the remaining `number_system_*`, `preset_notice_system`, `preset_share_system_label`) |
| `tests/test_number_systems.py`, `tests/test_presets.py`, `tests/test_worksheet.py` | toggle absent for single-system languages; absent while the gate is shut; `?system=` link works cold; system survives `_seed_quiz_session`; worksheet PDFs differ per system |
| `tests/test_translations.py` | **new**: key parity across all locales (nothing guards this today) |

### Phase 3 — per-number notes

| File | Change |
|---|---|
| `languages/notes_loader.py` | **new** — parse (`tomllib`), validate, resolve locale overrides, lazy + cached; modelled on `languages/conjugation_loader.py` |
| `languages/cy/notes.toml` | **new** — the seed notes from the thread |
| `languages/de/notes.toml`, `languages/fr/notes.toml`, `languages/es/notes.toml`, `languages/da/notes.toml` | **new** — one or two notes each, proving the schema is not Welsh-shaped |
| `app.py` | `_notes_for(lang, system, number, when)` where `when ∈ {prompt, revealed, reference}`; pass into the quiz, reveal, results, learn and worksheet-answer-key renders |
| `templates/_number_notes.html` | **new** partial (button + `hidden` panel, `aria-expanded`/`aria-controls`) |
| `templates/quiz_easy.html`, `quiz_advanced.html`, `quiz_hardcore.html`, `quiz_listen.html`, `results.html`, `worksheet_sheet.html` | include the partial with the right `when` |
| `static/js/number_notes.js` | **new** — tap-first toggle, Esc to close, no hover dependency |
| `static/css/style.css`, `static/css/style-classic.css` | lightbulb + panel styles, **both** |
| `translations.py` | +5 keys × 8 locales (`notes_toggle_label`, `notes_panel_title`, `notes_untranslated`, `notes_unreviewed`, `notes_source_label`) |
| `tests/test_notes.py` | **new** — the eight validation rules in §2.3, plus: no note renders beside an unanswered prompt unless `reveals_answer = false` |
| `ADD_NOTES.md` | **new** contributor guide (walkthrough B below) |

### Phase 4 — traditional data entry

| File | Change |
|---|---|
| `languages/cy/numbers_traditional.py` | skeleton: **only forms stated verbatim in the thread**; every other slot `None` with a `# TODO` and a pointer to the questions doc |
| `docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md` | kept in sync as answers arrive |
| `tests/test_number_systems.py` | the traditional deck contains no invented forms (every non-`None` entry is on an allow-list of verified forms until review completes) |

### Phase 5 — `cy` UI locale skeleton

| File | Change |
|---|---|
| `config.py` | `"cy"` in `SUPPORTED_UI_LANGUAGES` (line 15) |
| `translations.py` | new `"cy"` dict — 420 keys, English values as placeholders; `language_cy` added to the 8 existing dicts |
| `languages/config.py` | `"cy"` in `ui_names` **and** `ui_descriptions` for all 15 learning languages |
| `templates/base.html` | `('cy', '🏴󠁧󠁢󠁷󠁬󠁳󠁿', 'Cymraeg')` in `ui_langs` (line 144-153) |
| `app.py` | `OG_LOCALE_MAP["cy"] = "cy_GB"` (line 259-268) |
| `ADD_UI_LANGUAGE.md` | **add the missing `OG_LOCALE_MAP` step** — it is absent today |

Ship it with English placeholder values behind `SUPPORTED_UI_LANGUAGES` so `get_text`'s
English fallback (`app.py:339-342`) covers every untranslated key, and a Welsh speaker can
translate one key at a time.

### Phase 6+ — scoped, not detailed

- **Ordinals** — a `drill_type` axis beside the system toggle (§2.8).
- **Traditional audio** — `tools/generate_audio.py` writes `static/audio/<lang>/<n>.mp3`;
  a second system needs a per-system directory and a per-system `_available_audio_numbers`.
- **Contextual usage drills** — "what time is it?", "say this date" — the only format that
  actually teaches *when* each system applies, and the real answer to the thread's point.
  Needs a new question type; do not attempt it inside the number quiz.

---

## Part 4 — Contributor walkthroughs

### A. Adding or fixing a traditional Welsh number

1. Open <https://github.com/stefanwezel/diminumero/blob/main/languages/cy/numbers_traditional.py>.
2. Click the pencil (**Edit this file**). GitHub creates your own copy — you cannot break
   the live site.
3. Find the line for the number you know, e.g.

   ```python
       45: None,  # TODO: not yet verified — see docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md
   ```

4. Replace `None` with the Welsh form in double quotes and delete the `# TODO` comment:

   ```python
       45: "pump ar ddeugain",
   ```

   Rules: lowercase; single spaces; write the form as it is spoken for a bare number, with
   any mutation that is *inside* the number word (`un ar hugain`, not `un ar ugain`). If a
   mutation depends on the noun that follows, it does not belong here — it is a note (B).
   **If you are unsure, leave `None`.** A gap is correct; a guess is a bug.
5. Scroll down, write one line describing the change, and choose **Create a new branch and
   start a pull request**.
6. In the PR description, say how you know the form (course, dictionary, native speaker).
   Automated checks run; a maintainer reviews.
7. When every slot in 0–100 is filled, the "Traditional" option appears on
   diminumero.com/cy/numbers automatically — no further code change.

**Honest note about this walkthrough**: step 1 opens a file whose name ends in `.py`. It
contains nothing but a list of `number: "word",` lines and comments, but it *is* a source
file, so the stated goal ("adding a language means editing a plain text file") is met only
in spirit. This is deliberate: all 15 existing decks use this format, the generator scripts
and tests read it, and a public fork already depends on it — introducing a second format
for the same data would cost more than it buys. If the goal should be met literally, the
cheapest honest alternative is a `numbers.csv` (`number,word` lines) plus a ~10-line
loader for languages that opt in — at the cost of two formats for one concept and updates
to `generate_numbers.py`, `tools/check_worksheet_fonts.py` and the integrity tests. That
choice is the maintainer's; this plan does not assume it.

### B. Adding a note

1. Open <https://github.com/stefanwezel/diminumero/blob/main/languages/cy/notes.toml>
   (or `languages/<code>/notes.toml` for another language; create it if it does not exist).
2. Click the pencil (**Edit this file**).
3. Add a block at the end:

   ```toml
   [[note]]
   id = "cy-ugain-after-ar"
   applies_to = "20"
   systems = ["traditional"]
   text = "After ar, ugain becomes hugain — which is why 21 is un ar hugain."
   source = "r/learnwelsh, August 2026"
   reviewed = false

     [[note.examples]]
     phrase = "un ar hugain"
     gloss = "twenty-one"
   ```

   - `id` — anything unique in the file; lowercase with dashes.
   - `applies_to` — one number (`"20"`), a range (`"11-19"`), a list (`"11-19,30"`), or
     `"all"` for the whole system/language.
   - `systems` — leave it out if the note is true of every system.
   - `text` — plain sentences. No HTML, no links, no formatting.
   - `reviewed = false` until a native speaker has checked it; the site shows an
     "unreviewed" marker until then, which is the honest state.
4. **Create a new branch and start a pull request.** Automated checks confirm the file
   parses, the numbers exist, and the note does not give away a drill answer.
5. Translating a note is a *separate*, optional PR: copy the `id` into
   `languages/cy/notes.de.toml` with a translated `text`. Untranslated notes are shown in
   the original language with a marker — nothing is hidden for want of a translation.

**This walkthrough requires no source file and no local setup.** It is entirely a browser
task, which is the standard the deck format does not quite meet.

### Doc updates required to match

- `ADD_NUMBERS.md` — new section "Languages with more than one numeral system" (declaring
  `number_systems`, the second deck file, the `None`-gap convention, the completeness
  gate), plus checklist lines for both.
- `ADD_NOTES.md` — **new**, walkthrough B plus the full schema and the leak rule.
- `ADD_UI_LANGUAGE.md` — add the missing `OG_LOCALE_MAP` step (§1.6).
- `CLAUDE.md` — architecture bullets for `number_systems`, the notes loader and the leak
  rule; note that the worksheet PDF cache key now includes the system.
- `README.md` — one feature line each.

---

## Part 5 — Risks

| Risk | Why it is real here | Mitigation |
|---|---|---|
| **Silent breakage of the other 14 languages** | `get_language_numbers()` has five call sites plus two tools; a required parameter would break all of them | the `system=None` default keeps every existing call identical; `tests/test_number_systems.py` asserts the one-arg call returns the same dict for all 15 languages |
| **The toggle rendering for single-system languages** | a naive `{% if %}` on "has systems" is true everywhere once every language gets an implicit system | the template condition is `number_systems | length > 1` on *available* systems; a test asserts the control is absent from `/es/numbers` and from `/cy/numbers` while the gate is shut |
| **A note leaking a drill answer** | the motivating note (`deg` → `deng`) leaks; so do 10 of the 13 seed notes | default `reveals_answer = true`; render position by surface; a mechanical CI check on `reveals_answer = false`; `false` additionally requires `reviewed = true` because the check catches literal leaks only ("two nines" for `deunaw` would pass it) |
| **A wrong or unsourced note teaching with authority** | prose is harder to review than a word list, and a note *looks* editorial | `source` and `reviewed` in the schema from day one; visible "unreviewed" marker; the seed notes ship as `reviewed = false` until the sub reviews them (see the questions doc) |
| **Format churn rotting the existing fork** | someone forked the repo to look at it after the thread | `numbers.py` is untouched; the new deck is a sibling file in the identical format; `get_language_numbers()` keeps its signature; the notes file is additive and optional |
| **Two new translation debts while asking for a 9th locale** | Phase 2 = 88 strings, Phase 3 = 40 strings, and Phase 5 asks for 420 more | English fallback per key already exists (`app.py:339-342`), so nothing breaks while translations lag; keys land in English everywhere and are translated incrementally; the Learn-page explainer (the longest copy) stays English-only behind the `_en` template fallback; and `tests/test_translations.py` makes the debt visible instead of silent |
| **Worksheet PDF cache serving the wrong system** | the cache is keyed by a hash and shared by three gunicorn workers via `instance/worksheet_pdf/` | the system joins the cache key (`app.py:735`), with a test asserting two systems produce different bytes |
| **`?system=` accidentally starting a drill or de-indexing the page** | `_has_preset_params()` renders the drill for any recognised param and sets `noindex` (`app.py:450, 313`) | `system` deliberately stays out of `PRESET_PARAM_KEYS`; a test asserts `/cy/numbers?system=traditional` renders the config screen and stays indexable |
| **The magnitude dial silently doing nothing on a 0–100 deck** | every number lands in band 0, so levels 1–5 are identical | hide the dial when the deck spans one band, with the partial-range note in its place |
| **Defaulting to unreviewed data** | a half-filled traditional deck reaching learners | the completeness gate is derived from the data, the default system stays decimal, and Phase 4 ships gaps as `None` rather than guesses |
| **Teaching bare traditional forms without their context** | the forms are licensed by context the drill removes | the notes (`reveals_answer = false` usage notes) and the Learn explainer carry the "when", and contextual drills are named as Phase 6 rather than pretended to be solved |

---

## Part 6 — Open questions

Blocking Phase 4, in priority order, with the full text to post back to the sub in
[`docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md`](../QUESTIONS-FOR-NATIVE-SPEAKERS.md):

1. **41–99** — the largest gap; no forms were given for 41–49, 51–59, 61–69, 71–79, 81–89,
   91–99. Only `pump ar ddeugain` (45) appeared, inside a counter-example.
2. `deuddeg` vs `deudeg` (12).
3. `hanner can punt` vs `pum deg punt` for £50.
4. The form for 120.
5. Whether feminine `dwy`/`tair`/`pedair` belong in a bare-number drill at all.
6. Per-number frequency — which traditional forms are worth drilling.
7. **What the two systems should be called in Welsh** — the toggle needs two idiomatic
   labels; "decimal" and "traditional" are our English framing.
8. Review of the 13 seed notes, which are written in our words from thread comments.

---

## Part 7 — Implementation notes

What was built, and where the build departed from the plan above. Written after the
fact so the two documents don't quietly disagree.

### State on delivery

| Phase | Status |
|---|---|
| 0 — honest labelling + explainer | shipped |
| 1 — multi-system data model | shipped |
| 2 — the system toggle | shipped, and **currently invisible on `/cy` by design** — the gate is shut |
| 3 — per-number notes | shipped, with seed content for `cy`, `de`, `es`, `fr`, `da` |
| 4 — traditional deck skeleton | shipped: 30 verified forms, 70 explicit gaps |
| 5 — `cy` UI locale | shipped as plumbing + an empty dict; no Welsh strings invented |
| 6+ — ordinals, audio, contextual drills | not started, deliberately |

Tests: 573 pass (435 pre-existing, 138 new across `test_number_systems.py`,
`test_notes.py`, `test_translations.py`).

**The Welsh toggle does not appear on the live site yet, and that is the feature
working.** 70 of the 100 traditional forms are unknown, so `requires_complete: (1, 100)`
keeps the system out of the UI. Filling the gaps is a data-only pull request.

### Departures from the plan

1. **The `reviewed` requirement moved from CI into the render filter.** The plan had
   `reveals_answer = false` requiring `reviewed = true` as a validation rule. It is
   better as a display rule: the data then states two independent facts (does this
   reveal the answer / has a human checked it) and the policy combines them. A note can
   now be honestly marked as non-revealing while still waiting for review, and it starts
   appearing beside live prompts the moment someone reviews it — no edit to the note.
   CI still mechanically rejects a `reveals_answer = false` that spells out an answer.
2. **`applies_to` ranges only have to *overlap* the deck.** The plan said a note
   pointing outside the language's range fails CI. Implemented as written, that rejected
   a perfectly good Spanish note on `100-199`, because decks are deliberately sparse
   above 100. The rule is now: a single number must exist; a range must match at least
   one number. Same protection against typos, no false positives.
3. **No `languages/cy/__init__.py` change was needed.** The loader uses `importlib`, so
   a second deck module is found without an export. One fewer file to touch per system.
4. **Notes render on four surfaces, not one.** Reveal modals (advanced/hardcore/
   listening), the results page, and the worksheet answer key — plus the prompt itself
   for the notes that qualify. The results page matters more than expected: easy mode
   has no reveal step, so without it easy-mode players would never see a note at all.
5. **The worksheet answer key got notes, and the font checker was extended to match.**
   `tools/check_worksheet_fonts.py` now derives its required character set from note
   text as well as decks and UI strings. Free-form contributor prose is exactly the kind
   of text that arrives with a character no installed font can draw, and a PDF rendered
   without the font is still a valid-looking 200.
6. **Phase 5 ships an empty `cy` dict, not 420 English placeholders.** The plan said
   English values as placeholders. That would have made every string *look* translated
   with no way to tell which ones actually were. Instead the dict is empty, English
   fallback covers every key, and a new `PARTIAL_UI_LANGUAGES` set puts a line on every
   page saying the interface is only partly translated. A translator adds one key at a
   time and each goes live on its own.
7. **No Welsh `ui_names` / `ui_descriptions` were added.** The plan's Phase 5 file list
   included them for all 15 learning languages, which would have meant inventing Welsh
   language names. They fall back to the English names instead, and a Welsh speaker can
   add them with the rest of the locale.
8. **`language_cy` was not added to the other locales.** `ADD_UI_LANGUAGE.md` asks for
   it, but the `language_<code>` keys are not referenced by any template — the switcher
   uses native names hardcoded in `base.html`. Adding one would have been dead weight.
9. **The magnitude dial hides on a single-band deck, which the Welsh traditional deck is
   not.** With 100 in it, a 1–100 deck spans two bands, so the dial still renders and
   still does something (it changes how often 100 comes up). The mechanism is in place
   for a genuinely single-band deck; it just doesn't trigger here.
10. **Multiple accepted answers (§2.5) was implemented as the cross-system nudge only.**
    The `accepted_answers` session plumbing was not added, because no verified Welsh
    alternate exists to put in it — `ugain namyn un` is explicitly not a default and the
    `deuddeg`/`deudeg` question is unresolved. What did ship is the honest half: an
    answer that is correct in the language's *other* system is named as such rather than
    marked plainly wrong. The set-based checker remains a small change when real
    alternates arrive (`_acceptable_answers` in `app.py` is the pattern).

### What a reviewer should look at first

- `languages/config.py` — the `number_systems` declaration and the four helpers around it.
- `languages/notes_loader.py` — the scope grammar and the two halves of the leak rule.
- `tests/test_notes.py::TestAnswerLeakRule` — the rule stated as executable assertions.
- `tests/test_number_systems.py::TestCompletenessGate` — proof the toggle appears exactly
  when the data is ready and not before.

