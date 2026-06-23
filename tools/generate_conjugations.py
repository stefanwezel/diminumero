# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "verbecc",
# ]
# ///
"""
Generate the global Spanish verb-conjugation pool used by the Conjugation quiz.

For each verb in POPULAR_VERBS (a frequency-ranked list of common Spanish verbs)
this conjugates it with the `verbecc` library and writes the bare conjugated
forms for the curated set of useful tenses to languages/es/conjugations.json.

verbecc is deterministic and template-based for known verbs (the ML model is only
a fallback for verbs it has never seen), so the output is accurate. verbecc is a
GENERATION-ONLY dependency — it is intentionally NOT in pyproject.toml. The web app
reads the committed JSON and never imports verbecc.

The JSON shape is:

    {
      "comer": {
        "indicativo/presente": ["como", "comes", "come", "comemos", "coméis", "comen"],
        ...
      },
      ...
    }

Each tense maps to a 6-element list aligned to the canonical persons
[yo, tú, él/ella/usted, nosotros, vosotros, ellos/ellas/ustedes]. A slot is null
when the tense has no form for that person (e.g. imperativo afirmativo has no "yo").

Usage:
    uv run tools/generate_conjugations.py            # generate everything
    uv run tools/generate_conjugations.py --limit 20 # quick test on first 20 verbs
"""

import argparse
import json
import sys
from pathlib import Path

import copy

from verbecc import CompleteConjugator
from verbecc.src.inflectors.lang.inflector_es import InflectorEs

# verbecc 1.x has a bug in its voseo ("vos") ending logic: for some verb
# templates the second-person-plural ending is shorter than two characters and
# `ending[-2]` raises IndexError, which aborts conjugation of the whole verb
# (e.g. "pasar", "resultar"). We never read the "vos" form — we only use
# yo/tú/él/nosotros/vosotros/ellos — so we disable the voseo transformation
# entirely by returning the person ending unmodified for "vos".
_orig_modify = InflectorEs.modify_person_ending_if_applicable


def _safe_modify(self, person_ending, mood, tense, tense_template, pronoun):
    if pronoun == "vos":
        # Return an isolated deepcopy (never the shared template ending) so the
        # downstream string-building step can't mutate the real template in place
        # and wipe the other persons' endings for this verb.
        return copy.deepcopy(person_ending)
    return _orig_modify(self, person_ending, mood, tense, tense_template, pronoun)


InflectorEs.modify_person_ending_if_applicable = _safe_modify

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "languages" / "es" / "conjugations.json"

# Curated tenses we generate, keyed as "<mood>/<tense>" exactly as verbecc emits
# them. Order here is irrelevant (the app's conjugation_config defines display
# order); this is just the set we extract.
TENSES = [
    "indicativo/presente",
    "indicativo/pretérito-perfecto-simple",
    "indicativo/pretérito-imperfecto",
    "indicativo/futuro",
    "condicional/presente",
    "indicativo/pretérito-perfecto-compuesto",
    "subjuntivo/presente",
    "subjuntivo/pretérito-imperfecto-1",
    "indicativo/pretérito-pluscuamperfecto",
    "imperativo/afirmativo",
]

# Canonical pronoun for each of the 6 person slots. The conjugated form for
# él/ella/usted is identical, as is ellos/ellas/ustedes, so we read one
# representative pronoun per slot.
CANONICAL_PRONOUNS = ["yo", "tú", "él", "nosotros", "vosotros", "ellos"]

