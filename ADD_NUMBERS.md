# Adding Number Practice for a New Language to diminumero

This guide explains how to add a new learning language to diminumero's **number-translation** practice (the core quiz). It is the starting point for any new language.

Related guides:
- [ADD_LISTENING_EXERCISES.md](ADD_LISTENING_EXERCISES.md) — add the spoken-number Listening quiz to a language that already has numbers.
- [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) — add a Learn/tutorial page for a language.
- [ADD_NOTES.md](ADD_NOTES.md) — add a short per-number note (the lightbulb).
- [ADD_CONJUGATING_PRACTICE.md](ADD_CONJUGATING_PRACTICE.md) — the Spanish verb-conjugation section (regenerating the pool, extending it).

## Overview

diminumero supports multiple languages for number learning. Currently supported (all `ready: True`):
- **Spanish (es)**, **French (fr)**, **Japanese (ja)**, **German (de)**, **Korean (ko)**
- **Italian (it)**, **Chinese (zh)**, **Portuguese (pt)**, **Turkish (tr)**, **Nepalese (ne)**
- **Swedish (sv)**, **Danish (da)**, **Norwegian (no)**, **Welsh (cy)**, **Irish (ga)**


## Steps to Add a New Language

### 1. Create Language Directory

```bash
mkdir -p languages/<lang_code>
touch languages/<lang_code>/__init__.py
```

### 2. Register Language in Config

Edit `languages/config.py` and add your language to `AVAILABLE_LANGUAGES`:

```python
AVAILABLE_LANGUAGES = {
    'es': {...},  # Existing languages
    'xx': {  # Your new language code
        'name': 'LanguageName',
        'native_name': 'Native Name',
        'flag': '🏳️',  # Emoji flag
        'ready': False,  # Set to True when ready
        'has_learn_materials': False,  # True once you add learn templates (step 6)
        'has_audio_mode': False,       # True once you generate Listening MP3s (step 9)
        'description': 'Learn LanguageName numbers!',
        'validation_strategy': 'word_based',  # or 'component_based'
        # Display name in each supported UI language
        'ui_names': {
            'en': 'LanguageName', 'de': 'Sprachname', 'es': 'NombreLengua',
            'it': 'NomeLingua', 'fr': 'NomLangue', 'pt': 'NomeLíngua',
            'ar': 'اسم اللغة', 'uk': 'НазваМови',
        },
        # Description shown on the language selection page, in each UI language
        'ui_descriptions': {
            'en': 'Learn LanguageName numbers from 0 to 10 million',
            'de': 'Lerne Sprachname Zahlen von 1 bis 10 Millionen',
            'es': 'Aprende los números en NombreLengua del 1 al 10 millones',
            'it': 'Impara i numeri in NomeLingua da 1 a 10 milioni',
            'fr': 'Apprenez les nombres en NomLangue de 1 à 10 millions',
            'pt': 'Aprenda os números em NomeLíngua de 1 a 10 milhões',
            'ar': 'تعلم الأرقام باللغة من 1 إلى 10 ملايين',
            'uk': 'Вивчайте числа від 1 до 10 мільйонів',
        },
        # Word shown to the user when they answer correctly (in the target language)
        'feedback_expression': 'Correct!',
    },
}
```

> **Note on translations**: `ui_names` and `ui_descriptions` are how your language appears across all 8 UI languages. The app resolves `lang_xx_name` and `lang_xx_description` keys dynamically from these dicts — you do **not** need to add anything to `translations.py` for the language cards.

Update the import logic in `get_language_numbers()` in the same file — add an `elif` branch:

```python
elif lang_code == 'xx':
    from .xx import NUMBERS
```

### 3. Create Number Data

Create `languages/<lang_code>/numbers.py`:

```python
"""<Language> numbers data for diminumero."""

NUMBERS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    # Add more numbers...
}
```

**Start at 0.** Every deck includes zero — it is a normal quiz and worksheet
answer. Listening mode is the one exception, and it excludes zero on its own
because there is no `0.mp3`, so nothing extra is needed for it.

### 4. Create Number Generator (Optional but Recommended)

Copy and adapt `languages/es/generate_numbers.py`:

```python
"""Generate <Language> numbers programmatically for diminumero."""

def number_to_<language>(n):
    """Convert a number to <Language>."""
    # Implement language-specific logic
    pass

# Generate numbers and write to numbers.py
# ...
```

### 5. Create Package Init

Create `languages/<lang_code>/__init__.py`:

```python
"""<Language> language module for diminumero."""

from .numbers import NUMBERS

__all__ = ['NUMBERS']
```

### 6. Create Learn Pages (Optional)

