/**
 * Verb-conjugation manage page (/conjugate): add verbs with autocomplete from
 * the global pool, delete verbs, and show a "not supported" popup when a typed
 * verb isn't in the pool. Progressive enhancement — the underlying form POSTs
 * (add via /api/verbs, delete via /conjugate/<id>/delete) still work without JS.
 */

(function () {
    'use strict';

    const addSection = document.querySelector('.conjugate-add-section');
    const addForm = document.getElementById('conjugate-add-form');
    const input = document.getElementById('conjugate-verb-input');
    const suggestions = document.getElementById('conjugate-suggestions');
    if (!addSection || !addForm || !input || !suggestions) return;

    const i18n = {
        added: addSection.getAttribute('data-i18n-added') || 'Verb added.',
        duplicate: addSection.getAttribute('data-i18n-duplicate') || 'That verb is already in your list.',
        del: addSection.getAttribute('data-i18n-delete') || 'Remove',
        popupTitle: addSection.getAttribute('data-i18n-popup-title') || 'Verb not supported',
        addToCards: addSection.getAttribute('data-i18n-add-to-cards') || 'Add to cards'
    };
    const toastIcon = addSection.getAttribute('data-toast-icon') || '';

    const countEl = document.getElementById('conjugate-count');
    const popup = document.getElementById('conjugate-popup');
    const popupBody = document.getElementById('conjugate-popup-body');
    const popupClose = document.getElementById('conjugate-popup-close');

    // ----- Toast / popup helpers -------------------------------------------

    function showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-success';
        if (toastIcon) {
            const icon = document.createElement('img');
            icon.src = toastIcon;
            icon.alt = '';
            icon.className = 'toast-icon';
            toast.appendChild(icon);
        }
        const span = document.createElement('span');
        span.textContent = message;
        toast.appendChild(span);
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 3100);
    }

    function showPopup(message) {
        if (!popup) return;
        if (popupBody) popupBody.textContent = message;
        popup.hidden = false;
    }
    function hidePopup() {
        if (popup) popup.hidden = true;
    }
    if (popupClose) popupClose.addEventListener('click', hidePopup);
    if (popup) {
        popup.addEventListener('click', function (e) {
            if (e.target === popup) hidePopup();
        });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && popup && !popup.hidden) hidePopup();
    });

    // ----- List rendering --------------------------------------------------

    function findList() {
        return document.getElementById('conjugate-list');
    }

    function ownedVerbs() {
        const list = findList();
        if (!list) return [];
        return Array.prototype.map.call(
            list.querySelectorAll('.conjugate-list-infinitive'),
            function (el) { return (el.textContent || '').trim().toLowerCase(); }
        );
    }

    function updateCount() {
        if (!countEl) return;
        const list = findList();
        const n = list ? list.querySelectorAll('.conjugate-list-item').length : 0;
        countEl.textContent = '(' + n + ')';
    }

    function buildEmptyRing() {
        const wrap = document.createElement('div');
        wrap.className = 'cards-progress cards-progress-empty';
        wrap.setAttribute('data-score', '');
        wrap.setAttribute('data-practiced', '0');
        wrap.setAttribute('aria-label', 'No practice attempts yet');
        const svgNS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNS, 'svg');
        svg.setAttribute('class', 'cards-progress-svg');
        svg.setAttribute('viewBox', '0 0 36 36');
        svg.setAttribute('aria-hidden', 'true');
        const track = document.createElementNS(svgNS, 'circle');
        track.setAttribute('class', 'cards-progress-track');
        track.setAttribute('cx', '18');
        track.setAttribute('cy', '18');
        track.setAttribute('r', '15.9155');
        svg.appendChild(track);
        const text = document.createElement('span');
        text.className = 'cards-progress-text';
        text.textContent = '—';
        wrap.appendChild(svg);
        wrap.appendChild(text);
        return wrap;
    }

    function buildVerbLi(verb, opts) {
        opts = opts || {};
        const li = document.createElement('li');
        li.className = 'cards-list-item conjugate-list-item';
        li.setAttribute('data-verb-id', String(verb.id));

        const text = document.createElement('div');
        text.className = 'cards-list-text';
        const inf = document.createElement('span');
        inf.className = 'conjugate-list-infinitive';
        inf.textContent = verb.infinitive;
        text.appendChild(inf);

        const actions = document.createElement('div');
        actions.className = 'cards-list-actions';
        if (opts.missing) {
            const toCard = document.createElement('button');
            toCard.type = 'button';
            toCard.className = 'btn btn-secondary cards-list-btn conjugate-verb-to-card-btn';
            toCard.setAttribute('data-infinitive', verb.infinitive);
            toCard.textContent = i18n.addToCards;
            actions.appendChild(toCard);
        }
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/conjugate/' + verb.id + '/delete';
        form.className = 'conjugate-delete-form';
        const btn = document.createElement('button');
        btn.type = 'submit';
        btn.className = 'btn btn-secondary cards-list-btn cards-list-btn-delete';
        btn.textContent = i18n.del;
        form.appendChild(btn);
        actions.appendChild(form);

        li.appendChild(text);
        li.appendChild(buildEmptyRing());
        li.appendChild(actions);
        return li;
    }

    function ensureList() {
        let list = findList();
        if (list) return list;
        // Replace the empty-state paragraph with a fresh list.
        const section = document.querySelector('.cards-list-section');
        const empty = document.getElementById('conjugate-empty');
        if (empty) empty.remove();
        list = document.createElement('ul');
        list.className = 'cards-list conjugate-list';
        list.id = 'conjugate-list';
        if (section) section.appendChild(list);
        return list;
    }

    // ----- Autocomplete ----------------------------------------------------

    let activeIndex = -1;
    let searchTimer = null;

    function clearSuggestions() {
        suggestions.innerHTML = '';
        suggestions.hidden = true;
        activeIndex = -1;
    }

    function renderSuggestions(items) {
        suggestions.innerHTML = '';
        if (!items.length) {
            clearSuggestions();
            return;
        }
        items.forEach(function (verb, idx) {
            const li = document.createElement('li');
            li.className = 'conjugate-suggestion';
            li.setAttribute('role', 'option');
            li.setAttribute('data-index', String(idx));
            li.textContent = verb;
            li.addEventListener('mousedown', function (e) {
                // mousedown (not click) so it fires before the input blur.
                e.preventDefault();
                input.value = verb;
                clearSuggestions();
                input.focus();
            });
            suggestions.appendChild(li);
        });
        suggestions.hidden = false;
        activeIndex = -1;
    }

    function highlight(delta) {
        const opts = suggestions.querySelectorAll('.conjugate-suggestion');
        if (!opts.length) return;
        activeIndex = (activeIndex + delta + opts.length) % opts.length;
        opts.forEach(function (o, i) {
            o.classList.toggle('conjugate-suggestion-active', i === activeIndex);
        });
    }

    async function fetchSuggestions(q) {
        try {
            const res = await fetch('/api/verbs/search?q=' + encodeURIComponent(q));
            if (!res.ok) return;
            const data = await res.json();
            renderSuggestions(data.results || []);
        } catch (e) {
            clearSuggestions();
        }
    }

    input.addEventListener('input', function () {
        const q = input.value.trim();
        if (searchTimer) clearTimeout(searchTimer);
        if (q.length < 1) {
            clearSuggestions();
            return;
        }
        searchTimer = setTimeout(function () { fetchSuggestions(q); }, 150);
    });

    input.addEventListener('keydown', function (e) {
        if (suggestions.hidden) return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            highlight(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            highlight(-1);
        } else if (e.key === 'Enter') {
            if (activeIndex >= 0) {
                const opts = suggestions.querySelectorAll('.conjugate-suggestion');
                if (opts[activeIndex]) {
                    e.preventDefault();
                    input.value = opts[activeIndex].textContent;
                    clearSuggestions();
                }
            }
        } else if (e.key === 'Escape') {
            clearSuggestions();
        }
    });

    input.addEventListener('blur', function () {
        // Delay so a mousedown on a suggestion is processed first.
        setTimeout(clearSuggestions, 120);
    });

    // ----- Add -------------------------------------------------------------

    addForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const verb = (input.value || '').trim().toLowerCase();
        if (!verb) return;
        if (ownedVerbs().indexOf(verb) !== -1) {
            showToast(i18n.duplicate);
            input.value = '';
            clearSuggestions();
            return;
        }
        try {
            const res = await fetch('/api/verbs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ infinitive: verb })
            });
            const data = await res.json();
            if (!res.ok || !data.ok) {
                if (data && data.unsupported) {
                    showPopup(data.error || i18n.popupTitle);
                }
                return;
            }
            if (data.duplicate) {
                showToast(i18n.duplicate);
            } else if (data.verb) {
                const list = ensureList();
                // A freshly typed verb usually isn't in the deck yet, so offer
                // the per-verb "add to cards" affordance; duplicates are deduped
                // server-side if it turns out to already be a card.
                list.insertBefore(buildVerbLi(data.verb, { missing: true }), list.firstChild);
                updateCount();
                showToast(i18n.added);
            }
            input.value = '';
            clearSuggestions();
            input.focus();
        } catch (err) {
            // Fall back to a normal form submit on network error.
            addForm.submit();
        }
    });

    // ----- Delete (event-delegated) ----------------------------------------

    document.addEventListener('submit', async function (e) {
        const form = e.target;
        if (!form.classList || !form.classList.contains('conjugate-delete-form')) return;
        e.preventDefault();
        const li = form.closest('.conjugate-list-item');
        if (!li) return;
        const verbId = li.getAttribute('data-verb-id');
        try {
            const res = await fetch('/api/verbs/' + verbId, { method: 'DELETE' });
            if (!res.ok) {
                form.submit();
                return;
            }
            li.remove();
            updateCount();
        } catch (err) {
            form.submit();
        }
    });

    // ----- Insights matrix (reactive to the practice settings) -------------
    // The matrix mirrors what's selected in the practice form below it: only the
    // ticked tenses and the vosotros toggle feed the tense / pronoun rows, and
    // recap buttons inherit the current tenses, persons and difficulty. The verb
    // row always covers every verb (verb scores aren't sliceable per tense).

    (function initMatrix() {
        const matrixEl = document.getElementById('conjugate-matrix');
        const dataEl = document.getElementById('conjugate-stats-data');
        const practiceForm = document.querySelector('.conjugate-practice-form');
        if (!matrixEl || !dataEl || !practiceForm) return;

        let data;
        try {
            data = JSON.parse(dataEl.textContent || '{}');
        } catch (e) {
            return;
        }
        if (!data.categories) return;

        function categoryOf(score) {
            if (score === null || score === undefined) return 'unpracticed';
            if (score < 0.5) return 'weak';
            if (score < 0.8) return 'needs_work';
            return null; // strong — not shown in the matrix
        }

        function scoreFromCounts(practiced, correct) {
            return practiced ? correct / practiced : null;
        }

        function readSelection() {
            const tenses = Array.prototype.map.call(
                practiceForm.querySelectorAll('input[name="tenses"]:checked'),
                function (el) { return el.value; }
            );
            const vosotros = practiceForm.querySelector('input[name="include_vosotros"]');
            const vosotrosOn = !!(vosotros && vosotros.checked);
            const persons = data.persons
                .filter(function (p) { return !p.optional || vosotrosOn; })
                .map(function (p) { return p.index; });
            const diffEl = practiceForm.querySelector('input[name="difficulty"]:checked');
            const difficulty = diffEl ? diffEl.value : 'advanced';
            return { tenses: tenses, persons: persons, difficulty: difficulty };
        }

        function bucket(items, scoreFn) {
            const m = { unpracticed: [], weak: [], needs_work: [] };
            items.forEach(function (it) {
                const cat = categoryOf(scoreFn(it));
                if (cat) m[cat].push(it);
            });
            return m;
        }

        function computeDimensions(sel) {
            const selTenses = sel.tenses;
            const selPersons = sel.persons;

            const tenseItems = data.tenses.filter(function (t) {
                return selTenses.indexOf(t.key) !== -1;
            });
            const personItems = data.persons.filter(function (p) {
                return selPersons.indexOf(p.index) !== -1;
            });

            const tenseM = bucket(tenseItems, function (t) {
                return scoreFromCounts(t.practiced, t.correct);
            });
            const verbM = bucket(data.verbs, function (v) { return v.score; });
            const personM = bucket(personItems, function (p) {
                return scoreFromCounts(p.practiced, p.correct);
            });

            function cells(members, tensesFn, verbIdsFn, personsFn) {
                const out = {};
                data.categories.forEach(function (cat) {
                    const ids = members[cat];
                    out[cat] = {
                        count: ids.length,
                        tenses: tensesFn(ids),
                        verb_ids: verbIdsFn(ids),
                        persons: personsFn(ids)
                    };
                });
                return out;
            }

            return [
                {
                    label: data.dimension_labels.tenses,
                    cells: cells(
                        tenseM,
                        function (ids) { return ids.map(function (t) { return t.key; }); },
                        function () { return []; },
                        function () { return selPersons; }
                    )
                },
                {
                    label: data.dimension_labels.verbs,
                    cells: cells(
                        verbM,
                        function () { return selTenses; },
                        function (ids) { return ids.map(function (v) { return v.id; }); },
                        function () { return selPersons; }
                    )
                },
                {
                    label: data.dimension_labels.pronouns,
                    cells: cells(
                        personM,
                        function () { return selTenses; },
                        function () { return []; },
                        function (ids) { return ids.map(function (p) { return p.index; }); }
                    )
                }
            ];
        }

        function makeSpan(classes, text, role) {
            const el = document.createElement('span');
            el.className = classes;
            if (role) el.setAttribute('role', role);
            if (text) el.textContent = text;
            return el;
        }

        function hidden(name, value) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            input.value = String(value);
            return input;
        }

        function buildCell(cell, difficulty) {
            const div = document.createElement('div');
            div.className = 'conjugate-matrix-cell' + (cell.count === 0 ? ' conjugate-matrix-cell-empty' : '');
            div.setAttribute('role', 'cell');
            div.appendChild(makeSpan('conjugate-matrix-count', String(cell.count)));
            if (cell.count > 0) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = data.start_url;
                form.className = 'conjugate-matrix-recap-form';
                cell.tenses.forEach(function (t) { form.appendChild(hidden('tenses', t)); });
                cell.verb_ids.forEach(function (v) { form.appendChild(hidden('verb_ids', v)); });
                cell.persons.forEach(function (p) { form.appendChild(hidden('persons', p)); });
                form.appendChild(hidden('difficulty', difficulty));
                form.appendChild(hidden('sampling_mode', 'prioritized'));
                form.appendChild(hidden('reveal_mode', 'type'));
                form.appendChild(hidden('count', data.default_count));
                const btn = document.createElement('button');
                btn.type = 'submit';
                btn.className = 'btn btn-primary conjugate-matrix-recap-btn';
                btn.textContent = data.recap_label;
                form.appendChild(btn);
                div.appendChild(form);
            }
            return div;
        }

        function render() {
            const sel = readSelection();
            const dims = computeDimensions(sel);
            matrixEl.innerHTML = '';

            const head = document.createElement('div');
            head.className = 'conjugate-matrix-row conjugate-matrix-head';
            head.setAttribute('role', 'row');
            head.appendChild(makeSpan('conjugate-matrix-corner', '', 'columnheader'));
            data.categories.forEach(function (cat) {
                head.appendChild(makeSpan(
                    'conjugate-matrix-colhead conjugate-matrix-colhead-' + cat,
                    data.category_labels[cat],
                    'columnheader'
                ));
            });
            matrixEl.appendChild(head);

            dims.forEach(function (dim) {
                const row = document.createElement('div');
                row.className = 'conjugate-matrix-row';
                row.setAttribute('role', 'row');
                row.appendChild(makeSpan('conjugate-matrix-rowhead', dim.label, 'rowheader'));
                data.categories.forEach(function (cat) {
                    row.appendChild(buildCell(dim.cells[cat], sel.difficulty));
                });
                matrixEl.appendChild(row);
            });
        }

        practiceForm.addEventListener('change', render);
        render();
    }());

    // ----- Cards <-> conjugation sync --------------------------------------

    (function initSync() {
        const syncActions = document.querySelector('.conjugate-sync-actions');
        if (!syncActions) return;

        const syncI18n = {
            importDone: syncActions.getAttribute('data-i18n-import-done') || 'Imported {n} verb(s) from your cards.',
            importNone: syncActions.getAttribute('data-i18n-import-none') || 'No new verbs to import.',
            importTpl: syncActions.getAttribute('data-i18n-import-template') || 'Import {n} from index cards',
            missingTpl: syncActions.getAttribute('data-i18n-missing-template') || '{n} verbs aren’t in your index cards — add',
            syncDone: syncActions.getAttribute('data-i18n-sync-done') || 'Added {n} card(s) to your deck.'
        };

        // --- Import card verbs into conjugation practice ---
        const importBtn = document.getElementById('conjugate-import-from-cards');
        if (importBtn) {
            importBtn.addEventListener('click', async function () {
                importBtn.disabled = true;
                try {
                    const res = await fetch('/api/verbs/import-from-cards', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await res.json();
                    if (!res.ok || !data.ok) {
                        importBtn.disabled = false;
                        return;
                    }
                    const list = ensureList();
                    (data.verbs || []).forEach(function (verb) {
                        list.insertBefore(buildVerbLi(verb), list.firstChild);
                    });
                    updateCount();
                    importBtn.classList.add('conjugate-sync-hidden');
                    const added = data.added || 0;
                    showToast(
                        added > 0
                            ? syncI18n.importDone.replace('{n}', String(added))
                            : syncI18n.importNone
                    );
                } catch (err) {
                    importBtn.disabled = false;
                }
            });
        }

        // --- Walk-through: add missing verbs to index cards ---
        const missingBtn = document.getElementById('conjugate-missing-in-cards');
        const dataEl = document.getElementById('conjugate-missing-in-cards-data');
        const modal = document.getElementById('conjugate-sync-modal');
        const modalForm = document.getElementById('conjugate-sync-form');
        const verbEl = document.getElementById('conjugate-sync-verb');
        const transInput = document.getElementById('conjugate-sync-translation');
        const progressEl = document.getElementById('conjugate-sync-progress');
        const skipBtn = document.getElementById('conjugate-sync-skip');
        if (!missingBtn || !dataEl || !modal || !modalForm) return;

        let pending = [];
        try {
            pending = (JSON.parse(dataEl.textContent || '[]') || [])
                .map(function (it) { return it.infinitive; })
                .filter(Boolean);
        } catch (e) {
            pending = [];
        }

        let queue = [];
        let index = 0;
        let createdCount = 0;
        let created = {};

        function updateMissingBtn() {
            missingBtn.setAttribute('data-count', String(pending.length));
            if (pending.length <= 0) {
                missingBtn.classList.add('conjugate-sync-hidden');
            } else {
                missingBtn.textContent = syncI18n.missingTpl.replace('{n}', String(pending.length));
            }
        }

        function closeModal() {
            modal.hidden = true;
        }

        function finish() {
            closeModal();
            // Drop per-verb "add to cards" buttons for verbs now in the deck.
            const list = findList();
            if (list) {
                list.querySelectorAll('.conjugate-verb-to-card-btn').forEach(function (b) {
                    if (created[b.getAttribute('data-infinitive')]) b.remove();
                });
            }
            pending = pending.filter(function (inf) { return !created[inf]; });
            updateMissingBtn();
            if (createdCount > 0) {
                showToast(syncI18n.syncDone.replace('{n}', String(createdCount)));
            }
        }

        function startSync(infinitives) {
            queue = infinitives.slice();
            index = 0;
            createdCount = 0;
            created = {};
            showCurrent();
        }

        function showCurrent() {
            if (index >= queue.length) {
                finish();
                return;
            }
            const infinitive = queue[index];
            if (verbEl) verbEl.textContent = infinitive;
            if (progressEl) progressEl.textContent = (index + 1) + ' / ' + queue.length;
            if (transInput) transInput.value = '';
            modal.hidden = false;
            if (transInput) transInput.focus();
        }

        missingBtn.addEventListener('click', function () {
            if (!pending.length) return;
            startSync(pending);
        });

        // Per-verb "add to index cards" (event-delegated so dynamically added
        // verb rows are covered too).
        document.addEventListener('click', function (e) {
            const btn = e.target.closest('.conjugate-verb-to-card-btn');
            if (!btn) return;
            const infinitive = (btn.getAttribute('data-infinitive') || '').trim();
            if (infinitive) startSync([infinitive]);
        });

        if (skipBtn) {
            skipBtn.addEventListener('click', function () {
                index += 1;
                showCurrent();
            });
        }

        modalForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const infinitive = queue[index];
            const translation = (transInput && transInput.value || '').trim();
            if (!translation) {
                if (transInput) transInput.focus();
                return;
            }
            try {
                const res = await fetch('/api/cards', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ front: infinitive, back: translation })
                });
                const data = await res.json();
                if (res.ok && data.ok) {
                    created[infinitive] = true;
                    if (!data.duplicate) createdCount += 1;
                }
            } catch (err) {
                // Ignore and advance — the user can retry from /cards.
            }
            index += 1;
            showCurrent();
        });

        modal.addEventListener('click', function (e) {
            if (e.target === modal) finish();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.hidden) finish();
        });
    }());
}());