# Frequency-ranked list of common Spanish verbs (infinitives). Verbs not found
# in verbecc's database are skipped and reported at the end.
POPULAR_VERBS = [
    "ser", "estar", "tener", "hacer", "poder", "decir", "ir", "ver", "dar",
    "saber", "querer", "llegar", "pasar", "deber", "poner", "parecer", "quedar",
    "creer", "hablar", "llevar", "dejar", "seguir", "encontrar", "llamar",
    "venir", "pensar", "salir", "volver", "tomar", "conocer", "vivir", "sentir",
    "tratar", "mirar", "contar", "empezar", "esperar", "buscar", "existir",
    "entrar", "trabajar", "escribir", "perder", "producir", "ocurrir", "entender",
    "pedir", "recibir", "recordar", "terminar", "permitir", "aparecer", "conseguir",
    "comenzar", "servir", "sacar", "necesitar", "mantener", "resultar", "leer",
    "caer", "cambiar", "presentar", "crear", "abrir", "considerar", "oir",
    "acabar", "convertir", "ganar", "formar", "traer", "partir", "morir",
    "aceptar", "realizar", "suponer", "comprender", "lograr", "explicar",
    "preguntar", "tocar", "reconocer", "estudiar", "alcanzar", "nacer", "dirigir",
    "correr", "utilizar", "pagar", "ayudar", "gustar", "jugar", "escuchar",
    "cumplir", "ofrecer", "descubrir", "levantar", "intentar", "usar", "decidir",
    "repetir", "olvidar", "valer", "comer", "subir", "evitar", "señalar",
    "obtener", "asegurar", "andar", "comprar", "elegir", "vender", "responder",
    "soler", "cubrir", "marcar", "indicar", "comentar", "imaginar", "obligar",
    "observar", "mostrar", "demostrar", "actuar", "preparar", "determinar",
    "iniciar", "guardar", "soltar", "depender", "romper", "importar", "preferir",
    "presentir", "ofender", "acompañar", "matar", "aprender", "conducir",
    "compartir", "abandonar", "establecer", "aumentar", "regresar", "construir",
    "depositar", "defender", "describir", "sufrir", "desarrollar", "extender",
    "responsabilizar", "abrazar", "acercar", "aprovechar", "asistir", "atender",
    "atravesar", "avanzar", "bajar", "bastar", "beber", "besar", "bailar",
    "caminar", "cantar", "casar", "cerrar", "cocinar", "coger", "colocar",
    "comprobar", "concluir", "conducirse", "confiar", "confirmar", "conformar",
    "confundir", "conservar", "consistir", "constituir", "consumir", "contener",
    "continuar", "contribuir", "controlar", "convencer", "corresponder",
    "costar", "crecer", "criar", "cruzar", "cuidar", "curar", "dañar",
    "deber", "definir", "depender", "derivar", "desaparecer", "descansar",
    "desear", "despertar", "destacar", "destruir", "detener", "devolver",
    "dibujar", "diferenciar", "discutir", "disfrutar", "disponer", "distinguir",
    "dividir", "doblar", "doler", "dormir", "dudar", "durar", "echar",
    "ejercer", "elaborar", "emplear", "enamorar", "encender", "encerrar",
    "enfrentar", "engañar", "enseñar", "entregar", "enviar", "equivocar",
    "escapar", "esconder", "exigir", "expresar", "faltar", "fijar", "financiar",
    "firmar", "frenar", "fumar", "funcionar", "generar", "girar", "golpear",
    "gozar", "gritar", "guiar", "habitar", "heredar", "huir", "ignorar",
    "impedir", "imponer", "incluir", "incorporar", "influir", "informar",
    "ingresar", "insistir", "instalar", "integrar", "intervenir", "introducir",
    "investigar", "invitar", "juntar", "jurar", "justificar", "lanzar", "limpiar",
    "luchar", "manejar", "manifestar", "mejorar", "mencionar", "merecer", "meter",
    "modificar", "mojar", "molestar", "mover", "nadar", "negar", "notar",
    "obedecer", "ocultar", "ocupar", "odiar", "operar", "opinar", "oponer",
    "organizar", "originar", "pararse", "participar", "pegar", "perdonar",
    "permanecer", "pertenecer", "pesar", "pintar", "plantear", "practicar",
    "precisar", "pretender", "prever", "prohibir", "prometer", "promover",
    "proponer", "proteger", "provocar", "publicar", "quejarse", "quemar",
    "quitar", "reaccionar", "rechazar", "reclamar", "recoger", "recorrer",
    "reducir", "reflejar", "regalar", "registrar", "regular", "reir", "relacionar",
    "rendir", "renunciar", "reparar", "repartir", "representar", "reproducir",
    "rescatar", "reservar", "resistir", "resolver", "respetar", "respirar",
    "retirar", "reunir", "revelar", "revisar", "rezar", "robar", "rodear",
    "rogar", "saltar", "saludar", "satisfacer", "secar", "seducir", "seleccionar",
    "sentar", "separar", "significar", "sobrevivir", "solicitar", "sonar",
    "soñar", "sonreir", "soportar", "sorprender", "sospechar", "sostener",
    "subrayar", "suceder", "sugerir", "sujetar", "sumar", "superar", "suprimir",
    "surgir", "suspender", "sustituir", "tardar", "telefonear", "temer", "tender",
    "tirar", "transformar", "transmitir", "trasladar", "unir", "untar", "variar",
    "vencer", "vestir", "viajar", "vigilar", "violar", "visitar", "votar",
    "acordar", "acostar", "acostumbrar", "actualizar", "admitir", "adoptar",
    "adquirir", "advertir", "afectar", "afirmar", "agarrar", "agradecer",
    "agregar", "alegrar", "aliviar", "alimentar", "almorzar", "alojar", "alterar",
    "amar", "amenazar", "aplicar", "apoyar", "apreciar", "apretar", "aprobar",
    "arrancar", "arreglar", "arriesgar", "arrojar", "asegurarse", "asignar",
    "asociar", "asumir", "asustar", "atacar", "atar", "atraer", "atribuir",
    "autorizar", "avisar", "ayunar", "borrar", "brillar", "brindar", "burlar",
    "calcular", "calentar", "callar", "cansar", "capturar", "castigar", "causar",
    "celebrar", "cenar", "circular", "citar", "clasificar", "cobrar", "colaborar",
    "combatir", "combinar", "comercializar", "competir", "complementar",
    "completar", "componer", "comunicar", "concentrar", "conceder", "condenar",
    "conectar", "conmemorar", "conquistar", "conseguir", "consultar", "contactar",
    "contemplar", "contestar", "contratar", "convivir", "cooperar", "copiar",
    "corregir", "cortar", "cosechar", "cotizar", "deducir", "definir", "delegar",
    "demandar", "denunciar", "depositar", "desafiar", "descargar", "desconocer",
    "describir", "designar", "desligar", "deslizar", "despedir", "despegar",
    "detallar", "dictar", "digerir", "disculpar", "diseñar", "disminuir",
    "disparar", "distribuir", "documentar", "donar", "dotar", "editar", "educar",
    "efectuar", "ejecutar", "elevar", "eliminar", "embarcar", "emerger", "emitir",
    "empujar", "encabezar", "encajar", "encargar", "enfermar", "enfocar",
    "enojar", "enriquecer", "ensayar", "entrenar", "entretener", "entrevistar",
    "enumerar", "envejecer", "escoger", "esculpir", "esforzar", "espantar",
    "estacionar", "estimar", "estimular", "estirar", "estrenar", "evaluar",
    "evolucionar", "exagerar", "examinar", "exhibir", "experimentar", "explorar",
    "explotar", "exponer", "exportar", "expulsar", "extraer", "extrañar",
    "fabricar", "facilitar", "fallar", "fascinar", "favorecer", "felicitar",
    "festejar", "filmar", "florecer", "fomentar", "fortalecer", "fotografiar",
    "fracasar", "fundar", "garantizar", "gastar", "gestionar", "graduar",
    "grabar", "habituar", "heredar", "hervir", "honrar", "hospedar", "humillar",
    "identificar", "iluminar", "ilustrar", "imitar", "implicar", "implementar",
    "importar", "impresionar", "imprimir", "impulsar", "inaugurar", "inclinar",
    "indignar", "inducir", "infectar", "inflar", "inscribir", "inspirar",
    "instruir", "insultar", "interesar", "interpretar", "interrumpir", "invadir",
    "inventar", "invertir", "involucrar", "lamentar", "lastimar", "legalizar",
    "liberar", "ligar", "limitar", "liquidar", "llenar", "localizar", "madurar",
    "manchar", "mandar", "masticar", "maximizar", "medir", "memorizar", "mezclar",
    "migrar", "moldear", "moderar", "motivar", "multiplicar", "navegar", "nombrar",
    "obsequiar", "ofrecer", "omitir", "ondear", "ordenar", "orientar", "pacificar",
    "padecer", "palpar", "pastar", "patrocinar", "penetrar", "percibir", "perdurar",
    "perfeccionar", "perjudicar", "permutar", "perseguir", "persistir",
    "persuadir", "planear", "planificar", "plantar", "poblar", "poseer",
    "posibilitar", "predecir", "predicar", "preocupar", "prescindir", "presenciar",
    "preservar", "presionar", "prestar", "presumir", "prevenir", "privar",
    "probar", "proceder", "procesar", "procurar", "profundizar", "programar",
    "progresar", "prolongar", "pronunciar", "propagar", "proporcionar",
    "prosperar", "protestar", "provenir", "publicar", "pulir", "quebrar",
    "razonar", "rebajar", "recargar", "recaudar", "recetar", "rechazar",
    "reclutar", "recomendar", "recompensar", "reconstruir", "recordar", "recrear",
    "rectificar", "recuperar", "redactar", "redoblar", "reembolsar", "referir",
    "reflexionar", "reforzar", "refrescar", "regir", "rehusar", "reinar",
    "reiterar", "relajar", "relatar", "remediar", "remitir", "remover", "renovar",
    "rentar", "reparar", "repasar", "replicar", "reportar", "reprimir", "reprochar",
    "requerir", "resaltar", "resbalar", "rescindir", "resfriar", "residir",
    "respaldar", "restar", "restaurar", "restringir", "resucitar", "resumir",
    "retener", "retrasar", "retroceder", "reunificar", "revertir", "revivir",
    "rociar", "rotar", "rubricar", "sacudir", "sancionar", "saquear", "sazonar",
    "secuestrar", "sembrar", "sentenciar", "sintetizar", "situar", "sobrar",
    "sobrepasar", "socorrer", "sofocar", "solucionar", "someter", "sonrojar",
    "soplar", "sostener", "subastar", "subir", "sublevar", "subsistir",
    "suceder", "sudar", "sufragar", "sujetar", "supervisar", "suplicar",
    "suprimir", "surtir", "suscitar", "suscribir", "tachar", "tallar", "tapar",
    "tasar", "tejer", "templar", "tentar", "teñir", "testificar", "tipificar",
    "titular", "tolerar", "tomar", "torcer", "tornar", "torturar", "toser",
    "trabar", "traducir", "traficar", "tragar", "traicionar", "tramitar",
    "tranquilizar", "trascender", "trasladar", "trastornar", "tratar", "trazar",
    "trenzar", "trepar", "tributar", "trillar", "triturar", "triunfar", "trocar",
    "tronar", "tropezar", "trotar", "tutelar", "ubicar", "ulcerar", "ultimar",
    "ultrajar", "ungir", "uniformar", "untar", "urbanizar", "urgir", "usar",
    "usurpar", "vacar", "vaciar", "vacilar", "vacunar", "vagar", "valorar",
    "valuar", "vanagloriar", "vaporizar", "vedar", "vegetar", "velar", "vendar",
    "venerar", "ventilar", "verificar", "versar", "verter", "vetar", "vibrar",
    "vincular", "vindicar", "violentar", "virar", "visualizar", "vitorear",
    "vituperar", "vocalizar", "vociferar", "volar", "volcar", "voltear",
    "vulnerar", "yacer", "zambullir", "zarpar", "zigzaguear", "zozobrar", "zurcir",
]


