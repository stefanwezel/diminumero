# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Generate the global English verb-conjugation pool used by the Conjugation quiz.

verbecc has no English support, so this is a small self-contained engine like
the German one: regular verbs are built by rule (the -s, -ed and -ing spelling
rules), and every irregular verb carries its past and participle in IRREGULAR.

The JSON shape matches the other pools, with one difference: each tense maps to
a **5-element** list aligned to [I, you, he/she/it, we, they]. English "you" has
one form for one person and for several, so a sixth slot would only ask the same
question twice. A slot is null when the form isn't used:

    - stative verbs (STATIVE_VERBS) have no continuous tenses: "I know", never
      "I am knowing";
    - modals (DEFECTIVE) only exist in the tenses listed for them.

The deck is British, like the English number deck: "travelled", "realise",
"have got". American-only forms ("traveled", "gotten") are deliberately marked
wrong. Where British usage itself accepts two forms ("learnt"/"learned"), the
pool stores one and the rest go to conjugation_variants.json:

    { "learn": { "past-simple": { "learnt": ["learned"] }, ... }, ... }

which the practice check consults alongside the stored form.

Usage:
    uv run tools/generate_conjugations_en.py            # generate everything
    uv run tools/generate_conjugations_en.py --limit 20 # print the first 20, write nothing
