// Friend challenges: the create form's dependent fields, and the share box.
// Everything here is an enhancement — the form posts and the link is readable
// and selectable without it.
(function () {
    'use strict';

    // ---- Create form ----
    var form = document.getElementById('challenge-form');
    if (form) {
        var note = document.getElementById('challenge-no-listening');
        var difficulty = document.getElementById('challenge-difficulty');
        var listening = form.querySelector('input[name="kind"][value="listening"]');
        var numbers = form.querySelector('input[name="kind"][value="numbers"]');

        var sync = function () {
            var lang = form.querySelector('input[name="lang"]:checked');
            // No language picked yet: don't rule anything out.
            var hasListening = !lang || lang.getAttribute('data-listening') === '1';
            if (listening) {
                listening.disabled = !hasListening;
                if (!hasListening && listening.checked && numbers) numbers.checked = true;
            }
            if (note) note.hidden = hasListening;
            var kind = form.querySelector('input[name="kind"]:checked');
            if (difficulty) difficulty.hidden = !!(kind && kind.value === 'listening');
        };
        form.addEventListener('change', sync);
        sync();
    }

    // ---- Share box ----
    var url = document.getElementById('challenge-share-url');
    if (!url) return;
    var box = url.closest('[data-share-text]');
    var text = box ? box.getAttribute('data-share-text') : '';
    var copyBtn = document.getElementById('challenge-share-copy');
    var shareBtn = document.getElementById('challenge-share-native');

    url.addEventListener('focus', function () { url.select(); });

    // The phone's own share sheet (WhatsApp, Messages…) where there is one.
    if (shareBtn && navigator.share) {
        shareBtn.hidden = false;
        shareBtn.addEventListener('click', function () {
            navigator.share({ title: 'diminumero', text: text, url: url.value })
                .catch(function () { /* dismissed */ });
        });
    }

    if (copyBtn) {
        var labels = {
            copy: copyBtn.getAttribute('data-i18n-copy') || 'Copy link',
            copied: copyBtn.getAttribute('data-i18n-copied') || 'Copied!'
        };
        var done = function () {
            copyBtn.textContent = labels.copied;
            setTimeout(function () { copyBtn.textContent = labels.copy; }, 1600);
        };
        var fallback = function () {
            url.select();
            try { document.execCommand('copy'); done(); } catch (e) { /* noop */ }
        };
        copyBtn.addEventListener('click', function () {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url.value).then(done, fallback);
            } else {
                fallback();
            }
        });
    }
})();
