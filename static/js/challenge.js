// Friend challenges: the create form's dependent fields, its remembered
// defaults and Start/Share summary, and the share box. Everything here is an
// enhancement — the form posts and the link is readable and selectable
// without it.
(function () {
    'use strict';

    // ---- Create form ----
    var form = document.getElementById('challenge-form');
    if (form) {
        // The settings last used for a challenge, kept in this browser's
        // localStorage like the theme and the practice settings: they never
        // leave the device on their own, and they outlive the session cookie,
        // which (for anyone not logged in) is deleted with the browser.
        var KEY = 'diminumero:challenge_defaults';
        var note = document.getElementById('challenge-no-listening');
        var difficulty = document.getElementById('challenge-difficulty');
        var listening = form.querySelector('input[name="kind"][value="listening"]');
        var numbers = form.querySelector('input[name="kind"][value="numbers"]');
        var nameInput = form.querySelector('input[name="name"]');
        var summary = document.getElementById('challenge-go-summary');

        var checked = function (name) {
            return form.querySelector('input[name="' + name + '"]:checked');
        };
        // Check the radio in group `name` whose value is `value`, if one is.
        var choose = function (name, value) {
            if (typeof value !== 'string') return;
            var radios = form.querySelectorAll('input[name="' + name + '"]');
            for (var i = 0; i < radios.length; i++) {
                if (radios[i].value === value && !radios[i].disabled) {
                    radios[i].checked = true;
                    return;
                }
            }
        };
        var labelText = function (input) {
            var label = input && input.closest('label');
            return label ? label.textContent.replace(/\s+/g, ' ').trim() : '';
        };

        var load = function () {
            var saved = null;
            try { saved = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return; }
            if (!saved || typeof saved !== 'object') return;
            // A language in the URL was asked for just now; it wins.
            if (!form.hasAttribute('data-lang-explicit')) choose('lang', saved.lang);
            choose('kind', saved.kind);
            choose('difficulty', saved.difficulty);
            if (nameInput && !nameInput.value && typeof saved.name === 'string') {
                nameInput.value = saved.name.slice(0, nameInput.maxLength > 0 ? nameInput.maxLength : 24);
            }
        };

        var save = function () {
            var lang = checked('lang');
            var kind = checked('kind');
            var level = checked('difficulty');
            try {
                localStorage.setItem(KEY, JSON.stringify({
                    lang: lang ? lang.value : null,
                    kind: kind ? kind.value : null,
                    difficulty: level ? level.value : null,
                    name: nameInput ? nameInput.value.trim() : ''
                }));
            } catch (e) { /* storage blocked or full: nothing to remember */ }
        };

        var sync = function () {
            var lang = checked('lang');
            // No language picked yet: don't rule anything out.
            var hasListening = !lang || lang.getAttribute('data-listening') === '1';
            if (listening) {
                listening.disabled = !hasListening;
                if (!hasListening && listening.checked && numbers) numbers.checked = true;
            }
            if (note) note.hidden = hasListening;
            var kind = checked('kind');
            var isNumbers = !kind || kind.value === 'numbers';
            if (difficulty) difficulty.hidden = !!(kind && kind.value === 'listening');
            if (summary) {
                var parts = [labelText(lang), labelText(kind)];
                if (isNumbers) parts.push(labelText(checked('difficulty')));
                summary.textContent = parts.filter(Boolean).join(' · ');
            }
        };

        form.addEventListener('change', sync);

        form.addEventListener('submit', function (e) {
            save();
            // Start on a round that may be Listening goes through
            // quiz_listen.js's pjax (its listener is on .container, so it sees
            // this attribute after this listener has run): the click keeps the
            // page user-activated, which is what lets the first clip autoplay.
            // Every other submit is an ordinary POST.
            var go = e.submitter && e.submitter.name === 'go';
            var kind = checked('kind');
            var mayListen = kind && (kind.value === 'listening' || kind.value === 'surprise');
            if (go && mayListen) form.setAttribute('data-listen-pjax', '');
            else form.removeAttribute('data-listen-pjax');
        });

        load();
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

    // Arrived by pressing Share: the link is what they came for. Put focus on
    // the phone's share button (or Copy link), one tap away; no page may open
    // the share sheet by itself.
    if (box && box.hasAttribute('data-share-focus')) {
        var target = shareBtn && !shareBtn.hidden ? shareBtn : copyBtn;
        if (target) {
            try { target.focus({ preventScroll: false }); } catch (e) { target.focus(); }
        }
    }
})();
