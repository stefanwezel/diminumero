# Adding a UI Language

This guide explains how to add a new **UI language** — the language used for the app's interface (buttons, labels, instructions). This is different from a **learning language** (the language whose numbers the user practises).

## Overview

| Concept | Example | Where configured |
|---|---|---|
| UI language | The app shows "Start Learning" in French | `translations.py`, `config.py`, `base.html` |
| Learning language | The user practises French numbers | `languages/config.py`, `languages/fr/` |

Currently supported UI languages: English (`en`), German (`de`), Spanish (`es`), Italian (`it`), French (`fr`), Portuguese (`pt`), Arabic (`ar`), Ukrainian (`uk`).

---

## Steps

### 1. `config.py` (root)

Add the new code to `SUPPORTED_UI_LANGUAGES`. If it is a right-to-left language, also add it to `RTL_UI_LANGUAGES`:

```python
SUPPORTED_UI_LANGUAGES = {"en", "de", "es", "it", "fr", "pt", "ar", "uk", "xx"}

# only if RTL:
RTL_UI_LANGUAGES = {"ar", "xx"}
```

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

Also add a `"language_xx"` key to **every existing** UI language dict (including `"en"` and `"de"`) so those UIs can refer to your new language by name if needed:

```python
# in "en":
"language_xx": "Xhosa",
# in "de":
"language_xx": "Xhosa",
# etc.
```

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

There are currently 13 learning languages: `es`, `fr`, `ja`, `de`, `ko`, `it`, `zh`, `pt`, `tr`, `ne`, `sv`, `da`, `no`.

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
6. Run `uv run pytest` — all existing tests should pass.
7. Test an invalid code: `/set_language/zz` should redirect without changing the session language.