# A handful of common, fully-regular verbs are defective in verbecc's data — it
# returns only the 3rd-person-singular form and empty endings for the rest (it
# treats them like impersonal/weather verbs). We rebuild these from a working
# regular proxy verb of the same conjugation class by swapping the stem prefix.
# Maps broken_verb -> (proxy_verb, proxy_stem, target_stem).
REGULAR_FIX = {
    "pasar": ("hablar", "habl", "pas"),
    "resultar": ("hablar", "habl", "result"),
    "suceder": ("comer", "com", "suced"),
}


def is_corrupted(tense_map: dict[str, list]) -> bool:
    """Detect verbecc's defective-verb corruption.

    In Spanish present indicative the yo and tú forms are always distinct; a
    defective verb collapses them to the same truncated stem.
    """
    pres = tense_map.get("indicativo/presente")
    return bool(pres and pres[0] is not None and pres[0] == pres[1])


def rebuild_from_proxy(
    proxy_map: dict[str, list], proxy_stem: str, target_stem: str
) -> dict[str, list]:
    """Swap the proxy verb's stem for the target stem across all forms."""
    fixed: dict[str, list] = {}
    for tense_key, forms in proxy_map.items():
        fixed[tense_key] = [
            None if f is None else f.replace(proxy_stem, target_stem, 1) for f in forms
        ]
    return fixed


