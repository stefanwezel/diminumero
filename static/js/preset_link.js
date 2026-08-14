/**
 * Shareable drill links. Builds a preset URL from the selections on the
 * number-practice config screen (mode + range + the magnitude dial) so a
 * teacher can paste one link into Moodle or Teams and a student lands
 * straight in the configured drill.
 *
 * The same range also feeds the hidden inputs of the three Start forms, so
 * pressing Start here gives the teacher exactly what their link produces.
 */
(function () {
    'use strict';

    const root = document.getElementById('preset-share');
    if (!root) return;

    const urlField = document.getElementById('preset-share-url');
    const copyBtn = document.getElementById('preset-share-copy');
    const minInput = document.getElementById('preset-range-min');
    const maxInput = document.getElementById('preset-range-max');
    const slider = document.getElementById('magnitude-slider');
    const modeInputs = root.querySelectorAll('input[name="preset-mode"]');
    const rangeHiddenInputs = document.querySelectorAll('.preset-range-hidden-input');

    const baseUrl = root.getAttribute('data-base-url') || window.location.href;
    const deckMin = parseInt(root.getAttribute('data-deck-min'), 10);
    const deckMax = parseInt(root.getAttribute('data-deck-max'), 10);

    const labels = {
        copy: copyBtn ? (copyBtn.getAttribute('data-i18n-copy') || 'Copy link') : '',
        copied: copyBtn ? (copyBtn.getAttribute('data-i18n-copied') || 'Copied!') : ''
    };

    function selectedMode() {
        for (let i = 0; i < modeInputs.length; i++) {
            if (modeInputs[i].checked) return modeInputs[i].value;
        }
        return 'easy';
    }

    function clamp(value, low, high) {
        return Math.min(Math.max(value, low), high);
    }

    /** The range as "lo-hi", or '' when it covers the whole deck. */
    function rangeValue() {
        const rawMin = minInput ? minInput.value.trim() : '';
        const rawMax = maxInput ? maxInput.value.trim() : '';
        if (!rawMin && !rawMax) return '';

        let low = rawMin === '' ? deckMin : parseInt(rawMin, 10);
        let high = rawMax === '' ? deckMax : parseInt(rawMax, 10);
        if (isNaN(low)) low = deckMin;
        if (isNaN(high)) high = deckMax;

        low = clamp(low, deckMin, deckMax);
        high = clamp(high, deckMin, deckMax);
        if (low > high) { const swap = low; low = high; high = swap; }

        if (low === deckMin && high === deckMax) return '';
        return low + '-' + high;
    }

    function render() {
        const params = ['mode=' + encodeURIComponent(selectedMode())];
        const range = rangeValue();
        if (range) params.push('range=' + encodeURIComponent(range));
        if (slider) params.push('magnitude=' + encodeURIComponent(slider.value));

        if (urlField) urlField.value = baseUrl + '?' + params.join('&');

        // Keep the Start buttons on this page in step with the link.
        for (let i = 0; i < rangeHiddenInputs.length; i++) {
            rangeHiddenInputs[i].value = range;
        }
    }

    function onCopy() {
        if (!urlField) return;
        const done = function () {
            copyBtn.textContent = labels.copied;
            setTimeout(function () { copyBtn.textContent = labels.copy; }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(urlField.value).then(done, function () {
                urlField.select();
            });
        } else {
            urlField.select();
            try { document.execCommand('copy'); done(); } catch (e) { /* noop */ }
        }
    }

    for (let i = 0; i < modeInputs.length; i++) {
        modeInputs[i].addEventListener('change', render);
    }
    if (minInput) minInput.addEventListener('input', render);
    if (maxInput) maxInput.addEventListener('input', render);
    if (slider) slider.addEventListener('input', render);
    if (urlField) urlField.addEventListener('focus', function () { urlField.select(); });
    if (copyBtn) copyBtn.addEventListener('click', onCopy);

    render();
}());
