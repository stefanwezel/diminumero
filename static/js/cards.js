/**
 * In-place add/edit/delete on /cards. Progressive enhancement:
 * if anything fails or JS is disabled, the underlying form submissions
 * still work via the server-rendered routes.
 */

(function () {
    'use strict';

    // Only enhance the list view, not the server-rendered ?edit=<id> view —
    // the create form's id is only emitted when no card is being edited.
    const createForm = document.getElementById('cards-create-form');
    if (!createForm) return;

    const section = document.querySelector('.cards-list-section');
    if (!section) return;

    const i18n = {
        front: section.getAttribute('data-i18n-front') || 'Front',
        back: section.getAttribute('data-i18n-back') || 'Back',
        edit: section.getAttribute('data-i18n-edit') || 'Edit',
        del: section.getAttribute('data-i18n-delete') || 'Delete',
        save: section.getAttribute('data-i18n-save') || 'Save',
        cancel: section.getAttribute('data-i18n-cancel') || 'Cancel',
        frontPh: section.getAttribute('data-i18n-front-placeholder') || '',
        backPh: section.getAttribute('data-i18n-back-placeholder') || '',
        created: section.getAttribute('data-i18n-created') || 'Card added.',
        duplicate: section.getAttribute('data-i18n-duplicate') || 'That card is already in your deck — nothing added.',
        duplicateEdit: section.getAttribute('data-i18n-duplicate-edit') || 'Another card already matches those sides — change not applied.',
        verbSynced: section.getAttribute('data-i18n-verb-synced') || 'Added to conjugation practice.',
        importDone: section.getAttribute('data-i18n-import-done') || 'Imported {n} verb(s) from your cards.',
        importNone: section.getAttribute('data-i18n-import-none') || 'No new verbs to import.',
        verbAdd: section.getAttribute('data-i18n-verb-add') || 'Add to conjugation',
        verbBadge: section.getAttribute('data-i18n-verb-badge') || 'verb'
    };
    const toastIcon = section.getAttribute('data-toast-icon') || '';

    const countEl = document.getElementById('cards-count');

    function findList() {
        return document.querySelector('[data-cards-list]');
    }

    function updateCount() {
        if (!countEl) return;
        const list = findList();
        const n = list ? list.querySelectorAll('.cards-list-item').length : 0;
        countEl.textContent = '(' + n + ')';
    }

    function flash(li) {
        li.classList.remove('cards-list-item-flash');
        // Force reflow so the animation restarts on repeat edits.
        void li.offsetWidth;
        li.classList.add('cards-list-item-flash');
        setTimeout(function () {
            li.classList.remove('cards-list-item-flash');
        }, 800);
    }

    function buildCardLi(card, verbInfinitive) {
        const li = document.createElement('li');
        li.className = 'cards-list-item';
        li.setAttribute('data-card-id', String(card.id));
        li.setAttribute(
            'data-created-at',
            card.created_at || new Date().toISOString()
        );

        const text = document.createElement('div');
        text.className = 'cards-list-text';

        const lineFront = document.createElement('div');
        lineFront.className = 'cards-list-line';
        const labelFront = document.createElement('span');
        labelFront.className = 'cards-list-label cards-list-label-front';
        labelFront.textContent = i18n.front;
        const valFront = document.createElement('span');
        valFront.className = 'cards-list-front';
        valFront.textContent = card.front;
        lineFront.appendChild(labelFront);
        lineFront.appendChild(valFront);

        const lineBack = document.createElement('div');
        lineBack.className = 'cards-list-line';
        const labelBack = document.createElement('span');
        labelBack.className = 'cards-list-label cards-list-label-back';
        labelBack.textContent = i18n.back;
        const valBack = document.createElement('span');
        valBack.className = 'cards-list-back';
        valBack.textContent = card.back;
        lineBack.appendChild(labelBack);
        lineBack.appendChild(valBack);

        text.appendChild(lineFront);
        text.appendChild(lineBack);

        const progress = buildProgress(card);
        const actions = buildActions(card.id);

        li.appendChild(text);
        li.appendChild(progress);
        li.appendChild(actions);
        applyVerbAffordance(li, verbInfinitive);
        return li;
    }

    function buildProgress(card) {
        const wrap = document.createElement('div');
        wrap.className = 'cards-progress';
        wrap.setAttribute('data-practiced', String(card.times_practiced || 0));

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

        const hasScore = typeof card.score === 'number';
        if (hasScore) {
            const pct = Math.round(card.score * 100);
            const hue = Math.round(120 * card.score * 10) / 10;
            wrap.setAttribute('data-score', String(card.score));
            wrap.style.setProperty('--progress-color', 'hsl(' + hue + ', 70%, 42%)');
            wrap.setAttribute(
                'aria-label',
                pct + '% correct (' + (card.times_correct || 0) + '/' + (card.times_practiced || 0) + ')'
            );
            const bar = document.createElementNS(svgNS, 'circle');
            bar.setAttribute('class', 'cards-progress-bar');
            bar.setAttribute('cx', '18');
            bar.setAttribute('cy', '18');
            bar.setAttribute('r', '15.9155');
            bar.setAttribute('stroke-dasharray', pct + ' 100');
            svg.appendChild(bar);
            text.textContent = pct + '%';
        } else {
            wrap.classList.add('cards-progress-empty');
            wrap.setAttribute('data-score', '');
            wrap.setAttribute('aria-label', 'No practice attempts yet');
            text.textContent = '—';
        }

        wrap.appendChild(svg);
        wrap.appendChild(text);
        return wrap;
    }

    function buildActions(cardId) {
        const actions = document.createElement('div');
        actions.className = 'cards-list-actions';

        const editLink = document.createElement('a');
        editLink.className = 'btn btn-secondary cards-list-btn';
        editLink.href = '/cards?edit=' + cardId + '#edit';
        editLink.textContent = i18n.edit;

        const deleteForm = document.createElement('form');
        deleteForm.method = 'POST';
        deleteForm.action = '/cards/' + cardId + '/delete';
        deleteForm.className = 'cards-delete-form';
        const delBtn = document.createElement('button');
        delBtn.type = 'submit';
        delBtn.className = 'btn btn-secondary cards-list-btn cards-list-btn-delete';
        delBtn.textContent = i18n.del;
        deleteForm.appendChild(delBtn);

        actions.appendChild(editLink);
        actions.appendChild(deleteForm);
        return actions;
    }

    function setCreateError(message) {
        let err = createForm.querySelector('.cards-create-error');
        if (!err) {
            err = document.createElement('div');
            err.className = 'cards-create-error';
            err.setAttribute('role', 'alert');
            createForm.appendChild(err);
        }
        err.textContent = message;
    }

    function clearCreateError() {
        const err = createForm.querySelector('.cards-create-error');
        if (err) err.remove();
    }

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
        // The toast CSS animation runs slideIn (0–0.5s) then slideOut (2.5–3s);
        // remove just after slideOut completes.
        setTimeout(function () { toast.remove(); }, 3100);
    }

    // ----- Create -----

    createForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const frontIn = createForm.querySelector('input[name="front"]');
        const backIn = createForm.querySelector('input[name="back"]');
        const front = (frontIn.value || '').trim();
        const back = (backIn.value || '').trim();
        if (!front || !back) {
            // Browser's native required validation will fire on real submit;
            // here we just bail silently.
            return;
        }
        try {
            const response = await fetch('/api/cards', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ front: front, back: back })
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                setCreateError(data.error || 'Could not create card');
                return;
            }
            clearCreateError();
            const list = findList();
            if (!list) {
                // Empty deck — full reload to also reveal the practice form.
                location.reload();
                return;
            }
            if (data.duplicate) {
                // Server detected a normalized match; highlight the existing row
                // instead of inserting a new one.
                const existing = list.querySelector(
                    '[data-card-id="' + String(data.card.id) + '"]'
                );
                if (existing) {
                    existing.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    flash(existing);
                }
                frontIn.value = '';
                backIn.value = '';
                frontIn.focus();
                showToast(i18n.duplicate);
                return;
            }
            const li = buildCardLi(data.card, data.verb_infinitive);
            list.insertBefore(li, list.firstChild);
            if (typeof window.diminumeroCardsApplySort === 'function') {
                window.diminumeroCardsApplySort();
            }
            refreshImportAllCount();
            frontIn.value = '';
            backIn.value = '';
            frontIn.focus();
            updateCount();
            flash(li);
            showToast(i18n.created);
        } catch (err) {
            setCreateError('Network error — please try again');
        }
    });

    // ----- Delete (event delegation) -----

    document.addEventListener('submit', async function (e) {
        const form = e.target.closest('.cards-delete-form');
        if (!form) return;
        const li = form.closest('.cards-list-item');
        if (!li) return;
        e.preventDefault();
        const cardId = li.getAttribute('data-card-id');
        if (!cardId) return;
        try {
            const response = await fetch('/api/cards/' + cardId, {
                method: 'DELETE',
                headers: { 'Accept': 'application/json' }
            });
            if (!response.ok) {
                location.reload();
                return;
            }
            li.classList.add('cards-list-item-removing');
            let removed = false;
            const finish = function () {
                if (removed) return;
                removed = true;
                li.remove();
                updateCount();
                const list = findList();
                if (list && list.querySelectorAll('.cards-list-item').length === 0) {
                    // Deck is empty — reload to render the empty state and
                    // hide the practice form.
                    location.reload();
                }
            };
            li.addEventListener('transitionend', finish, { once: true });
            // Fallback if transitionend doesn't fire (e.g., reduced motion).
            setTimeout(finish, 400);
        } catch (err) {
            location.reload();
        }
    });

    // ----- Edit toggle (event delegation) -----

    document.addEventListener('click', function (e) {
        const link = e.target.closest('.cards-list-actions a.cards-list-btn');
        if (!link) return;
        const li = link.closest('.cards-list-item');
        if (!li) return;
        e.preventDefault();
        startInlineEdit(li);
    });

    function startInlineEdit(li) {
        if (li.querySelector('.cards-inline-edit-form')) return;

        const cardId = li.getAttribute('data-card-id');
        const text = li.querySelector('.cards-list-text');
        const actions = li.querySelector('.cards-list-actions');
        if (!text || !actions || !cardId) return;

        const currentFront = li.querySelector('.cards-list-front').textContent;
        const currentBack = li.querySelector('.cards-list-back').textContent;
        const currentVerbInfinitive = li.getAttribute('data-verb-infinitive');

        const form = document.createElement('form');
        form.className = 'cards-inline-edit-form';

        const inputRow = document.createElement('div');
        inputRow.className = 'cards-input-row';
        inputRow.appendChild(buildEditInput('front', i18n.front, currentFront, i18n.frontPh));
        inputRow.appendChild(buildEditInput('back', i18n.back, currentBack, i18n.backPh));

        const formActions = document.createElement('div');
        formActions.className = 'cards-form-actions';
        const saveBtn = document.createElement('button');
        saveBtn.type = 'submit';
        saveBtn.className = 'btn btn-primary';
        saveBtn.textContent = i18n.save;
        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'btn btn-secondary';
        cancelBtn.textContent = i18n.cancel;
        formActions.appendChild(saveBtn);
        formActions.appendChild(cancelBtn);

        const errEl = document.createElement('div');
        errEl.className = 'cards-create-error';
        errEl.style.display = 'none';

        form.appendChild(inputRow);
        form.appendChild(formActions);
        form.appendChild(errEl);

        // Replace the row's contents while keeping the <li> in place.
        text.replaceWith(form);
        actions.remove();

        const frontInput = form.querySelector('input[name="front"]');
        frontInput.focus();
        frontInput.select();

        const restoreView = function (newFront, newBack, verbInfinitive) {
            const front = typeof newFront === 'string' ? newFront : currentFront;
            const back = typeof newBack === 'string' ? newBack : currentBack;
            const verbInf =
                arguments.length >= 3 ? verbInfinitive : currentVerbInfinitive;
            const newText = document.createElement('div');
            newText.className = 'cards-list-text';
            newText.appendChild(buildLine('front', i18n.front, front));
            newText.appendChild(buildLine('back', i18n.back, back));
            form.replaceWith(newText);
            li.appendChild(buildActions(cardId));
            applyVerbAffordance(li, verbInf);
            refreshImportAllCount();
        };

        cancelBtn.addEventListener('click', function () {
            restoreView();
        });

        form.addEventListener('submit', async function (ev) {
            ev.preventDefault();
            const newFront = form.querySelector('input[name="front"]').value.trim();
            const newBack = form.querySelector('input[name="back"]').value.trim();
            if (!newFront || !newBack) return;
            saveBtn.disabled = true;
            try {
                const response = await fetch('/api/cards/' + cardId, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ front: newFront, back: newBack })
                });
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    saveBtn.disabled = false;
                    errEl.textContent = data.error || 'Could not save';
                    errEl.style.display = '';
                    return;
                }
                if (data.duplicate) {
                    // Server kept the original card unchanged; close the edit
                    // row and let the user know nothing was applied.
                    restoreView(data.card.front, data.card.back, data.verb_infinitive);
                    showToast(i18n.duplicateEdit);
                    return;
                }
                restoreView(data.card.front, data.card.back, data.verb_infinitive);
                flash(li);
            } catch (err) {
                saveBtn.disabled = false;
                errEl.textContent = 'Network error — please try again';
                errEl.style.display = '';
            }
        });
    }

    function buildEditInput(name, labelText, value, placeholder) {
        const label = document.createElement('label');
        label.className = 'cards-input';
        const span = document.createElement('span');
        span.className = 'cards-input-label';
        span.textContent = labelText;
        const input = document.createElement('input');
        input.type = 'text';
        input.name = name;
        input.required = true;
        input.maxLength = 500;
        input.autocomplete = 'off';
        input.value = value;
        if (placeholder) input.placeholder = placeholder;
        label.appendChild(span);
        label.appendChild(input);
        return label;
    }

    function buildLine(side, labelText, value) {
        const line = document.createElement('div');
        line.className = 'cards-list-line';
        const label = document.createElement('span');
        label.className = 'cards-list-label cards-list-label-' + side;
        label.textContent = labelText;
        const val = document.createElement('span');
        val.className = 'cards-list-' + side;
        val.textContent = value;
        line.appendChild(label);
        line.appendChild(val);
        return line;
    }

    // ----- Add a card's verb to conjugation practice -----

    const importAllBtn = document.getElementById('cards-verbs-import-all');

    function refreshImportAllCount() {
        if (!importAllBtn) return;
        const remaining = findList()
            ? findList().querySelectorAll('.cards-verb-add-btn').length
            : 0;
        importAllBtn.setAttribute('data-count', String(remaining));
        if (remaining <= 0) {
            importAllBtn.classList.add('cards-verbs-import-all-hidden');
        } else {
            importAllBtn.classList.remove('cards-verbs-import-all-hidden');
            const tpl = importAllBtn.getAttribute('data-i18n-template') || '{n}';
            importAllBtn.textContent = tpl.replace('{n}', String(remaining));
        }
    }

    function clearVerbAffordances(li) {
        const btn = li.querySelector('.cards-verb-add-btn');
        if (btn) btn.remove();
        const badge = li.querySelector('.cards-verb-badge');
        if (badge) badge.remove();
        li.removeAttribute('data-verb-infinitive');
    }

    // Add the "verb" badge + "add to conjugation" button to a card row when the
    // server reports it as an importable verb. Idempotent: clears any existing
    // affordance first so it can also be used to refresh after an edit.
    function applyVerbAffordance(li, verbInfinitive) {
        clearVerbAffordances(li);
        if (!verbInfinitive) return;
        li.setAttribute('data-verb-infinitive', verbInfinitive);
        const frontLine = li.querySelector('.cards-list-line');
        if (frontLine) {
            const badge = document.createElement('span');
            badge.className = 'cards-verb-badge';
            badge.textContent = i18n.verbBadge;
            frontLine.appendChild(badge);
        }
        const actions = li.querySelector('.cards-list-actions');
        if (actions) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-secondary cards-list-btn cards-verb-add-btn';
            btn.setAttribute('data-infinitive', verbInfinitive);
            btn.textContent = i18n.verbAdd;
            actions.insertBefore(btn, actions.firstChild);
        }
    }

    // Per-card "add to conjugation" (event delegation).
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.cards-verb-add-btn');
        if (!btn) return;
        const li = btn.closest('.cards-list-item');
        const infinitive = (btn.getAttribute('data-infinitive') || '').trim();
        if (!li || !infinitive) return;
        btn.disabled = true;
        try {
            const res = await fetch('/api/verbs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ infinitive: infinitive })
            });
            const data = await res.json();
            if (!res.ok || !data.ok) {
                btn.disabled = false;
                return;
            }
            clearVerbAffordances(li);
            refreshImportAllCount();
            showToast(i18n.verbSynced);
        } catch (err) {
            btn.disabled = false;
        }
    });

    // Batch "add all card verbs to conjugation".
    if (importAllBtn) {
        importAllBtn.addEventListener('click', async function () {
            importAllBtn.disabled = true;
            try {
                const res = await fetch('/api/verbs/import-from-cards', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    importAllBtn.disabled = false;
                    return;
                }
                const list = findList();
                if (list) {
                    list.querySelectorAll('.cards-list-item').forEach(clearVerbAffordances);
                }
                const added = data.added || 0;
                importAllBtn.classList.add('cards-verbs-import-all-hidden');
                showToast(
                    added > 0
                        ? i18n.importDone.replace('{n}', String(added))
                        : i18n.importNone
                );
            } catch (err) {
                importAllBtn.disabled = false;
            }
        });
    }
})();