If you want a learn/tutorial page for this language, create one template per UI language:

```
templates/learn_<lang_code>_en.html   ← required (fallback for all UI languages)
templates/learn_<lang_code>_de.html
templates/learn_<lang_code>_es.html
templates/learn_<lang_code>_it.html
templates/learn_<lang_code>_fr.html
templates/learn_<lang_code>_pt.html
templates/learn_<lang_code>_ar.html
templates/learn_<lang_code>_uk.html
```

The `_en` template is the only required one — the app falls back to it when a UI-language-specific template doesn't exist.

Then set **one flag** in `languages/config.py` — no `app.py` edits are needed:

```python
'xx': {
    ...
    'has_learn_materials': True,
    ...
}
```

`mode_selection()`, `results()`, `learn()`, and `sitemap_xml()` all consult `get_languages_with_learn_materials()`, which derives the list from that flag (plus `ready: True`). There are no hardcoded language sets in `app.py`.

See [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) for the full learn-page guide.

### 7. Update SEO Assets

**`translations.py`** — Add the language name to the index page SEO strings in **all 8 UI languages**:
- `meta_desc_index` — the `<meta name="description">` for the landing page
- `seo_title_index` — the `<title>` for the landing page

These are the only keys in `translations.py` that need updating for a new learning language.

**`templates/language_selection.html`** — Add your language code to the JSON-LD `inLanguage` array:
```json
"inLanguage": ["es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "ne", "sv", "da", "no", "cy", "ga", "xx"]
```

### 8. Enable the Language

Once everything is ready:

1. Set `'ready': True` in `languages/config.py`
2. Test thoroughly
3. Deploy!

### 9. Add Listening Audio (Optional)

Once the number deck exists you can optionally add the spoken-number **Listening**
quiz for the language. That flow (voice pools, generating the MP3s, flipping
`has_audio_mode`) now lives in its own guide:
**[ADD_LISTENING_EXERCISES.md](ADD_LISTENING_EXERCISES.md)**.

## Example: Adding Quechua

```bash
# 1. Create directory
mkdir -p languages/qu
touch languages/qu/__init__.py

# 2. Edit languages/config.py - add to AVAILABLE_LANGUAGES:
'qu': {
    'name': 'Quechua',
    'native_name': 'Runasimi',
    'flag': '🇵🇪',
    'ready': False,
    'description': 'Learn Quechua numbers from 0 to millions!',
    'validation_strategy': 'word_based',
    'ui_names': {
        'en': 'Quechua', 'de': 'Quechua', 'es': 'Quechua',
        'it': 'Quechua', 'fr': 'Quechua', 'pt': 'Quechua',
        'ar': 'كيتشوا', 'uk': 'Кечуа',
    },
    'ui_descriptions': {
        'en': 'Learn Quechua numbers from 0 to 10 million',
        'de': 'Lerne Quechua Zahlen von 1 bis 10 Millionen',
        'es': 'Aprende los números en quechua del 1 al 10 millones',
        'it': 'Impara i numeri in quechua da 1 a 10 milioni',
        'fr': 'Apprenez les nombres en quechua de 1 à 10 millions',
        'pt': 'Aprenda os números em quechua de 1 a 10 milhões',
        'ar': 'تعلم الأرقام بالكيتشوا من 1 إلى 10 ملايين',
        'uk': 'Вивчайте числа кечуа від 1 до 10 мільйонів',
    },
    'feedback_expression': 'Allinmi!',
}

# 3. Edit languages/config.py - add import in get_language_numbers():
elif lang_code == 'qu':
    from .qu import NUMBERS

# 4. Create numbers.py with Quechua translations

# 5. Test with ready: False (shows "Coming Soon")

# 6. When ready, set ready: True in languages/config.py
```

## Languages with More Than One Numeral System

Some languages have two ways of saying the same number, both current, used in
different situations:

| Language | Systems |
|---|---|
| **Welsh (`cy`)** | decimal (`dau ddeg pump`) and traditional/vigesimal (`pump ar hugain`) — the traditional one is obligatory for the time, dates and age |
| Korean (`ko`) | Sino-Korean (`일, 이, 삼`) and native (`하나, 둘, 셋`) — only Sino ships today |
| Japanese (`ja`) | Sino-Japanese and native *wago* (`ひとつ, ふたつ`) — only Sino ships today |
| French (`fr`) | standard (`soixante-dix`) and Belgian/Swiss (`septante`, `nonante`) |

A language declares its systems in `languages/config.py`. **A language that
declares nothing has exactly one system and behaves as it always has** — this is
purely additive.

