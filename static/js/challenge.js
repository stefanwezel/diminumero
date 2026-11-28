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
        // Where a kind can't be had (no recordings, no verbs), back to the default.
        var fallback = form.querySelector('input[name="kind"][value="surprise"]');
        var verbs = form.querySelector('input[name="kind"][value="verbs"]');
        var nameInput = form.querySelector('input[name="name"]');
        // The logged-in person's first name, which the server offers in the
        // field. It is never kept here: logged out (or someone else at this
        // computer), the field must not show it.
        var loginName = nameInput ? nameInput.getAttribute('data-login-name') : null;
        var summary = document.getElementById('challenge-go-summary');
        // A verb challenge is made from the creator's own verbs: the language
        // radio says whether it has verb practice (data-conj) and, for someone
        // logged in, how many verbs they have in it (data-verbs).
        var verbsLogin = document.getElementById('challenge-verbs-login');
        var verbsEmpty = document.getElementById('challenge-verbs-empty');
        var verbsEmptyLink = document.getElementById('challenge-verbs-empty-link');
        var verbsFrom = document.getElementById('challenge-verbs-from');
        var tenses = document.getElementById('challenge-tenses');
        var easyOnly = form.querySelectorAll('[data-numbers-only]');

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

        // The tense checklist of one verb language, by its data-tenses-lang.
        var tenseLists = function () {
            return form.querySelectorAll('[data-tenses-lang]');
        };

        var load = function () {
            var saved = null;
            try { saved = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return; }
            if (!saved || typeof saved !== 'object') return;
            // A language, kind, difficulty or tense list in the URL was asked
            // for just now ("New challenge" after a round); it wins.
            if (!form.hasAttribute('data-lang-explicit')) choose('lang', saved.lang);
            // Which kinds can be picked depends on the language just restored.
            sync();
            if (!form.hasAttribute('data-kind-explicit')) choose('kind', saved.kind);
            if (!form.hasAttribute('data-difficulty-explicit')) choose('difficulty', saved.difficulty);
            var tensesAskedFor = form.getAttribute('data-tenses-explicit');
            // A name this browser remembers beats one guessed from the login
            // (the session that knew their chosen name may have ended); an
            // empty one doesn't, since it can't tell "none" from "never asked".
            var guessed = nameInput && nameInput.hasAttribute('data-name-suggested');
            var savedName = typeof saved.name === 'string' ? saved.name : null;
            // Kept before the login's name was left out: it's the login's still.
            if (savedName && loginName && savedName === loginName) savedName = '';
            if (nameInput && savedName !== null && (!nameInput.value || (guessed && savedName))) {
                nameInput.value = savedName.slice(0, nameInput.maxLength > 0 ? nameInput.maxLength : 24);
            }
            // Tenses per language: {es: ["indicativo/presente", …]}. A list
            // that no longer names any tense here is ignored, not applied as
            // "none ticked".
            var savedTenses = saved.tenses && typeof saved.tenses === 'object' ? saved.tenses : {};
            var savedOptional = saved.optional && typeof saved.optional === 'object' ? saved.optional : {};
            Array.prototype.forEach.call(tenseLists(), function (list) {
                var code = list.getAttribute('data-tenses-lang');
                if (code === tensesAskedFor) return;
                var keys = savedTenses[code];
                var boxes = list.querySelectorAll('input[name^="tenses_"]');
                if (Array.isArray(keys)) {
                    var known = Array.prototype.some.call(boxes, function (box) {
                        return keys.indexOf(box.value) !== -1;
                    });
                    if (known) {
                        Array.prototype.forEach.call(boxes, function (box) {
                            box.checked = keys.indexOf(box.value) !== -1;
                        });
                    }
                }
                var optional = list.querySelector('input[name^="include_vosotros_"]');
                if (optional && typeof savedOptional[code] === 'boolean') {
                    optional.checked = savedOptional[code];
                }
            });
        };

        var save = function () {
            var lang = checked('lang');
            var kind = checked('kind');
            var level = checked('difficulty');
            var savedTenses = {};
            var savedOptional = {};
            Array.prototype.forEach.call(tenseLists(), function (list) {
                var code = list.getAttribute('data-tenses-lang');
                savedTenses[code] = Array.prototype.map.call(
                    list.querySelectorAll('input[name^="tenses_"]:checked'),
                    function (box) { return box.value; }
                );
                var optional = list.querySelector('input[name^="include_vosotros_"]');
                if (optional) savedOptional[code] = optional.checked;
            });
            try {
                localStorage.setItem(KEY, JSON.stringify({
                    lang: lang ? lang.value : null,
                    kind: kind ? kind.value : null,
                    difficulty: level ? level.value : null,
                    name: nameInput && nameInput.value.trim() !== loginName ? nameInput.value.trim() : '',
                    tenses: savedTenses,
                    optional: savedOptional
                }));
            } catch (e) { /* storage blocked or full: nothing to remember */ }
        };

        var sync = function () {
            var lang = checked('lang');
            // No language picked yet: don't rule anything out.
            var hasListening = !lang || lang.getAttribute('data-listening') === '1';
            if (listening) {
                listening.disabled = !hasListening;
                if (!hasListening && listening.checked && fallback) fallback.checked = true;
            }
            if (note) note.hidden = hasListening;

            var hasConj = !!lang && lang.getAttribute('data-conj') === '1';
            var verbCount = lang ? lang.getAttribute('data-verbs') : null;
            var loggedIn = verbCount !== null;
            var canVerbs = hasConj && loggedIn && parseInt(verbCount, 10) > 0;
            if (verbs) {
                verbs.disabled = !canVerbs;
                if (!canVerbs && verbs.checked && fallback) fallback.checked = true;
            }
            if (verbsLogin) verbsLogin.hidden = !(hasConj && !loggedIn);
            if (verbsEmpty) verbsEmpty.hidden = !(hasConj && loggedIn && !canVerbs);
            if (verbsEmptyLink && hasConj) {
                verbsEmptyLink.href = lang.getAttribute('data-conjugate-url') || verbsEmptyLink.href;
            }

            var kind = checked('kind');
            var round = kind ? kind.value : 'numbers';
            var isVerbs = round === 'verbs';
            if (difficulty) difficulty.hidden = round === 'listening';
            // There's no multiple choice for verbs: Easy is a numbers mode.
            Array.prototype.forEach.call(easyOnly, function (label) {
                label.hidden = isVerbs;
                var input = label.querySelector('input');
                if (isVerbs && input && input.checked) choose('difficulty', 'advanced');
            });
            if (verbsFrom) verbsFrom.hidden = !isVerbs;
            if (tenses) tenses.hidden = !isVerbs;
            Array.prototype.forEach.call(tenseLists(), function (list) {
                list.hidden = !lang || list.getAttribute('data-tenses-lang') !== lang.value;
            });
            if (summary) {
                var parts = [labelText(lang), labelText(kind)];
                if (round === 'numbers' || isVerbs) parts.push(labelText(checked('difficulty')));
                summary.textContent = parts.filter(Boolean).join(' · ');
            }
        };

        form.addEventListener('change', function (e) {
            // A verb challenge needs a tense: the last one can't be unticked.
            var box = e.target;
            if (box && box.name && box.name.indexOf('tenses_') === 0 && !box.checked) {
                var list = box.closest('[data-tenses-lang]');
                if (list && !list.querySelector('input[name^="tenses_"]:checked')) box.checked = true;
            }
            sync();
        });

        // Which button submitted the form: e.submitter, where the browser has
        // it (null for a submit no button made). Safari before 15.4 has no
        // such property, so there the last submit button clicked stands in
        // (Enter in a field clicks the form's first one too). On the document,
        // because Start and Share sit outside the form (form="challenge-form").
        var clicked = null;
        document.addEventListener('click', function (e) {
            var btn = e.target.closest && e.target.closest('button, input[type="submit"]');
            clicked = btn && btn.type === 'submit' && btn.form === form ? btn : null;
        }, true);

        form.addEventListener('submit', function (e) {
            save();
            var submitter = 'submitter' in e ? e.submitter : clicked;
            clicked = null;
            var go = !!submitter && submitter.name === 'go';
            var kind = checked('kind');
            var round = kind ? kind.value : 'numbers';
            // Start on "Surprise me" is decided here rather than by the
            // server, so the round is known before the request goes. The pick
            // is a hidden field, never the radio, which must still read
            // "Surprise me" if Back returns to this page.
            var pick = form.querySelector('input[name="surprise_pick"]');
            if (pick) pick.parentNode.removeChild(pick);
            if (go && round === 'surprise') {
                var lang = checked('lang');
                var canListen = lang && lang.getAttribute('data-listening') === '1';
                round = canListen && Math.random() < 0.5 ? 'listening' : 'numbers';
                pick = document.createElement('input');
                pick.type = 'hidden';
                pick.name = 'surprise_pick';
                pick.value = round;
                form.appendChild(pick);
            }
            // Start on a Listening round goes through quiz_listen.js's pjax
            // (its listener is on .container, so it sees this attribute after
            // this listener has run): the click keeps the page user-activated,
            // which is what lets the first clip autoplay. Every other submit,
            // a numbers round included, is an ordinary POST, so the quiz page
            // loads with its own scripts, its notice and a Back to this form.
            if (go && round === 'listening') form.setAttribute('data-listen-pjax', '');
            else form.removeAttribute('data-listen-pjax');
        });

        sync();
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
