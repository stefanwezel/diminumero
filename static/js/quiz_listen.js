// Listening quiz: keep the page as a single living document and advance
// questions via fetch instead of full-page navigation. Because every
// transition is triggered by a user gesture (Start / a digit / Next), the
// document keeps its "user activation", so audio.play() is always allowed —
// this is what makes the mp3 autoplay reliably, like a YouTube video.
(function () {
    'use strict';

    var container = document.querySelector('.container');
    if (!container) return;

    var MAX_DIGITS = 9;

    // ---- audio ----
    // This controller is the *only* thing that starts a clip. The <audio> tag
    // deliberately carries no `autoplay`, because the browser honouring that
    // attribute and the code below were two independent starters racing each
    // other: the browser began the clip, then START_LAG_MS later this code
    // rewound it to 0. The recordings have only ~0-155ms of room tone before
    // the speech, so that rewind landed on or just after the onset and you
    // heard the number restart mid-word — audible on a phone (whose decoder
    // reaches the word by then) and usually not on a laptop.
    var START_LAG_MS = 150;
    // A clip is ~20KB, so it is normally buffered long before this; the cap is
    // only so a bad connection still gets its question rather than silence.
    var BUFFER_WAIT_MS = 1200;

    var pendingTimer = null;
    var pendingWait = null;

    function cancelPendingPlay() {
        if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
        if (pendingWait) {
            pendingWait.el.removeEventListener('canplaythrough', pendingWait.fn);
            pendingWait.el.removeEventListener('error', pendingWait.fn);
            pendingWait = null;
        }
    }

    function playAudio() {
        var audio = document.getElementById('audio-el');
        if (!audio) return;
        // A second tap on play/replay, or a swap arriving over a queued start,
        // must not leave two starts in flight.
        cancelPendingPlay();

        var started = false;
        var start = function () {
            if (started) return;
            started = true;
            cancelPendingPlay();
            // Only a replay needs rewinding: a freshly rendered element is
            // already at 0, and an unnecessary seek is exactly what makes a
            // mobile decoder hiccup.
            if (audio.currentTime > 0) {
                try { audio.currentTime = 0; } catch (e) {}
            }
            var p = audio.play();
            if (p && typeof p.catch === 'function') p.catch(function () {});
        };

        // A deliberate lag so the audio doesn't start the very instant the
        // question appears, then however long buffering still needs.
        pendingTimer = setTimeout(function () {
            pendingTimer = null;
            // HAVE_ENOUGH_DATA. The old gate was HAVE_CURRENT_DATA, which
            // promises only the current frame — on a phone the buffer can run
            // dry a few frames in, which stutters too.
            if (audio.readyState >= 4) { start(); return; }
            pendingWait = { el: audio, fn: start };
            audio.addEventListener('canplaythrough', start, { once: true });
            audio.addEventListener('error', start, { once: true });
            pendingTimer = setTimeout(start, BUFFER_WAIT_MS);
        }, START_LAG_MS);
    }

    // ---- numpad input (looked up live so it survives content swaps) ----
    function input() { return document.getElementById('answerInput'); }
    function renderDisplay() {
        var el = input();
        var display = document.getElementById('numpadDisplay');
        if (el && display) display.textContent = el.value.length ? el.value : ' ';
    }
    function setValue(v) {
        var el = input();
        if (el) { el.value = v; renderDisplay(); }
    }
    function appendDigit(d) {
        var el = input();
        if (!el || el.value.length >= MAX_DIGITS) return;
        setValue(el.value + d);
    }

    // ---- toasts (mirror static/js/quiz.js auto-hide for swapped-in toasts) ----
    function refreshToasts(doc) {
        document.querySelectorAll('body > .toast').forEach(function (t) { t.remove(); });
        if (doc) {
            doc.querySelectorAll('.toast').forEach(function (t) { document.body.appendChild(t); });
        }
        document.querySelectorAll('.toast').forEach(function (toast) {
            setTimeout(function () { toast.remove(); }, 3000);
        });
    }

    // ---- pjax ----
    function swapFrom(html, url) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        // Anything that isn't a listening-quiz page (e.g. the results page) is a
        // terminal navigation. Use replace() so the finished listening entry is
        // discarded — otherwise "back" from results would return to a stale
        // (already completed) listening page.
        if (!doc.querySelector('.quiz-page')) {
            window.location.replace(url);
            return;
        }
        // Stop the outgoing clip before its element is destroyed. Removing a
        // playing <audio> pauses it eventually rather than immediately, and on
        // a phone that tail overlaps the incoming clip.
        var leaving = document.getElementById('audio-el');
        if (leaving) { try { leaving.pause(); } catch (e) {} }
        cancelPendingPlay();

        var newContainer = doc.querySelector('.container');
        container.innerHTML = newContainer ? newContainer.innerHTML : '';
        if (url) {
            try {
                var newPath = new URL(url, window.location.href).pathname;
                var curPath = window.location.pathname;
                if (newPath === curPath) {
                    // In-session transition (answer / reveal / next): collapse
                    // into a single history entry so the whole listening run is
                    // one "back" step, not one per question.
                    history.replaceState({ listen: true }, '', url);
                } else {
                    // Entering the listening quiz from another page (mode page,
                    // landing, or results). Anchor the back button to the
                    // language's mode page so "back" is consistent no matter
                    // where listening was launched from.
                    var modeUrl = newPath.replace(/\/listen(\/.*)?$/, '') || '/';
                    if (modeUrl !== curPath) {
                        history.replaceState(null, '', modeUrl);
                    }
                    history.pushState({ listen: true }, '', url);
                }
            } catch (e) {}
        }
        refreshToasts(doc);
        renderDisplay();
        var next = document.querySelector('.reveal-modal-next');
        if (next) next.focus();
        playAudio();
    }

    function pjaxSubmit(form, submitter) {
        var method = (form.method || 'GET').toUpperCase();
        var opts = { method: method, headers: { 'X-Requested-With': 'fetch' } };
        if (method === 'POST') {
            // FormData doesn't include the submit button's name/value on its
            // own, so the reveal/next buttons (which signal intent via their
            // name) would otherwise be lost and the POST would fall through to
            // the answer branch. Append the submitter explicitly.
            var fd = new FormData(form);
            if (submitter && submitter.name) fd.append(submitter.name, submitter.value);
            opts.body = fd;
        }
        fetch(form.action, opts)
            .then(function (resp) {
                return resp.text().then(function (text) { return { url: resp.url, text: text }; });
            })
            .then(function (r) { swapFrom(r.text, r.url); })
            .catch(function () { form.submit(); });
    }

    // ---- delegated listeners (bound once; survive content swaps) ----
    container.addEventListener('click', function (e) {
        var digit = e.target.closest('[data-digit]');
        if (digit) { appendDigit(digit.getAttribute('data-digit')); return; }
        if (e.target.closest('#numpadBack')) {
            var el = input();
            if (el) setValue(el.value.slice(0, -1));
            return;
        }
        if (e.target.closest('#audio-play-btn') || e.target.closest('#audio-replay-btn')) {
            playAudio();
        }
    });

    container.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.matches || !form.matches('[data-listen-pjax]')) return;
        if (form.id === 'answerForm') {
            var el = input();
            if (!el || !el.value) { e.preventDefault(); return; }
        }
        e.preventDefault();
        pjaxSubmit(form, e.submitter);
    });

    document.addEventListener('keydown', function (e) {
        var form = document.getElementById('answerForm');
        if (!form) return;
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
        if (e.key >= '0' && e.key <= '9') {
            appendDigit(e.key);
            e.preventDefault();
        } else if (e.key === 'Backspace') {
            var el = input();
            if (el) setValue(el.value.slice(0, -1));
            e.preventDefault();
        } else if (e.key === 'Enter') {
            var el2 = input();
            if (el2 && el2.value) {
                if (form.requestSubmit) form.requestSubmit();
                else pjaxSubmit(form);
            }
            e.preventDefault();
        }
    });

    // A back/forward navigation can't be reconstructed from session state
    // client-side, so fall back to a real load.
    window.addEventListener('popstate', function () { window.location.reload(); });

    // initial page
    renderDisplay();
    playAudio();
})();