```python
"cy": {
    ...
    "number_systems": [
        {"key": "decimal", "module": "numbers", "default": True},
        {
            "key": "traditional",
            "module": "numbers_traditional",
            "requires_complete": (1, 100),   # the completeness gate, below
            "has_audio": False,              # no MP3s for this system
        },
    ],
},
```

| Field | Meaning |
|---|---|
| `key` | Used in URLs (`/cy/numbers?system=traditional`) and in note scoping. Also the i18n key suffix: add `number_system_name_<key>` and `number_system_desc_<key>` to **all** UI languages in `translations.py`. |
| `module` | The file under `languages/<code>/` holding this system's `NUMBERS` dict. |
| `default` | The system a bare `/<lang>` URL drills. Exactly one system should have it. |
| `requires_complete` | `(low, high)` — the range that must be filled before the system is offered. |
| `has_audio` | Whether the Listening quiz may use this deck. |

### The completeness gate

A second system is **offered only when its deck is actually usable**, and that is
derived from the data, not from a flag someone has to remember to flip. While any
number in `requires_complete` is missing, the system does not appear in the UI at
all — no toggle, no dead control, no half-empty drill. The pull request that
fills the last gap turns the feature on with no code change.

This is what lets the code and the data land in either order, which matters when
the data depends on volunteers.

### Provenance: where a form came from

A deck being assembled from public review is a set of claims, and the difference
between "a speaker told us this" and "a rule produced this" matters more than the
spelling does — a plausible wrong form teaches with exactly the same confidence
as a right one.

Welsh traditional is the first deck to track this. Instead of `{number: "word"}`
it carries a list of forms per number, each with a `source`:

```python
SPEAKER_FORMS = {
    13: [
        {"text": "tri ar ddeg",  "gender": "m", "source": "single"},
        {"text": "tair ar ddeg", "gender": "f", "source": "reconstructed"},
    ],
}
```

| `source` | Means | Served to learners? |
|---|---|---|
| `confirmed` | two or more speakers agreed, or one corrected another | yes |
| `single` | one speaker, uncorroborated | yes |
| `reconstructed` | derived from a grammatical rule, by a script or an LLM — **no speaker has confirmed it** | **no**, unless `SERVE_RECONSTRUCTED` |

`config.SERVE_RECONSTRUCTED` (default `False`) is the switch. While it is off, a
number whose only forms are reconstructed is **absent from the deck entirely** —
the drill skips it. It does not fall back to the other system and it does not
render a blank. Reconstructed forms are committed anyway for two reasons, and
only two: so they can be exported for review, and so they can be switched on in
one line when they come back confirmed.

`languages/provenance.py` holds the machinery (`build_numbers`, `merge_forms`,
`validate_forms`); the deck module derives a plain `NUMBERS` dict from its forms,
so the loader and every caller see the same `dict[int, str]` as any other
language.

Two files, on purpose:

- `numbers_traditional.py` — **hand-edited**, holds what speakers told us. No
  script ever writes it, so an editorial comment or a newly confirmed form cannot
  be clobbered by a rerun.
- `numbers_traditional_generated.py` — **machine-owned**, holds rule-derived
  forms, entirely `reconstructed`. Never edited by hand; to correct one of these,
  add the speaker's form to the hand-edited file, which wins.

### Generating rule-governed forms

`languages/cy/generate_numbers_traditional.py` is the model. Welsh 41–99 is not
54 facts but one rule (`[unit] + connective + [score]`), and the generator
encodes it, along with the mutation the connective triggers — the two are one
choice, not two.

Two things it must do, and both are the point rather than polish:

1. **Reproduce every confirmed form, or abort.** If the rule can't produce
   `deg a thrigain`, the rule is wrong, not the expectation. Flipping the
   unresolved connective to its other value fails the run with a message naming
   the confirmed forms it contradicts, instead of quietly emitting 54 wrong ones.
2. **Report disagreements rather than resolving them.** Where the rule and a
   speaker differ (Welsh 45), the speaker's form is what gets served, the rule's
   form is kept as a withheld alternative, and the run prints the conflict as a
   question for the next review round.

### Getting forms confirmed

```bash
uv run tools/export_unconfirmed_forms.py --source single    # the smallest ask
uv run tools/export_unconfirmed_forms.py --include-notes    # everything
```

Dumps a markdown table of every form no speaker has confirmed, ready to post
where speakers are. Withholding unconfirmed forms is only half a policy; the
other half is making them cheap to check.

### Walkthrough: fill in a missing number

**This one does need a file ending in `.py`** — see the note at the end.

1. Open the deck on GitHub, e.g.
   [`languages/cy/numbers_traditional.py`](languages/cy/numbers_traditional.py).
