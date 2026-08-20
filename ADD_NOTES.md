# Adding Per-Number Notes

A **note** is one short fact attached to a number: *"Before a word beginning
with m-, `deg` becomes `deng`."* On the site it appears behind a small lightbulb
next to the number — after the learner has answered, never before.

Notes live in `languages/<code>/notes.toml`. **You can add one entirely in your
browser.** No Python, no local setup, no build step.

Related guides:
- [ADD_NUMBERS.md](ADD_NUMBERS.md) — the number lists themselves.
- [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) — full tutorial pages.
- [ADD_UI_LANGUAGE.md](ADD_UI_LANGUAGE.md) — translating the interface.

---

## Walkthrough: add a note

1. Open `languages/<code>/notes.toml` on GitHub — for example
   [`languages/cy/notes.toml`](languages/cy/notes.toml). If your language has no
   file yet, use **Add file → Create new file** and name it
   `languages/<code>/notes.toml`, starting with the two header lines below.
2. Click the pencil (**Edit this file**). GitHub makes your own copy; you cannot
   break the live site.
3. Add a block at the end:

```toml
[[note]]
id = "cy-ugain-after-ar"
applies_to = "20"
systems = ["traditional"]
text = "After ar, ugain becomes hugain, which gives un ar hugain for 21."
source = "r/learnwelsh, August 2026"
reviewed = false

  [[note.examples]]
  phrase = "un ar hugain"
  gloss = "twenty-one"
```

4. Scroll down, describe the change in one line, and choose **Create a new
   branch and start a pull request**.
5. Automated checks confirm the file parses, the numbers exist, the system name
   is real, and the note doesn't give a drill answer away. A maintainer reviews.

That's it. Translating a note is a separate, optional PR — see
[Translations](#translations).

---

## The file

Two header lines, then any number of `[[note]]` blocks:

```toml
language = "cy"        # the language these notes belong to
authored_in = "en"     # the language the note text is written in
```

### Fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique within the file. Lowercase with dashes. Translations refer to it, so don't rename one casually. |
| `text` | yes | The note itself, in plain sentences. |
| `applies_to` | no (default `"all"`) | Which numbers this is about — see below. |
| `systems` | no | Which numeral systems this applies to. Omit for all of them. |
| `examples` | no | `phrase` + optional `gloss` pairs. |
| `source` | no | Where the fact came from: a thread, a grammar, a person. |
| `reviewed` | no (default `false`) | `true` once a native speaker has checked it. |
| `reveals_answer` | no (default `true`) | Whether the note gives a drill answer away — see [The lightbulb rule](#the-lightbulb-rule). |

### `applies_to`

Four shapes, one field:

| Value | Means |
|---|---|
| `"20"` | just the number 20 |
| `"11-19"` | every number from 11 to 19 |
| `"2,3,4"` or `"11-19,30"` | any combination of the two |
| `"all"` | the whole language (or, with `systems`, the whole system) |

A note about a mutation pattern is usually `"all"` plus a `systems` filter. A
note about one irregular word is usually a single number.

### `systems`

Only relevant for a language with more than one numeral system (see
[ADD_NUMBERS.md](ADD_NUMBERS.md#languages-with-more-than-one-numeral-system)).
Welsh has `decimal` and `traditional`:

```toml
systems = ["traditional"]   # only in traditional drills
# omit the field entirely   # in every system
```

A note scoped to a system that isn't live yet simply doesn't appear until it is.
That is fine and expected — write the note when you know the fact.

### `text`

Plain sentences. **No HTML, no Markdown, no links** — a note is rendered as
text, identically everywhere it appears, and the checks reject `<` outright.
This is deliberate: contributors can't break a page, and a note can't quietly
become an advert.

Keep it to one or two sentences. If it needs a paragraph, it wants to be a
section on the Learn page instead ([ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md)).

### `examples`

```toml
  [[note.examples]]
  phrase = "deng munud"     # in the language being learned
  gloss = "ten minutes"     # in the language the note is written in
```

The phrase stays put when a note is translated; only the gloss moves.

---

## The lightbulb rule

**A note is never shown next to a question the learner hasn't answered yet, if
it would give the answer away.**

This is not a detail — it is the reason the notes have a schema at all. If the
drill asks "how do you say 10 in Welsh?" and a lightbulb next to it reads
*"`deg` becomes `deng` before m-"*, the answer is on the screen.

So each note declares `reveals_answer`, and it **defaults to `true`** — the safe
direction to be wrong in. Where a note shows up:

| Where | Which notes |
|---|---|
| Live question, answer still hidden | only notes with `reveals_answer = false` **and** `reviewed = true` |
| After a reveal, and on the results page | all of them |
| Worksheet answer key, Learn pages | all of them |
| Worksheet exercise side | none, ever |

Two checks stand behind this:

- **Mechanical.** If you set `reveals_answer = false` on a note whose text or
  examples contain a word the learner could be asked to produce, CI fails and
  names the word. You cannot mark a leaking note as safe by accident.
- **Human.** The mechanical check only catches a spelled-out answer. It cannot
  catch *"this one is literally two nines"* next to `deunaw`. So an unreviewed
  note stays away from live questions no matter what it declares. Setting
  `reviewed = true` is a maintainer's or native speaker's call, not the note
  author's.

If in doubt, leave both defaults alone. The note still gets shown — just after
the answer, which is when most notes are more useful anyway.

---

## Translations

Notes are written in **one** language and translated **optionally**. Requiring
eight translations per note would mean no notes.

- The authoring language is the file's `authored_in` (usually `en`).
- A translation lives in a sibling file named after the UI language:
  `languages/cy/notes.de.toml`, `languages/cy/notes.fr.toml`, …
- It contains only the `id` and the translated text:

```toml
[[note]]
id = "cy-deg-before-m"
text = "Vor einem Wort, das mit m- beginnt, wird aus deg das Wort deng."

  [[note.examples]]
  phrase = "deng munud"
  gloss = "zehn Minuten"
```

A note with no translation for the reader's language is **shown anyway**, in the
language it was written in, with a small marker saying so. Hiding it would keep
a correct fact from everyone who doesn't read English, which is worse.

---

## What CI checks

`tests/test_notes.py` fails the build if:

1. the file doesn't parse, or a note has no `id` or no `text`;
2. two notes share an `id`;
3. `applies_to` is malformed, or a part of it matches no number the language has
   a word for (ranges only need to overlap the deck — decks are sparse above 100);
4. `systems` names a system the language doesn't declare;
5. a translation file refers to an `id` that doesn't exist;
6. any string contains `<`;
7. `reveals_answer = false` on a note that spells out a scoped answer.

At runtime the loader is deliberately forgiving: a broken notes file costs the
notes and nothing else — the drill keeps working.

---

## Which languages have notes today

`cy`, `de`, `es`, `fr`, `da`. Every one of them is `reviewed = false` and would
benefit from a native speaker's eye. Good candidates for new notes:

- **Korean / Japanese** — the two counting systems and when each is used.
- **Turkish** — vowel harmony in the tens.
- **Chinese** — 二 vs 两, and the financial numerals.
- **Nepali** — the fully irregular 1–100.
- **Irish** — counting vs personal numerals.

## Style

- One fact per note. Two facts about the same number are two notes.
- Say what a learner would get wrong, not what a grammar book would say.
- Name the exception, not the rule — the rule is on the Learn page.
- Write for someone who has just seen this number for the first time.
