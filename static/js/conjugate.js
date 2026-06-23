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
        popupTitle: addSection.getAttribute('data-i18n-popup-title') || 'Verb not supported'
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

    function buildVerbLi(verb) {
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
                list.insertBefore(buildVerbLi(data.verb), list.firstChild);
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
}());