2. Click the pencil (**Edit this file**). GitHub makes your own copy.
3. Find the number you know, or add it if it isn't there:

   ```python
       45: [{"text": "pump ar ddeugain", "source": "single"}],
   ```

4. Add your form, or correct the one there. `source` is the important field —
   `single` if you are the only person we have heard it from, `confirmed` if you
   are agreeing with a form already listed:

   ```python
       45: [{"text": "pump ar ddeugain", "source": "confirmed"}],
   ```

   If your form differs from one the generator produced, leave the generated one
   alone — it lives in `numbers_traditional_generated.py`, it is never shown to
   anyone, and the next run will report the disagreement.

   Rules: lowercase; single spaces between words; include any mutation that
   happens **inside** the number word (`un ar hugain`, not `un ar ugain`). A
   mutation caused by the noun that comes *after* the number does not belong
   here — that is a note ([ADD_NOTES.md](ADD_NOTES.md)). Add
   `"gender": "m"` / `"f"` only where the form actually changes with the noun's
   gender.
5. **If you are unsure, leave the `None`.** A gap is correct and harmless; a
   plausible guess teaches someone the wrong thing with full confidence.
6. Scroll down and choose **Create a new branch and start a pull request**. Say
   in the description how you know the form (course, dictionary, native speaker).

> **Honest caveat.** Step 1 opens a Python file. It contains nothing but
> `number: "word",` lines and comments, but the extension is real. We keep this
> format because all fifteen existing decks, the generator scripts and the tests
> use it, and a second format for the same data would rot. Notes files
> (`notes.toml`) are the plain-text path and need no source file at all.

### Checklist for a second system

- [ ] `number_systems` declared in `languages/config.py`, one entry with `default: True`
- [ ] `languages/<code>/<module>.py` created; anything unverified is either absent or marked `reconstructed`
- [ ] `number_system_name_<key>` and `number_system_desc_<key>` added to all UI languages in `translations.py`
- [ ] A test asserting the new deck contains no invented forms (see `tests/test_number_systems.py`)
- [ ] Listening: `has_audio: False` unless MP3s exist for that system
- [ ] Native-speaker review of every `single` form before the gate opens
- [ ] `uv run tools/export_unconfirmed_forms.py` posted somewhere speakers will see it

## Number Generation Best Practices

1. **Coverage**: Include variety across magnitudes
   - 0-100: All numbers (the generator's `range(0, 101)` — don't drop the 0)
   - 100-1000: Good coverage
   - 1000+: Sample representative numbers

2. **Irregular forms**: Don't forget special cases
   - Spanish: cien/ciento, veintiún vs veinte y uno
   - Each language has its quirks!

3. **Test thoroughly**: Verify accuracy of generated numbers
   - Have a native speaker review
   - Test edge cases (100, 1000, millions, etc.)

## Testing Checklist

Before marking a language as `ready: True`:

- [ ] Numbers dictionary is complete and accurate
- [ ] Language registered in `languages/config.py` with `ui_names` and `ui_descriptions` for all 8 UI languages, plus `feedback_expression`
- [ ] `elif` branch added to `get_language_numbers()` in `languages/config.py`
- [ ] Language appears on selection page with correct name in each UI language
- [ ] Mode selection works when accessed directly
- [ ] Quiz modes function correctly
- [ ] Results page displays properly
- [ ] (Optional) Learn pages created and `has_learn_materials: True` set in `languages/config.py`
- [ ] (Optional) Listening audio added — see [ADD_LISTENING_EXERCISES.md](ADD_LISTENING_EXERCISES.md)
- [ ] `meta_desc_index` and `seo_title_index` updated in `translations.py` for all 8 UI languages
- [ ] Language code added to JSON-LD `inLanguage` in `templates/language_selection.html`
- [ ] Edge cases tested (very small/large numbers)
- [ ] Native speaker review completed


## Architecture

The multi-language system consists of:

1. **languages/** directory - Contains language-specific data
   - `config.py` - Language registry and metadata
   - `<lang_code>/` - Individual language directories
     - `numbers.py` - Number translations
     - `generate_numbers.py` - Script to generate numbers
     - `__init__.py` - Package initialization

2. **Route structure** - URL pattern: `/<lang_code>/...`
   - `/` - Language selection page
   - `/<lang_code>` - Mode selection page
   - `/<lang_code>/quiz/<mode>` - Quiz pages
   - `/<lang_code>/results` - Results page
   - `/<lang_code>/learn` - Learn page

3. **Session management**
   - `language` - UI language (one of the 8 supported UI languages)
   - `learn_language` - Learning language (es, fr, ja, de, …)


## Questions?

Check existing implementations in `languages/es/` for reference, or contact the maintainer.
