/**
 * normalizeText(): the browser's copy of normalize_text() in quiz_logic.py, so
 * an answer checked here is accepted or refused exactly as the server would.
 *
 * The only copy. Load it before any script that compares answers, and change it
 * together with the Python. Five copies had drifted apart before it existed:
 * only one stripped every combining mark and mapped Turkish ı, as the server
 * does.
 */
function normalizeText(text) {
    return text.toLowerCase().trim()
        // German: "fuenf" for "fünf", "zwoelf" for "zwölf".
        .replace(/ü/g, 'ue').replace(/ö/g, 'oe').replace(/ä/g, 'ae')
        .replace(/ß/g, 'ss')
        // Turkish dotless i, which NFD doesn't decompose.
        .replace(/ı/g, 'i')
        .split(/\s+/).join(' ')
        // Accents: decompose, then drop every nonspacing mark (Python's "Mn").
        .normalize('NFD').replace(/\p{Mn}/gu, '');
}
