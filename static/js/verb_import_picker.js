/**
 * The checklist shown before index-card verbs are imported into conjugation
 * practice. A word on a card can be spelled like a verb without being one
 * ("Land / country"), and only the person who wrote the card can tell, so
 * nothing is added until they have seen the list.
 *
 * window.pickCardVerbsToImport(lang) fetches the candidates, shows them, and
 * imports what stays ticked. `lang` restricts it to one pool (a /<lang>/conjugate
 * page); without it the server runs its automatic scan (/cards). It resolves to
 * the import response, or to null if the user cancelled, and rejects on a failed
 * request.
 */

window.pickCardVerbsToImport = (function () {
    const ENDPOINT = '/api/verbs/import-from-cards';

    function buildRow(verb, index) {
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.checked = true;
        box.value = String(index);

        const name = document.createElement('span');
        name.className = 'verb-import-verb';
        name.textContent = verb.infinitive;

        const card = document.createElement('span');
        card.className = 'verb-import-card';
        card.textContent = verb.front + ' / ' + verb.back;

        const label = document.createElement('label');
        label.className = 'verb-import-row';
        label.append(box, name, card);

        const li = document.createElement('li');
        li.appendChild(label);
        return li;
    }

    // Resolves to the verbs left ticked, or null if the list was dismissed.
    function choose(verbs) {
        const modal = document.getElementById('verb-import-modal');
        const form = document.getElementById('verb-import-form');
        const list = document.getElementById('verb-import-list');
        const confirm = document.getElementById('verb-import-confirm');
        const cancel = document.getElementById('verb-import-cancel');

        list.replaceChildren.apply(list, verbs.map(buildRow));
        confirm.disabled = false;
        modal.hidden = false;
        confirm.focus();

        return new Promise(function (resolve) {
            const listeners = new AbortController();
            const on = { signal: listeners.signal };

            function close(result) {
                listeners.abort();
                modal.hidden = true;
                resolve(result);
            }

            function ticked() {
                return Array.from(list.querySelectorAll('input:checked'));
            }

            list.addEventListener('change', function () {
                confirm.disabled = ticked().length === 0;
            }, on);
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                close(ticked().map(function (box) { return verbs[Number(box.value)]; }));
            }, on);
            cancel.addEventListener('click', function () { close(null); }, on);
            modal.addEventListener('click', function (e) {
                if (e.target === modal) close(null);
            }, on);
            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') close(null);
            }, on);
        });
    }

    async function readJson(res) {
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error('Verb import request failed');
        return data;
    }

    return async function pickCardVerbsToImport(lang) {
        const query = lang ? '?lang=' + encodeURIComponent(lang) : '';
        const candidates = (await readJson(await fetch(ENDPOINT + query))).verbs;
        if (!candidates.length) return { added: 0, remaining: 0, verbs: [] };

        const chosen = await choose(candidates);
        if (chosen === null) return null;

        const payload = { verbs: chosen.map(function (verb) {
            return { lang: verb.lang, infinitive: verb.infinitive };
        }) };
        if (lang) payload.lang = lang;
        return readJson(await fetch(ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }));
    };
}());
