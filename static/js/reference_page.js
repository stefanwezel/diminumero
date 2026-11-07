/**
 * The interactive parts of a reference page: per-number audio, the self-test,
 * the number lookup and the print button. All of it reads the page's own tables,
 * so it needs no account, no session and no request beyond the MP3s.
 *
 * Everything here is an enhancement. The sections it drives are `hidden` until
 * it runs, and the tables and links underneath work without it.
 */
(function () {
    'use strict';

    const root = document.querySelector('[data-ref-page]');
    if (!root) return;
    root.classList.add('ref-js');

    const audioBase = root.getAttribute('data-audio-base');
    let player = null;

    function play(number) {
        if (!audioBase) return;
        if (!player) player = new Audio();
        player.pause();
        player.src = audioBase + number + '.mp3';
        player.play().catch(function () { /* autoplay refused; the button still works */ });
    }

    root.addEventListener('click', function (event) {
        const button = event.target.closest('.ref-play');
        if (button) play(button.getAttribute('data-n'));
    });

    // Mirrors normalize_text() in quiz_logic.py, so the test here accepts what a
    // real drill accepts (ASCII for umlauts and accents).
    function normalize(text) {
        return text.toLowerCase().trim()
            .replace(/ü/g, 'ue').replace(/ö/g, 'oe').replace(/ä/g, 'ae')
            .replace(/ß/g, 'ss').replace(/ı/g, 'i')
            .split(/\s+/).join(' ')
            .normalize('NFD').replace(/\p{Mn}/gu, '');
    }

    function initQuiz(quiz) {
        const items = Array.from(root.querySelectorAll('.ref-word[data-q]'));
        if (!items.length) return;

        const listenItems = items.filter(function (cell) {
            return cell.closest('tr').querySelector('.ref-play');
        });
        const prompt = quiz.querySelector('[data-ref-quiz-prompt]');
        const form = quiz.querySelector('[data-ref-quiz-form]');
        const input = quiz.querySelector('[data-ref-quiz-input]');
        const submit = quiz.querySelector('[data-ref-quiz-submit]');
        const feedback = quiz.querySelector('[data-ref-quiz-feedback]');
        const scoreLine = quiz.querySelector('[data-ref-quiz-score]');
        const replay = quiz.querySelector('[data-ref-quiz-replay]');
        const modeButtons = quiz.querySelectorAll('[data-ref-quiz-mode]');
        const wordLang = input.getAttribute('lang');

        let mode = 'type';
        let current = null;
        let answered = false;
        let correct = 0;
        let asked = 0;

        function askNext(takeFocus) {
            const pool = mode === 'listen' ? listenItems : items;
            let next = current;
            while (next === current && pool.length > 1) {
                next = pool[Math.floor(Math.random() * pool.length)];
            }
            current = next || pool[0];
            answered = false;

            const listening = mode === 'listen';
            prompt.textContent = listening ? '' : current.getAttribute('data-q');
            if (replay) replay.hidden = !listening;
            if (listening) play(current.getAttribute('data-q'));

            input.value = '';
            input.inputMode = listening ? 'numeric' : 'text';
            if (listening) input.removeAttribute('lang');
            else input.setAttribute('lang', wordLang);
            feedback.textContent = '';
            feedback.className = 'ref-quiz-feedback';
            submit.textContent = quiz.getAttribute('data-i18n-check');
            // Not on page load: that would scroll a visitor away from the top.
            if (takeFocus) input.focus();
        }

        function isCorrect(value) {
            if (mode === 'listen') {
                return value.replace(/\D/g, '') === current.getAttribute('data-q');
            }
            const alternatives = (current.getAttribute('data-alt') || '').split('|');
            return [current.textContent].concat(alternatives)
                .filter(Boolean)
                .map(normalize)
                .includes(normalize(value));
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            if (answered) {
                askNext(true);
                return;
            }
            if (!input.value.trim()) return;

            const right = isCorrect(input.value);
            answered = true;
            asked += 1;
            if (right) correct += 1;

            feedback.textContent = right
                ? quiz.getAttribute('data-i18n-correct')
                : quiz.getAttribute('data-i18n-wrong') + ' ' + current.textContent.trim();
            feedback.className = 'ref-quiz-feedback ' + (right ? 'is-correct' : 'is-wrong');
            submit.textContent = quiz.getAttribute('data-i18n-next');

            let score = quiz.getAttribute('data-i18n-score');
            [correct, asked].forEach(function (value) {
                score = score.replace('{}', value);
            });
            scoreLine.textContent = score;
        });

        if (replay) {
            replay.addEventListener('click', function () {
                play(current.getAttribute('data-q'));
            });
        }

        modeButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                mode = button.getAttribute('data-ref-quiz-mode');
                modeButtons.forEach(function (other) {
                    const active = other === button;
                    other.classList.toggle('active', active);
                    other.setAttribute('aria-pressed', active ? 'true' : 'false');
                });
                askNext(true);
            });
        });

        if (!listenItems.length) {
            modeButtons.forEach(function (button) { button.hidden = true; });
        }

        quiz.hidden = false;
        askNext(false);
    }

    function initLookup(lookup) {
        const form = lookup.querySelector('[data-ref-lookup-form]');
        const input = lookup.querySelector('[data-ref-lookup-input]');
        const result = lookup.querySelector('[data-ref-lookup-result]');

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            result.textContent = '';

            const value = input.value.replace(/[\s.,]/g, '');
            const cell = /^\d+$/.test(value)
                ? root.querySelector('.ref-word[data-q="' + parseInt(value, 10) + '"]')
                : null;
            if (!cell) {
                result.textContent = root.getAttribute('data-i18n-lookup-invalid');
                return;
            }

            const word = document.createElement('strong');
            word.textContent = cell.textContent.trim();
            word.setAttribute('lang', cell.closest('[lang]').getAttribute('lang'));
            result.appendChild(word);

            const button = cell.closest('tr').querySelector('.ref-play');
            if (button) {
                result.appendChild(document.createTextNode(' '));
                result.appendChild(button.cloneNode(true));
            }
        });

        lookup.hidden = false;
    }

    const quiz = root.querySelector('[data-ref-quiz]');
    if (quiz) initQuiz(quiz);

    const lookup = root.querySelector('[data-ref-lookup]');
    if (lookup) initLookup(lookup);

    const printButton = root.querySelector('[data-ref-print]');
    if (printButton) {
        printButton.hidden = false;
        printButton.addEventListener('click', function () { window.print(); });
    }
}());
