# Welsh ordinals — a plan, not a build

Status: **not started.** Written August 2026, after the review round that settled the
41–99 connective. Nothing in this document is implemented.

## Why this is next

Dates are the single biggest surviving use of the traditional system, and dates are
ordinals: *y trydydd ar ddeg o Fai*, *yr unfed ar hugain*, written `13eg`, `21ain`. The
site drills cardinals only. A learner can finish every traditional drill we offer and
still be unable to read a date — the Learn page says so in as many words, which is honest
but not a fix.

The reviewer put it plainly: for 1–31 the ordinals carry more real-world load than the
cardinals. We are drilling the quieter half.

## What makes this different from adding a numeral system

A numeral system answers *"what is the word for 13?"*. Ordinals answer *"what is the word
for 13th?"* — a different question about the same digit. That breaks an assumption that
has held everywhere so far: **the prompt is the number itself**. `13` on a card cannot
mean both `tri ar ddeg` and `y trydydd ar ddeg`.

So the smallest honest version needs one new capability: a deck may say how its prompt is
written. Something like an optional `PROMPTS` map beside `NUMBERS` in a deck module —
`{13: "13eg", 21: "21ain", 1: "1af"}` — with `str(number)` as the default, which is what
all fifteen languages get today with no change. Everything else already exists:

* the numeral-system machinery would carry it (a third entry under `cy`, `module:
  numbers_ordinal`, gated on `requires_complete: (1, 31)`);
* the provenance tiers apply unchanged — an ordinal nobody has confirmed is withheld the
  same way `chwe ugain` is;
* the usage weighting applies unchanged — 1–31 is the whole point, so there is nothing to
  down-weight;
* worksheets, notes and the answer key follow the deck without edits.

The alternative — a separate drill mode with its own routes — buys nothing the prompt
override does not, and would fork the quiz templates. Prefer the small extension.

## What we do not have

The data. Ordinals are **not** safely derivable from the cardinals by rule:

* 1st–3rd are suppletive: `cyntaf`, `ail`, `trydydd`.
* Several are formed with `-fed` / `-ed` on a stem that is not the cardinal
  (`deuddegfed`, `pymthegfed`).
* The compounds put the ordinal on the *unit*: `y trydydd ar ddeg`, not
  `*y tri ar ddegfed`.
* Gender runs through them — `y drydedd ar ddeg` — and dates take a feminine noun
  (*blwyddyn*? *dyddiad*? this is exactly the kind of thing to ask rather than assume).
* The definite article mutates what follows: `y trydydd`, but `yr unfed ar hugain`.

A generator could produce the regular middle of that and would be wrong at both ends,
confidently. So: no generated ordinal deck until speakers or a reference work supply the
irregular spine. Question 9 in `docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md` is the ask.

## Scope for a first version

* **1st–31st only.** That is what dates need; extending later is a data change, not a
  design change.
* **Cardinal prompt, ordinal answer.** The card shows `13eg` and expects
  `y trydydd ar ddeg`. Whether the article belongs in the expected answer is an open
  question — it is how the form is actually used, but it makes the answer longer to type
  and the validator would need to accept both.
* **Masculine by default**, feminine stored, exactly as the cardinals do now.
* **Not in scope**: reading a whole date (`yr ail ar hugain o fis Medi`). That is a
  sentence drill, not a number drill, and it needs the months too.

## Order of work

1. Ask (question 9 of the review round). Nothing below can start honestly without it.
2. `PROMPTS` support in the deck loader + the quiz templates, defaulted so no other
   language notices. Test: a language without it renders exactly as before.
3. `languages/cy/numbers_ordinal.py` with provenance per form, gated at `(1, 31)`.
4. Learn page section, and delete the paragraph saying we do not do ordinals.
5. Notes: the article mutation (`y` vs `yr`) is a good lightbulb, and it is the kind of
   thing that reveals the answer, so it needs `reveals_answer = true`.
