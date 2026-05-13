/**
 * Client-side sort for the /cards list. Persists the chosen option in
 * localStorage and re-applies on every load (including bfcache restores),
 * mirroring how cards_practice_prefs.js keeps the radio selections sticky.
 *
 * Unpracticed cards have no score; for "score lowest first" they are
 * treated as 0 (weakest first) to match the prioritized sampling strategy
 * in app.py — see _pick_weighted_card.
 */
(function () {
    'use strict';

    var KEY = 'diminumero:card_sort';
    var DEFAULT_SORT = 'created_desc';
    var ALLOWED = ['created_desc', 'times_practiced_desc', 'score_asc'];

    var select = document.getElementById('cards-sort-select');
    if (!select) return;

    function readStored() {
        try {
            var v = localStorage.getItem(KEY);
            if (v && ALLOWED.indexOf(v) !== -1) return v;
        } catch (e) { /* ignore */ }
        return DEFAULT_SORT;
    }

    function writeStored(v) {
        try { localStorage.setItem(KEY, v); } catch (e) { /* ignore */ }
    }

    function findList() {
        return document.querySelector('[data-cards-list]');
    }

    function getCreatedAt(li) {
        return li.getAttribute('data-created-at') || '';
    }

    function getTimesPracticed(li) {
        var p = li.querySelector('.cards-progress');
        if (!p) return 0;
        return parseInt(p.getAttribute('data-practiced') || '0', 10) || 0;
    }

    function getScoreForSort(li) {
        var p = li.querySelector('.cards-progress');
        if (!p) return 0;
        var raw = p.getAttribute('data-score');
        if (raw === null || raw === '') return 0;
        var n = parseFloat(raw);
        return isNaN(n) ? 0 : n;
    }

    function compare(sort, a, b) {
        if (sort === 'times_practiced_desc') {
            var diff = getTimesPracticed(b) - getTimesPracticed(a);
            if (diff !== 0) return diff;
            // Tiebreak: newest first, so order stays stable & intuitive.
            return getCreatedAt(a) < getCreatedAt(b) ? 1 : -1;
        }
        if (sort === 'score_asc') {
            var sDiff = getScoreForSort(a) - getScoreForSort(b);
            if (sDiff !== 0) return sDiff;
            return getCreatedAt(a) < getCreatedAt(b) ? 1 : -1;
        }
        // created_desc (default)
        var ca = getCreatedAt(a), cb = getCreatedAt(b);
        if (ca === cb) return 0;
        return ca < cb ? 1 : -1;
    }

    function applySort() {
        var list = findList();
        if (!list) return;
        var sort = readStored();
        if (select.value !== sort) select.value = sort;
        var items = Array.prototype.slice.call(
            list.querySelectorAll('.cards-list-item')
        );
        items.sort(function (a, b) { return compare(sort, a, b); });
        var frag = document.createDocumentFragment();
        items.forEach(function (li) { frag.appendChild(li); });
        list.appendChild(frag);
    }

    select.value = readStored();
    applySort();
    window.addEventListener('pageshow', applySort);

    select.addEventListener('change', function () {
        if (ALLOWED.indexOf(select.value) === -1) {
            select.value = DEFAULT_SORT;
        }
        writeStored(select.value);
        applySort();
    });

    // cards.js calls this after creating a new card so the new <li> moves
    // into the right position under the active sort instead of always
    // staying at the top.
    window.diminumeroCardsApplySort = applySort;
})();
