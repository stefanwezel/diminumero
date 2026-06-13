(function () {
    'use strict';

    var KEY = 'diminumero:card_practice_prefs';
    var DIRECTIONS = ['back_to_front', 'front_to_back', 'random'];
    var SAMPLING_MODES = ['prioritized', 'random'];
    var DIFFICULTIES = ['hardcore', 'advanced'];
    var REVEAL_MODES = ['type', 'click'];
    // Single source of truth for the form defaults, mirroring the `checked`
    // radios / count in templates/cards.html and the server-side fallbacks in
    // cards_practice_start().
    var DEFAULTS = {
        direction: 'back_to_front',
        sampling_mode: 'prioritized',
        difficulty: 'advanced',
        reveal_mode: 'type',
        count: '10'
    };

    var form = document.querySelector('.cards-practice-form');
    if (!form) return;

    // Stop the browser from auto-restoring stale radio state on refresh,
    // which otherwise wins against our value-setting after page load.
    form.setAttribute('autocomplete', 'off');

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

    function applyPrefs() {
        var raw;
        try { raw = localStorage.getItem(KEY); } catch (e) { return; }
        if (!raw) return;
        var saved;
        try { saved = JSON.parse(raw); } catch (e) { return; }
        if (!saved || typeof saved !== 'object') return;
        setRadio('direction', saved.direction, DIRECTIONS);
        setRadio('sampling_mode', saved.sampling_mode, SAMPLING_MODES);
        setRadio('difficulty', saved.difficulty, DIFFICULTIES);
        setRadio('reveal_mode', saved.reveal_mode, REVEAL_MODES);
        setCount(saved.count);
    }

    function save() {
        try {
            var data = new FormData(form);
            localStorage.setItem(KEY, JSON.stringify({
                direction: data.get('direction'),
                sampling_mode: data.get('sampling_mode'),
                difficulty: data.get('difficulty'),
                reveal_mode: data.get('reveal_mode'),
                count: data.get('count')
            }));
        } catch (e) {
            // Storage unavailable (private mode, quota, etc.) — ignore.
        }
    }

    function resetDefaults() {
        setRadio('direction', DEFAULTS.direction, DIRECTIONS);
        setRadio('sampling_mode', DEFAULTS.sampling_mode, SAMPLING_MODES);
        setRadio('difficulty', DEFAULTS.difficulty, DIFFICULTIES);
        setRadio('reveal_mode', DEFAULTS.reveal_mode, REVEAL_MODES);
        setCount(DEFAULTS.count);
        // Drop the saved prefs so a later visit falls back to these defaults.
        try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    }

    var resetBtn = form.querySelector('.cards-practice-reset');
    if (resetBtn) resetBtn.addEventListener('click', resetDefaults);

    applyPrefs();
    // pageshow fires on initial load AND when restored from Firefox bfcache.
    window.addEventListener('pageshow', applyPrefs);

    // Save whenever the user touches any input in the form.
    form.addEventListener('change', save);
    form.addEventListener('input', save);
})();
