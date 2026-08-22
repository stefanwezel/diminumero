# Adding a UI Language

This guide explains how to add a new **UI language** — the language used for the app's interface (buttons, labels, instructions). This is different from a **learning language** (the language whose numbers the user practises).

## Overview

| Concept | Example | Where configured |
|---|---|---|
| UI language | The app shows "Start Learning" in French | `translations.py`, `config.py`, `base.html` |
| Learning language | The user practises French numbers | `languages/config.py`, `languages/fr/` |

Currently supported UI languages: English (`en`), German (`de`), Spanish (`es`), Italian (`it`), French (`fr`), Portuguese (`pt`), Arabic (`ar`), Ukrainian (`uk`), Welsh (`cy`, **in progress**).

> **You do not have to translate everything at once.** `get_text()` falls back to
> English per key, so a locale can go live with ten strings translated and grow
> from there. See [Translating incrementally](#translating-incrementally).

---

## Steps

### 1. `config.py` (root)

Add the new code to `SUPPORTED_UI_LANGUAGES`. While the translation is still incomplete, also add it to `PARTIAL_UI_LANGUAGES`. If it is a right-to-left language, add it to `RTL_UI_LANGUAGES` too:

```python
SUPPORTED_UI_LANGUAGES = {"en", "de", "es", "it", "fr", "pt", "ar", "uk", "cy", "xx"}

# while it is still being translated:
PARTIAL_UI_LANGUAGES = {"cy", "xx"}

# only if RTL:
RTL_UI_LANGUAGES = {"ar", "xx"}
```

`PARTIAL_UI_LANGUAGES` puts a short line at the top of every page saying the
interface is only partly translated and the rest is English. That is the honest
state, and it is better than a page that quietly looks finished. Remove the code
from the set when the dict is complete — a test (`tests/test_translations.py`)
checks that the set and the actual coverage agree, in both directions.

The `RTL_UI_LANGUAGES` set drives the `dir` attribute on `<html>`. The CSS already contains `[dir="rtl"]` rules that mirror the globe button and dropdown.

### 2. `translations.py`

Add a new top-level dict keyed by your language code. Copy the entire `"en"` dict and translate every value. Rules:

- Keep `LANGUAGE_NAME_PLACEHOLDER` **verbatim** in any string that contains it — it is replaced at runtime with the learning-language name.
- Translate `meta_desc_index` and `seo_title_index` to list the learning language names in the new UI language.
- The `flash_correct` / `flash_incorrect` / `flash_gave_up` values use `{}` as a format placeholder — keep it exactly.

```python
TRANSLATIONS = {
    ...
    "xx": {
        "app_title": "diminumero",
        "language_en": "...",
        ...
    },
}
```

Also add a `"language_xx"` key to **every existing** UI language dict so those UIs can display the new language's name in the globe dropdown:

```python
# in "en":
"language_xx": "Xhosa",
# in "de":
"language_xx": "Xhosa",
# etc. for es, it, fr, pt, ar, uk
```

> **Note**: Learning language names and descriptions (shown on the language cards) are **not** stored in `translations.py`. They come from `ui_names` and `ui_descriptions` in `languages/config.py`. When you add a new UI language, add the new code to those dicts for every learning language — see step 3.

### 3. `languages/config.py`

For **every** learning language entry in `AVAILABLE_LANGUAGES`, add the new code to both `ui_names` and `ui_descriptions`:

```python
"es": {
    ...
    "ui_names": {
        "en": "Spanish", "de": "Spanisch", ..., "xx": "Espangolo",
    },
    "ui_descriptions": {
        "en": "Learn Spanish numbers from 1 to 10 million",
        ...,
        "xx": "...",
    },
},
```

There are currently 15 learning languages: `es`, `fr`, `ja`, `de`, `ko`, `it`, `zh`, `pt`, `tr`, `ne`, `sv`, `da`, `no`, `cy`, `ga`.

### 4. `templates/base.html`

Add a tuple to the `ui_langs` list inside the language switcher block:

```html
{% set ui_langs = [
    ('en', '🇬🇧', 'English'),
    ...
    ('xx', '🏳️', 'Native Name'),
] %}
```

Use the language's own native name as the label (e.g. `'Français'` not `'French'`).

### 5. `app.py` — `OG_LOCALE_MAP`

Add the locale used in the `og:locale` meta tag. Without this the page claims
`en_US` to every social network and crawler, whatever the interface says:

```python
OG_LOCALE_MAP = {
    ...
    "xx": "xx_XX",   # e.g. "cy": "cy_GB"
}
```

### 6. Learn page templates (optional)

The `learn()` route generates template names as `learn_{lang_code}_{ui_lang}.html` and falls back to `learn_{lang_code}_en.html` if the UI-language-specific file doesn't exist. You don't *have* to create translated learn templates — the English fallback works automatically. If you do want translated learn pages, create one file per learning language that has learn materials:

```
templates/learn_es_xx.html
templates/learn_fr_xx.html
... (one per language in the has_learn_materials set)
```

---

## Translating incrementally

A locale does **not** have to be complete to be useful. `get_text()` falls back
to English for any key a locale is missing (`app.py`), so:

1. add the code to `SUPPORTED_UI_LANGUAGES` **and** `PARTIAL_UI_LANGUAGES`;
2. add an empty (or nearly empty) dict to `translations.py`;
3. translate keys one at a time — each one goes live on its own.

Welsh (`cy`) is set up exactly this way today: the dict is deliberately empty
rather than pre-filled with English strings, because a copy of the English text
under a `cy` key looks translated and nobody can tell the difference afterwards.
Copy the key name from the `"en"` dict, translate the value, open a PR.

---

## SEO checklist

All SEO-relevant strings are driven by `translations.py` keys, so once Step 2 is done:

- `<title>` — from `seo_title_*` keys
- `<meta name="description">` — from `meta_desc_*` keys
- `og:title` / `og:description` — same keys via template blocks
- `<html lang="…">` — set automatically from `ui_language` context variable
- `<html dir="…">` — set automatically from `ui_dir` context variable (RTL handled)
- `<link rel="canonical">` — always the page's canonical URL, language-agnostic

---

## RTL languages

Simply add the code to `RTL_UI_LANGUAGES` in `config.py`. The CSS `[dir="rtl"]` rules already handle:

- Globe button moving from top-right to top-left
- Dropdown aligning to the left edge instead of right

No template changes are needed for RTL support.

---

## Testing

1. Start the dev server: `uv run flask --app app run --debug`
2. Visit `/set_language/xx` — the page should reload in the new UI language.
3. Click the 🌐 globe — verify the new language appears highlighted in the dropdown.
4. If RTL: inspect `<html dir="rtl">` in the source and verify the globe is top-left.
5. Check `/`, `/<lang_code>`, `/about`, `/privacy` pages render in the new language.
6. Verify learning language cards show translated names and descriptions (from `ui_names`/`ui_descriptions` in `languages/config.py`).
7. Run `uv run pytest` — all existing tests should pass.
8. Test an invalid code: `/set_language/zz` should redirect without changing the session language.
