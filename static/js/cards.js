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
        created: section.getAttribute('data-i18n-created') || 'Card added.'
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

    function buildCardLi(card) {
        const li = document.createElement('li');
        li.className = 'cards-list-item';
        li.setAttribute('data-card-id', String(card.id));

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

        const actions = buildActions(card.id);

        li.appendChild(text);
        li.appendChild(actions);
        return li;
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
            const li = buildCardLi(data.card);
            list.insertBefore(li, list.firstChild);
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

        const restoreView = function (newFront, newBack) {
            const front = typeof newFront === 'string' ? newFront : currentFront;
            const back = typeof newBack === 'string' ? newBack : currentBack;
            const newText = document.createElement('div');
            newText.className = 'cards-list-text';
            newText.appendChild(buildLine('front', i18n.front, front));
            newText.appendChild(buildLine('back', i18n.back, back));
            form.replaceWith(newText);
            li.appendChild(buildActions(cardId));
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
                restoreView(data.card.front, data.card.back);
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
})();
