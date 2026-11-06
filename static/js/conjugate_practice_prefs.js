(function () {
    'use strict';

    var SAMPLING_MODES = ['prioritized', 'random'];
    var DIFFICULTIES = ['advanced', 'hardcore'];

    var form = document.querySelector('.conjugate-practice-form');
    if (!form) return;

    // Per language: tense keys differ between languages, so one language's
    // saved list would untick every box on another's page, then get saved back.
    var LEGACY_KEY = 'diminumero:conjugate_practice_prefs';
    var KEY = LEGACY_KEY + ':' + form.getAttribute('data-lang');

    // Set while we re-render after a reset, so the change event we dispatch for
    // the insights matrix doesn't re-persist the defaults we just cleared.
    var suppressSave = false;

    // Stop the browser from auto-restoring stale radio/checkbox state on
    // refresh, which otherwise wins against our value-setting after load.
    form.setAttribute('autocomplete', 'off');

    function tenseInputs() {
        return Array.prototype.slice.call(
            form.querySelectorAll('input[type="checkbox"][name="tenses"]')
        );
    }

    function vosotrosInput() {
        return form.querySelector('input[type="checkbox"][name="include_vosotros"]');
    }

    function setRadio(name, value, allowed) {
        if (allowed.indexOf(value) === -1) return;
        var input = form.querySelector(
            'input[type="radio"][name="' + name + '"][value="' + value + '"]'
        );
        if (input) input.checked = true;
    }

    function setCount(value) {
        var n = parseInt(value, 10);
        if (isNaN(n) || n < 1 || n > 100) return;
        var input = form.querySelector('input[type="number"][name="count"]');
        if (input) input.value = String(n);
    }

    // Settings used to live under one key shared by every language. Hand them to
    // the first page opened since, keeping the tense list only if it's that
    // page's own, and drop the old key.
    function migrateLegacyPrefs() {
        try {
            var raw = localStorage.getItem(LEGACY_KEY);
            if (raw === null) return;
            localStorage.removeItem(LEGACY_KEY);
            if (localStorage.getItem(KEY) !== null) return;
            var saved = JSON.parse(raw);
            if (!saved || typeof saved !== 'object') return;
            if (Array.isArray(saved.tenses)) {
                var own = tenseInputs().map(function (input) { return input.value; });
                saved.tenses = saved.tenses.filter(function (tense) {
                    return own.indexOf(tense) !== -1;
                });
                if (!saved.tenses.length) delete saved.tenses;
            }
            localStorage.setItem(KEY, JSON.stringify(saved));
        } catch (e) {
            // Storage unavailable or the old entry unreadable: defaults apply.
        }
    }

    function applyPrefs() {
        var raw;
        try { raw = localStorage.getItem(KEY); } catch (e) { return; }
        if (!raw) return;
        var saved;
        try { saved = JSON.parse(raw); } catch (e) { return; }
        if (!saved || typeof saved !== 'object') return;

        if (Array.isArray(saved.tenses)) {
            tenseInputs().forEach(function (input) {
                input.checked = saved.tenses.indexOf(input.value) !== -1;
            });
        }
        var vos = vosotrosInput();
        if (vos && typeof saved.include_vosotros === 'boolean') {
            vos.checked = saved.include_vosotros;
        }
        setRadio('difficulty', saved.difficulty, DIFFICULTIES);
        setRadio('sampling_mode', saved.sampling_mode, SAMPLING_MODES);
        setCount(saved.count);
        notifyChange();
    }

    // Let other listeners (the live insights matrix in conjugate.js) react to
    // state we set programmatically, which doesn't fire native change events.
    function notifyChange() {
        form.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function save() {
        if (suppressSave) return;
        try {
            var data = new FormData(form);
            var vos = vosotrosInput();
            localStorage.setItem(KEY, JSON.stringify({
                tenses: data.getAll('tenses'),
                include_vosotros: !!(vos && vos.checked),
                difficulty: data.get('difficulty'),
                sampling_mode: data.get('sampling_mode'),
                count: data.get('count')
            }));
        } catch (e) {
            // Storage unavailable (private mode, quota, etc.) — ignore.
        }
    }

    function resetDefaults() {
        // Restore each control to the server-rendered default (the HTML
        // `checked`/`value` attributes, reflected by defaultChecked/defaultValue).
        tenseInputs().forEach(function (input) {
            input.checked = input.defaultChecked;
        });
        var vos = vosotrosInput();
        if (vos) vos.checked = vos.defaultChecked;
        Array.prototype.slice.call(
            form.querySelectorAll('input[type="radio"]')
        ).forEach(function (input) {
            input.checked = input.defaultChecked;
        });
        var count = form.querySelector('input[type="number"][name="count"]');
        if (count) count.value = count.defaultValue;
        // Drop the saved prefs so a later visit falls back to these defaults.
        try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
        suppressSave = true;
        notifyChange();
        suppressSave = false;
    }

    var resetBtn = form.querySelector('.conjugate-practice-reset');
    if (resetBtn) resetBtn.addEventListener('click', resetDefaults);

    migrateLegacyPrefs();
    applyPrefs();
    // pageshow fires on initial load AND when restored from Firefox bfcache.
    window.addEventListener('pageshow', applyPrefs);

    // Save whenever the user touches any input in the form.
    form.addEventListener('change', save);
    form.addEventListener('input', save);
})();