"""

import argparse
import json
import re
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "languages" / "en"
OUTPUT_PATH = OUTPUT_DIR / "conjugations.json"
VARIANTS_PATH = OUTPUT_DIR / "conjugation_variants.json"

TENSES = [
    "present-simple",
    "past-simple",
    "present-continuous",
    "present-perfect",
    "future-will",
    "past-continuous",
    "future-going-to",
    "conditional",
    "past-perfect",
    "present-perfect-continuous",
]

CONTINUOUS_TENSES = (
    "present-continuous",
    "past-continuous",
    "present-perfect-continuous",
)

NO_FORMS = [None] * 5

BE_PRESENT = ["am", "are", "is", "are", "are"]
BE_PAST = ["was", "were", "was", "were", "were"]
HAVE_PRESENT = ["have", "have", "has", "have", "have"]

# Frequency-ranked pool. Order is preserved in the JSON so autocomplete ranks
# common verbs first. A verb missing from IRREGULAR is conjugated as regular.
POPULAR_VERBS = [
    "be",
    "have",
    "do",
    "say",
    "go",
    "can",
    "get",
    "make",
    "know",
    "think",
    "take",
    "see",
    "come",
    "want",
    "look",
    "use",
    "find",
    "give",
    "tell",
    "work",
    "may",
    "call",
    "try",
    "ask",
    "need",
    "feel",
    "become",
    "leave",
    "put",
    "mean",
    "keep",
    "let",
    "begin",
    "seem",
    "help",
    "talk",
    "turn",
    "start",
    "must",
    "show",
    "hear",
    "play",
    "run",
    "move",
    "like",
    "live",
    "believe",
    "hold",
    "bring",
    "happen",
    "write",
    "provide",
    "sit",
    "stand",
    "lose",
    "pay",
    "meet",
    "include",
    "continue",
    "set",
    "learn",
    "change",
    "lead",
    "understand",
    "watch",
    "follow",
    "stop",
    "create",
    "speak",
    "read",
    "allow",
    "add",
    "spend",
    "grow",
    "open",
    "walk",
    "win",
    "offer",
    "remember",
    "love",
    "consider",
    "appear",
    "buy",
    "wait",
    "serve",
    "die",
    "send",
    "expect",
    "build",
    "stay",
    "fall",
    "cut",
    "reach",
    "kill",
    "remain",
    "suggest",
    "raise",
    "pass",
    "sell",
    "require",
    "report",
    "decide",
    "pull",
    "return",
    "explain",
    "hope",
    "develop",
    "carry",
    "break",
    "receive",
    "agree",
    "support",
    "hit",
    "produce",
    "eat",
    "cover",
    "catch",
    "draw",
    "choose",
    "cause",
    "point",
    "listen",
    "realise",
    "place",
    "close",
    "involve",
    "increase",
    "thank",
    "pick",
    "wear",
    "drive",
    "lie",
    "teach",
    "throw",
    "apply",
    "join",
    "save",
    "fight",
    "share",
    "finish",
    "enjoy",
    "protect",
    "forget",
    "visit",
    "study",
    "describe",
    "reduce",
    "sleep",
    "drink",
    "sing",
    "plan",
    "imagine",
    "prepare",
    "improve",
    "wish",
    "smile",
    "laugh",
    "cook",
    "clean",
    "travel",
    "answer",
    "arrive",
    "dance",
    "cry",
    "worry",
    "hate",
    "own",
    "miss",
    "prefer",
    "accept",
    "achieve",
    "act",
    "admit",
    "advise",
    "affect",
    "aim",
    "announce",
    "argue",
    "arrange",
    "assume",
    "attack",
    "attend",
    "avoid",
    "bake",
    "bear",
    "beat",
    "bend",
    "bet",
    "bite",
    "bleed",
    "blow",
    "boil",
    "book",
    "borrow",
    "bother",
    "brush",
    "burn",
    "burst",
    "care",
    "cast",
    "celebrate",
    "charge",
    "chat",
    "check",
    "claim",
    "climb",
    "collect",
    "commit",
    "compare",
    "complain",
    "complete",
    "confirm",
    "connect",
    "contain",
    "control",
    "copy",
    "cost",
    "count",
    "crash",
    "cross",
    "damage",
    "deal",
    "defend",
    "deliver",
    "demand",
    "deny",
    "depend",
    "deserve",
    "design",
    "destroy",
    "determine",
    "dig",
    "disappear",
    "discover",
    "discuss",
    "divide",
    "doubt",
    "download",
    "dream",
    "dress",
    "drop",
    "dry",
    "earn",
    "encourage",
    "enter",
    "establish",
    "examine",
    "exist",
    "expand",
    "experience",
    "express",
    "extend",
    "fail",
    "feed",
    "fill",
    "fit",
    "fix",
    "flee",
    "flow",
    "fly",
    "focus",
    "fold",
    "force",
    "forgive",
    "freeze",
    "gain",
    "gather",
    "guess",
    "handle",
    "hang",
    "hide",
    "hire",
    "hug",
    "hunt",
    "hurry",
    "hurt",
    "identify",
    "ignore",
    "influence",
    "inform",
    "insist",
    "install",
    "intend",
    "introduce",
    "invent",
    "invest",
    "invite",
    "jump",
    "kick",
    "kiss",
    "kneel",
    "knock",
    "lack",
    "land",
    "last",
    "lay",
    "lean",
    "leap",
    "lend",
    "lift",
    "light",
    "limit",
    "link",
    "lock",
    "manage",
    "mark",
    "marry",
    "match",
    "matter",
    "measure",
    "melt",
    "mention",
    "mind",
    "mix",
    "notice",
    "obtain",
    "occur",
    "order",
    "organise",
    "owe",
    "paint",
    "park",
    "perform",
    "permit",
    "persuade",
    "plant",
    "pour",
    "practise",
    "pray",
    "predict",
    "press",
    "pretend",
    "prevent",
    "print",
    "promise",
    "prove",
    "publish",
    "push",
    "quit",
    "recognise",
    "recommend",
    "record",
    "refer",
    "reflect",
    "refuse",
    "regret",
    "relax",
    "release",
    "rely",
    "rent",
    "repair",
    "repeat",
    "replace",
    "reply",
    "represent",
    "request",
    "rescue",
    "resemble",
    "respect",
    "respond",
    "rest",
    "reveal",
    "ride",
    "ring",
    "rise",
    "rob",
    "roll",
    "rub",
    "rush",
    "satisfy",
    "score",
    "search",
    "seek",
    "select",
    "shake",
    "shape",
    "shine",
    "shoot",
    "shop",
    "shout",
    "shut",
    "sign",
    "sink",
    "ski",
    "slide",
    "slip",
    "smell",
    "smoke",
    "solve",
    "sort",
    "sound",
    "spell",
    "spill",
    "spin",
    "spit",
    "split",
    "spoil",
    "spread",
    "stare",
    "steal",
    "stick",
    "stir",
    "store",
    "strike",
    "struggle",
    "succeed",
    "suffer",
    "supply",
    "suppose",
    "surprise",
    "surround",
    "survive",
    "swear",
    "sweep",
    "swim",
    "swing",
    "switch",
    "taste",
    "tear",
    "test",
    "tie",
    "touch",
    "train",
    "transfer",
    "translate",
    "treat",
    "trust",
    "type",
    "upset",
    "vote",
    "wake",
    "warn",
    "wash",
    "waste",
    "wave",
    "weigh",
    "welcome",
    "whisper",
    "wipe",
    "wonder",
    "wrap",
    "analyse",
    "apologise",
    "arise",
    "awake",
    "belong",
    "bind",
    "breed",
    "broadcast",
    "cancel",
    "cling",
    "consist",
    "creep",
    "criticise",
    "emphasise",
    "enrol",
    "exercise",
    "forbid",
    "forecast",
    "fulfil",
    "grind",
    "label",
    "memorise",
    "mislead",
    "misunderstand",
    "overcome",
    "overtake",
    "panic",
    "possess",
    "rebuild",
    "repay",
    "rewrite",
    "sew",
    "shrink",
    "signal",
    "spring",
    "sting",
    "stink",
    "summarise",
    "tread",
    "undergo",
    "undertake",
    "undo",
    "weep",
    "wind",
    "withdraw",
]

# verb -> (past simple, past participle). British forms.
IRREGULAR = {
    "arise": ("arose", "arisen"),
    "awake": ("awoke", "awoken"),
    "be": ("was", "been"),
    "bear": ("bore", "borne"),
    "beat": ("beat", "beaten"),
    "become": ("became", "become"),
    "begin": ("began", "begun"),
    "bend": ("bent", "bent"),
    "bet": ("bet", "bet"),
    "bind": ("bound", "bound"),
    "bite": ("bit", "bitten"),
    "bleed": ("bled", "bled"),
    "blow": ("blew", "blown"),
    "break": ("broke", "broken"),
    "breed": ("bred", "bred"),
    "bring": ("brought", "brought"),
    "broadcast": ("broadcast", "broadcast"),
    "build": ("built", "built"),
    "burn": ("burnt", "burnt"),
    "burst": ("burst", "burst"),
    "buy": ("bought", "bought"),
    "cast": ("cast", "cast"),
    "catch": ("caught", "caught"),
    "choose": ("chose", "chosen"),
    "cling": ("clung", "clung"),
    "come": ("came", "come"),
    "cost": ("cost", "cost"),
    "creep": ("crept", "crept"),
    "cut": ("cut", "cut"),
    "deal": ("dealt", "dealt"),
    "dig": ("dug", "dug"),
    "do": ("did", "done"),
    "draw": ("drew", "drawn"),
    "dream": ("dreamt", "dreamt"),
    "drink": ("drank", "drunk"),
    "drive": ("drove", "driven"),
    "eat": ("ate", "eaten"),
    "fall": ("fell", "fallen"),
    "feed": ("fed", "fed"),
    "feel": ("felt", "felt"),
    "fight": ("fought", "fought"),
    "find": ("found", "found"),
    "flee": ("fled", "fled"),
    "fly": ("flew", "flown"),
    "forbid": ("forbade", "forbidden"),
    "forecast": ("forecast", "forecast"),
    "forget": ("forgot", "forgotten"),
    "forgive": ("forgave", "forgiven"),
    "freeze": ("froze", "frozen"),
    "get": ("got", "got"),
    "give": ("gave", "given"),
    "go": ("went", "gone"),
    "grind": ("ground", "ground"),
    "grow": ("grew", "grown"),
    "hang": ("hung", "hung"),
    "have": ("had", "had"),
    "hear": ("heard", "heard"),
    "hide": ("hid", "hidden"),
    "hit": ("hit", "hit"),
    "hold": ("held", "held"),
    "hurt": ("hurt", "hurt"),
    "keep": ("kept", "kept"),
    "kneel": ("knelt", "knelt"),
    "know": ("knew", "known"),
    "lay": ("laid", "laid"),
    "lead": ("led", "led"),
    "lean": ("leant", "leant"),
    "leap": ("leapt", "leapt"),
    "learn": ("learnt", "learnt"),
    "leave": ("left", "left"),
    "lend": ("lent", "lent"),
    "let": ("let", "let"),
    "lie": ("lay", "lain"),
    "light": ("lit", "lit"),
    "lose": ("lost", "lost"),
    "make": ("made", "made"),
    "mean": ("meant", "meant"),
    "meet": ("met", "met"),
    "mislead": ("misled", "misled"),
    "misunderstand": ("misunderstood", "misunderstood"),
    "overcome": ("overcame", "overcome"),
    "overtake": ("overtook", "overtaken"),
    "pay": ("paid", "paid"),
    "put": ("put", "put"),
    "quit": ("quit", "quit"),
    "read": ("read", "read"),
    "rebuild": ("rebuilt", "rebuilt"),
    "repay": ("repaid", "repaid"),
    "rewrite": ("rewrote", "rewritten"),
    "ride": ("rode", "ridden"),
    "ring": ("rang", "rung"),
    "rise": ("rose", "risen"),
    "run": ("ran", "run"),
    "say": ("said", "said"),
    "see": ("saw", "seen"),
    "seek": ("sought", "sought"),
    "sell": ("sold", "sold"),
    "send": ("sent", "sent"),
    "set": ("set", "set"),
    "sew": ("sewed", "sewn"),
    "shake": ("shook", "shaken"),
    "shine": ("shone", "shone"),
    "shoot": ("shot", "shot"),
    "show": ("showed", "shown"),
    "shrink": ("shrank", "shrunk"),
    "shut": ("shut", "shut"),
    "sing": ("sang", "sung"),
    "sink": ("sank", "sunk"),
    "sit": ("sat", "sat"),
    "sleep": ("slept", "slept"),
    "slide": ("slid", "slid"),
    "smell": ("smelt", "smelt"),
    "speak": ("spoke", "spoken"),
    "spell": ("spelt", "spelt"),
    "spend": ("spent", "spent"),
    "spill": ("spilt", "spilt"),
    "spin": ("spun", "spun"),
    "spit": ("spat", "spat"),
    "split": ("split", "split"),
    "spoil": ("spoilt", "spoilt"),
    "spread": ("spread", "spread"),
    "spring": ("sprang", "sprung"),
    "stand": ("stood", "stood"),
    "steal": ("stole", "stolen"),
    "stick": ("stuck", "stuck"),
    "sting": ("stung", "stung"),
    "stink": ("stank", "stunk"),
    "strike": ("struck", "struck"),
    "swear": ("swore", "sworn"),
    "sweep": ("swept", "swept"),
    "swim": ("swam", "swum"),
    "swing": ("swung", "swung"),
    "take": ("took", "taken"),
    "teach": ("taught", "taught"),
    "tear": ("tore", "torn"),
    "tell": ("told", "told"),
    "think": ("thought", "thought"),
    "throw": ("threw", "thrown"),
    "tread": ("trod", "trodden"),
    "undergo": ("underwent", "undergone"),
    "understand": ("understood", "understood"),
    "undertake": ("undertook", "undertaken"),
    "undo": ("undid", "undone"),
    "upset": ("upset", "upset"),
    "wake": ("woke", "woken"),
    "wear": ("wore", "worn"),
    "weep": ("wept", "wept"),
    "win": ("won", "won"),
    "wind": ("wound", "wound"),
    "withdraw": ("withdrew", "withdrawn"),
    "write": ("wrote", "written"),
}

# Other (past, participle[, -ing]) forms British usage accepts. Stored as answer
# variants, never as the displayed form. "lie" is two verbs in one spelling,
# and the drill can't say which is meant, so both count.
ALTERNATE_PARTS = {
    "bet": [("betted", "betted")],
    "broadcast": [("broadcasted", "broadcasted")],
    "burn": [("burned", "burned")],
    "dream": [("dreamed", "dreamed")],
    "focus": [("focussed", "focussed", "focussing")],
    "forecast": [("forecasted", "forecasted")],
    "hang": [("hanged", "hanged")],
    "kneel": [("kneeled", "kneeled")],
    "lean": [("leaned", "leaned")],
    "leap": [("leaped", "leaped")],
    "learn": [("learned", "learned")],
    "lie": [("lied", "lied")],
    "light": [("lighted", "lighted")],
    "prove": [("proved", "proven")],
    "quit": [("quitted", "quitted")],
    "sew": [("sewed", "sewed")],
    "shine": [("shined", "shined")],
    "show": [("showed", "showed")],
    "smell": [("smelled", "smelled")],
    "spell": [("spelled", "spelled")],
    "spill": [("spilled", "spilled")],
    "spoil": [("spoiled", "spoiled")],
}

# -ise verbs that British (Oxford) spelling also writes with -ize. Not "advise",
# "exercise", "promise", "raise" or "surprise", which are -ise everywhere, and
# not "analyse": "analyze" is American only.
IZE_VERBS = {
    "apologise",
    "criticise",
    "emphasise",
    "memorise",
    "organise",
    "realise",
    "recognise",
    "summarise",
}

# Verbs of state: not normally used in the continuous, so the drill must not
# ask for "am knowing". Deliberately conservative. Verbs with a common dynamic
# sense ("I'm having lunch", "I'm thinking", "I'm seeing her") stay in.
STATIVE_VERBS = {
    "agree",
    "believe",
    "belong",
    "consist",
    "contain",
    "depend",
    "deserve",
    "doubt",
    "exist",
    "hate",
    "include",
    "involve",
    "know",
    "like",
    "love",
    "matter",
    "mean",
    "need",
    "owe",
    "own",
    "possess",
    "prefer",
    "realise",
    "recognise",
    "remember",
    "resemble",
    "seem",
    "suppose",
    "understand",
    "want",
}

# Modals have no -s, no participle and no -ing: only these tenses exist.
DEFECTIVE = {
    "can": {"present-simple": "can", "past-simple": "could", "conditional": "could"},
    "may": {"present-simple": "may", "conditional": "might"},
    "must": {"present-simple": "must"},
}

# Longer verbs that double their final consonant. Stress can't be read off the
# spelling (admit → admitted, visit → visited), so these are listed. The final
# -l ones double because British English always does, stressed or not.
DOUBLE_FINAL = {
    "admit",
    "begin",
    "cancel",
    "commit",
    "control",
    "enrol",
    "forbid",
    "forget",
    "fulfil",
    "label",
    "occur",
    "permit",
    "prefer",
    "refer",
    "regret",
    "signal",
    "transfer",
    "travel",
    "upset",
}


def doubles_final(verb: str) -> bool:
    """True when -ed/-ing double the final consonant (stop → stopped).

    One-syllable verbs follow the consonant + single vowel + consonant rule,
    except that w, x and y never double (show, fix, play).
    """
    return (
        verb in DOUBLE_FINAL
        or re.fullmatch(r"(?:qu|[^aeiou]*)[aeiou][^aeiouwxy]", verb) is not None
    )


def ends_in_consonant_y(verb: str) -> bool:
    return verb.endswith("y") and verb[-2] not in "aeiou"


def third_person(verb: str) -> str:
    if verb.endswith(("s", "x", "z", "ch", "sh", "o")):
        return verb + "es"
    if ends_in_consonant_y(verb):
        return verb[:-1] + "ies"
    return verb + "s"


def regular_past(verb: str) -> str:
    if verb.endswith("e"):
        return verb + "d"
    if ends_in_consonant_y(verb):
        return verb[:-1] + "ied"
    if verb.endswith("c"):
        return verb + "ked"
    if doubles_final(verb):
        return verb + verb[-1] + "ed"
    return verb + "ed"


def ing_form(verb: str) -> str:
    if verb == "be":
        return "being"
    if verb.endswith("ie"):
        return verb[:-2] + "ying"
    if verb.endswith("e") and not verb.endswith(("ee", "oe", "ye")):
        return verb[:-1] + "ing"
    if verb.endswith("c"):
        return verb + "king"
    if doubles_final(verb):
        return verb + verb[-1] + "ing"
    return verb + "ing"


def conjugate(
    verb: str,
    past: str | None = None,
    participle: str | None = None,
    ing: str | None = None,
) -> dict[str, list]:
    """Full tense→forms map for one verb.

    ``past``/``participle``/``ing`` override the verb's principal parts, which
    is how the answer variants are built.
    """
    if verb in DEFECTIVE:
        cells = DEFECTIVE[verb]
        return {t: [cells[t]] * 5 if t in cells else list(NO_FORMS) for t in TENSES}

    if past is None:
        regular = regular_past(verb)
        past, participle = IRREGULAR.get(verb, (regular, regular))
    ing = ing or ing_form(verb)
    forms = {
        "present-simple": (
            BE_PRESENT
            if verb == "be"
            else HAVE_PRESENT
            if verb == "have"
            else [verb, verb, third_person(verb), verb, verb]
        ),
        "past-simple": BE_PAST if verb == "be" else [past] * 5,
        "present-continuous": [f"{a} {ing}" for a in BE_PRESENT],
        "present-perfect": [f"{a} {participle}" for a in HAVE_PRESENT],
        "future-will": [f"will {verb}"] * 5,
        "past-continuous": [f"{a} {ing}" for a in BE_PAST],
        "future-going-to": [f"{a} going to {verb}" for a in BE_PRESENT],
        "conditional": [f"would {verb}"] * 5,
        "past-perfect": [f"had {participle}"] * 5,
        "present-perfect-continuous": [f"{a} been {ing}" for a in HAVE_PRESENT],
    }
    if verb in STATIVE_VERBS:
        for tense in CONTINUOUS_TENSES:
            forms[tense] = list(NO_FORMS)
    if verb == "be":
        # Grammatical on paper, but nobody says "have been being".
        forms["present-perfect-continuous"] = list(NO_FORMS)
    return {t: list(forms[t]) for t in TENSES}


def form_variants(verb: str) -> dict[str, dict[str, list[str]]]:
    """{tense: {stored form: [other accepted forms]}} for one verb."""
    alternates = [conjugate(verb, *parts) for parts in ALTERNATE_PARTS.get(verb, [])]
    if verb in IZE_VERBS:
        alternates.append(conjugate(verb[:-3] + "ize"))
    stored_forms = conjugate(verb)
    out: dict[str, dict[str, list[str]]] = {}
    for alternate in alternates:
        for tense in TENSES:
            for stored, other in zip(stored_forms[tense], alternate[tense]):
                if stored is None or other == stored:
                    continue
                accepted = out.setdefault(tense, {}).setdefault(stored, [])
                if other not in accepted:
                    accepted.append(other)
    return out


# Spot checks against known-good paradigms; a wrong engine rule fails loudly
# instead of silently committing bad data.
EXPECTED = {
    ("be", "present-simple"): ["am", "are", "is", "are", "are"],
    ("be", "past-simple"): ["was", "were", "was", "were", "were"],
    ("be", "present-continuous", 2): "is being",
    ("be", "present-perfect", 2): "has been",
    ("be", "present-perfect-continuous", 0): None,
    ("have", "present-simple"): ["have", "have", "has", "have", "have"],
    ("have", "present-perfect", 0): "have had",
    ("have", "present-continuous", 0): "am having",
    ("do", "present-simple", 2): "does",
    ("do", "present-perfect", 2): "has done",
    ("go", "present-simple", 2): "goes",
    ("go", "past-simple", 0): "went",
    ("go", "present-perfect", 0): "have gone",
    ("go", "past-perfect", 4): "had gone",
    ("go", "future-going-to", 2): "is going to go",
    ("get", "present-perfect", 0): "have got",
    ("say", "present-simple", 2): "says",
    ("say", "past-simple", 0): "said",
    ("pay", "past-simple", 0): "paid",
    ("work", "present-simple"): ["work", "work", "works", "work", "work"],
    ("work", "past-simple", 2): "worked",
    ("work", "present-continuous"): [
        "am working",
        "are working",
        "is working",
        "are working",
        "are working",
    ],
    ("work", "past-continuous"): [
        "was working",
        "were working",
        "was working",
        "were working",
        "were working",
    ],
    ("work", "present-perfect-continuous", 2): "has been working",
    ("work", "future-will", 0): "will work",
    ("work", "conditional", 0): "would work",
    # -s spelling
    ("watch", "present-simple", 2): "watches",
    ("wash", "present-simple", 2): "washes",
    ("fix", "present-simple", 2): "fixes",
    ("pass", "present-simple", 2): "passes",
    ("focus", "present-simple", 2): "focuses",
    ("study", "present-simple", 2): "studies",
    ("fly", "present-simple", 2): "flies",
    ("play", "present-simple", 2): "plays",
    ("enjoy", "present-simple", 2): "enjoys",
    ("ski", "present-simple", 2): "skis",
    # -ed spelling
    ("like", "past-simple", 0): "liked",
    ("agree", "past-simple", 0): "agreed",
    ("die", "past-simple", 0): "died",
    ("study", "past-simple", 0): "studied",
    ("play", "past-simple", 0): "played",
    ("stop", "past-simple", 0): "stopped",
    ("plan", "past-simple", 0): "planned",
    ("fix", "past-simple", 0): "fixed",
    ("fit", "past-simple", 0): "fitted",
    ("ski", "past-simple", 0): "skied",
    ("panic", "past-simple", 0): "panicked",
    ("admit", "past-simple", 0): "admitted",
    ("prefer", "past-simple", 0): "preferred",
    ("visit", "past-simple", 0): "visited",
    ("offer", "past-simple", 0): "offered",
    ("open", "past-simple", 0): "opened",
    ("develop", "past-simple", 0): "developed",
    ("focus", "past-simple", 0): "focused",
    # British final -l
    ("travel", "past-simple", 0): "travelled",
    ("cancel", "past-simple", 0): "cancelled",
    ("label", "past-simple", 0): "labelled",
    ("signal", "past-simple", 0): "signalled",
    ("control", "past-simple", 0): "controlled",
    ("enrol", "present-simple", 2): "enrols",
    ("enrol", "past-simple", 0): "enrolled",
    ("fulfil", "past-simple", 0): "fulfilled",
    ("reveal", "past-simple", 0): "revealed",
    ("install", "past-simple", 0): "installed",
    # -ing spelling
    ("make", "present-continuous", 0): "am making",
    ("see", "present-continuous", 0): "am seeing",
    ("flee", "present-continuous", 0): "am fleeing",
    ("die", "present-continuous", 0): "am dying",
    ("lie", "present-continuous", 0): "am lying",
    ("tie", "present-continuous", 0): "am tying",
    ("stop", "present-continuous", 0): "am stopping",
    ("run", "present-continuous", 0): "am running",
    ("put", "present-continuous", 0): "am putting",
    ("quit", "present-continuous", 0): "am quitting",
    ("begin", "present-continuous", 0): "am beginning",
    ("forget", "present-continuous", 0): "am forgetting",
    ("travel", "present-continuous", 0): "am travelling",
    ("visit", "present-continuous", 0): "am visiting",
    ("show", "present-continuous", 0): "am showing",
    ("fix", "present-continuous", 0): "am fixing",
    ("play", "present-continuous", 0): "am playing",
    ("ski", "present-continuous", 0): "am skiing",
    ("panic", "present-continuous", 0): "am panicking",
    # Irregular shapes
    ("put", "past-simple", 0): "put",
    ("put", "present-perfect", 0): "have put",
    ("come", "present-perfect", 0): "have come",
    ("run", "present-perfect", 0): "have run",
    ("write", "past-simple", 0): "wrote",
    ("write", "present-perfect", 0): "have written",
    ("buy", "past-simple", 0): "bought",
    ("read", "past-simple", 0): "read",
    ("lie", "past-simple", 0): "lay",
    ("lie", "present-perfect", 0): "have lain",
    ("lay", "past-simple", 0): "laid",
    ("show", "present-perfect", 0): "have shown",
    ("prove", "present-perfect", 0): "have proved",
    # Stative verbs have no continuous; everything else stays.
    ("know", "present-continuous"): [None] * 5,
    ("know", "past-continuous"): [None] * 5,
    ("know", "present-perfect-continuous"): [None] * 5,
    ("know", "present-simple", 2): "knows",
    ("know", "present-perfect", 0): "have known",
    ("want", "present-continuous", 0): None,
    ("think", "present-continuous", 0): "am thinking",
    # Modals
    ("can", "present-simple"): ["can"] * 5,
    ("can", "past-simple", 2): "could",
    ("can", "conditional", 0): "could",
    ("can", "present-perfect", 0): None,
    ("can", "future-will", 0): None,
    ("may", "conditional", 0): "might",
    ("must", "present-simple", 2): "must",
    ("must", "past-simple", 0): None,
}


def run_self_checks(pool: dict[str, dict[str, list]]) -> None:
    failures = []
    for key, expected in EXPECTED.items():
        verb, tense = key[0], key[1]
        forms = pool.get(verb, {}).get(tense)
        if forms is None:
            failures.append(f"{verb} {tense}: missing")
            continue
        if len(key) == 3:
            actual = forms[key[2]]
            if actual != expected:
                failures.append(f"{verb} {tense}[{key[2]}]: {actual!r} != {expected!r}")
        elif forms != expected:
            failures.append(f"{verb} {tense}: {forms!r} != {expected!r}")
    for verb, tenses in pool.items():
        for tense, forms in tenses.items():
            if len(forms) != 5:
                failures.append(f"{verb} {tense}: {len(forms)} slots, not 5")
    for name, group in (
        ("IRREGULAR", IRREGULAR),
        ("ALTERNATE_PARTS", ALTERNATE_PARTS),
        ("IZE_VERBS", IZE_VERBS),
        ("STATIVE_VERBS", STATIVE_VERBS),
        ("DEFECTIVE", DEFECTIVE),
        ("DOUBLE_FINAL", DOUBLE_FINAL),
    ):
        for verb in group:
            if verb not in pool:
                failures.append(f"{name} lists {verb}, which isn't in the pool")
    if failures:
        print("Self-checks FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        sys.exit(1)
    print(f"Self-checks passed ({len(EXPECTED)} known forms verified).")


def build_pool(verbs: list[str]) -> dict[str, dict[str, list]]:
    return {verb: conjugate(verb) for verb in verbs}


def build_variants(verbs: list[str]) -> dict[str, dict[str, dict[str, list[str]]]]:
    return {verb: v for verb in verbs if (v := form_variants(verb))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        help="print the first N verbs instead of writing the committed files",
    )
    args = parser.parse_args()

    verbs = POPULAR_VERBS[: args.limit] if args.limit else POPULAR_VERBS
    dupes = {v for v in verbs if verbs.count(v) > 1}
    if dupes:
        print(f"Duplicate verbs in POPULAR_VERBS: {sorted(dupes)}", file=sys.stderr)
        sys.exit(1)

    pool = build_pool(verbs)
    if args.limit:
        # A quick look only: the app reads these files, so a truncated pool on
        # disk would reject most verbs as unsupported.
        print(json.dumps(pool, ensure_ascii=False, indent=1))
        return
    run_self_checks(pool)

    for path, data in (
        (OUTPUT_PATH, pool),
        (VARIANTS_PATH, build_variants(verbs)),
    ):
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print(f"Wrote {len(data)} verbs to {path}")


if __name__ == "__main__":
    main()