def extract_forms(conj_json: dict, tense_key: str) -> list[str | None]:
    """Return the 6 bare conjugated forms for a tense, aligned to CANONICAL_PRONOUNS.

    A slot is None when the tense has no entry for that pronoun (e.g. imperativo
    afirmativo lacks a "yo" form). The pronoun prefix is stripped from each form
    ("yo como" -> "como"; imperatives like "come" have no prefix and are kept).
    """
    mood, tense = tense_key.split("/", 1)
    entries = conj_json.get("moods", {}).get(mood, {}).get(tense)
    if not entries:
        return [None] * len(CANONICAL_PRONOUNS)

    by_pronoun: dict[str, str] = {}
    for entry in entries:
        pr = entry.get("pr")
        forms = entry.get("c") or []
        if not pr or not forms:
            continue
        form = forms[0]
        prefix = pr + " "
        if form.startswith(prefix):
            form = form[len(prefix):]
        by_pronoun.setdefault(pr, form)

    return [by_pronoun.get(pr) for pr in CANONICAL_PRONOUNS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="only process the first N verbs"
    )
    args = parser.parse_args()

    conjugator = CompleteConjugator("es")

    verbs = POPULAR_VERBS
    if args.limit is not None:
        verbs = verbs[: args.limit]

    def conjugate_verb(verb: str) -> dict[str, list]:
        conj = json.loads(conjugator.conjugate(verb).to_json())
        tense_map: dict[str, list] = {}
        for tense_key in TENSES:
            forms = extract_forms(conj, tense_key)
            if any(f is not None for f in forms):
                tense_map[tense_key] = forms
        return tense_map

    result: dict[str, dict[str, list]] = {}
    missing: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()

    for verb in verbs:
        if verb in seen:
            continue
        seen.add(verb)
        try:
            tense_map = conjugate_verb(verb)
        except Exception as exc:  # noqa: BLE001 — verbecc raises VerbNotFoundError etc.
            missing.append(f"{verb} ({type(exc).__name__})")
            continue
        if is_corrupted(tense_map):
            if verb in REGULAR_FIX:
                proxy_verb, proxy_stem, target_stem = REGULAR_FIX[verb]
                proxy_map = conjugate_verb(proxy_verb)
                tense_map = rebuild_from_proxy(proxy_map, proxy_stem, target_stem)
            else:
                dropped.append(verb)
                continue
        if tense_map:
            result[verb] = tense_map

    # Preserve POPULAR_VERBS (frequency) order so the app can rank autocomplete
    # suggestions by commonness (e.g. "co" -> "comer" before rarer co* verbs).
    # Tense keys within each verb are sorted for stable diffs.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=0, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(result)} verbs to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"File size: {size_kb:.0f} KiB")
    if missing:
        print(f"\nSkipped {len(missing)} verb(s) not found in verbecc:")
        for m in missing:
            print(f"  - {m}")
    if dropped:
        print(f"\nDropped {len(dropped)} defective verb(s) (verbecc returns only")
        print("3rd-person-singular; not in REGULAR_FIX, so excluded):")
        for v in dropped:
            print(f"  - {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
