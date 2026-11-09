/* Plain spoken text, without model-specific markup or external requests. */
(function () {
    'use strict';

    const digits = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
    const spellDigits = text => text.replace(/[0-9]/g, digit => ` ${digits[Number(digit)]} `)
        .replace(/ +/g, ' ').trim();
    const domain = String.raw`(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}`;
    const email = String.raw`[a-z0-9_+%-]+(?:\.[a-z0-9_+%-]+)*@${domain}`;
    const website = String.raw`(?:https?:\/\/)?${domain}(?::[0-9]+)?(?:[/?#][^\s<>"'()\[\]{}]*)?`;
    const extension = String.raw`(?:[ \t]*(?:ext\.?|extension|x|\#)[ \t]*[0-9]{1,6})?`;
    const northAmerican = String.raw`(?:\+?1[ .-]?)?(?:\([0-9]{3}\)[ .-]?|[0-9]{3}[ .-]?)[0-9]{3}[ .-]?[0-9]{4}`;
    const international = String.raw`\+[0-9](?:[ .-]?[0-9]){6,14}`;
    // A single pass keeps phone-like digits inside URLs from being converted twice.
    const tokens = new RegExp(String.raw`(?<![\w@.+/-])(?:${email}|${website}|(?:${northAmerican}|${international})${extension})(?![\w@/-])`, 'gi');

    function speakAddress(text) {
        const symbols = {
            '.': 'dot', '@': 'at', '/': 'slash', '-': 'dash', '_': 'underscore',
            '?': 'question mark', '=': 'equals', '&': 'ampersand', '#': 'hash',
            '%': 'percent', '+': 'plus', ':': 'colon', '~': 'tilde',
        };
        return text.replace(/^https?:\/\//i, '')
            .replace(/www(?=\.)/gi, 'double you double you double you')
            .replace(/[.@/\-_?=&#%+:~]/g, symbol => ` ${symbols[symbol]} `)
            .replace(/[0-9]+/g, number => ` ${spellDigits(number)} `)
            .replace(/ +/g, ' ').trim();
    }

    function speakPhone(text) {
        const parts = text.split(/[ \t]*(?:extension|ext\.?|x|#)[ \t]*/i);
        let phone = parts[0].replace(/^\+/, '');
        const numbers = phone.replace(/\D/g, '');
        // Normalize North American grouping even for numbers pasted without separators.
        if (/^[0-9]{10}$/.test(numbers) || /^1[0-9]{10}$/.test(numbers)) {
            phone = numbers.length === 11
                ? `${numbers[0]} ${numbers.slice(1, 4)} ${numbers.slice(4, 7)} ${numbers.slice(7)}`
                : `${numbers.slice(0, 3)} ${numbers.slice(3, 6)} ${numbers.slice(6)}`;
        }
        const spoken = phone.match(/[0-9]+/g).map(spellDigits).join(', ');
        return spoken + (parts[1] ? `, extension ${spellDigits(parts[1])}` : '');
    }

    function prepareVoiceScript(text, spellOtherNumbers = false) {
        let result = '';
        let last = 0;
        const plain = value => spellOtherNumbers
            ? value.replace(/[0-9]+/g, spellDigits) : value;
        for (const match of text.matchAll(tokens)) {
            result += plain(text.slice(last, match.index));
            // Sentence punctuation belongs to the script, not the address.
            const token = match[0].replace(/[.,!?:;]+$/, '');
            const trailing = match[0].slice(token.length);
            result += (/[a-z]/i.test(token.replace(/(?:extension|ext|x)/gi, '')) || token.includes('@')
                ? speakAddress(token) : speakPhone(token)) + trailing;
            last = match.index + match[0].length;
        }
        return result + plain(text.slice(last));
    }

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { prepareVoiceScript };
    }
    if (typeof document === 'undefined') return;

    document.addEventListener('DOMContentLoaded', function () {
        const form = document.getElementById('voice-prep-form');
        const input = document.getElementById('voice-input');
        const output = document.getElementById('voice-output');
        const copy = document.getElementById('voice-copy');
        const status = document.getElementById('voice-status');
        const numbers = document.getElementById('spell-numbers');

        function prepare() {
            output.value = prepareVoiceScript(input.value, numbers.checked);
            copy.disabled = !output.value.trim();
            status.textContent = output.value === input.value
                ? 'No matching phone numbers or addresses found. You can edit the prepared script.'
                : 'Script prepared. Review and edit it, then copy.';
        }
        form.addEventListener('submit', event => {
            event.preventDefault();
            prepare();
        });
        document.getElementById('voice-example').addEventListener('click', () => {
            input.value = 'Call (905) 555-0123 ext. 204, visit www.example.ca/contact, or email hello@example.ca.';
            prepare();
        });
        document.getElementById('voice-clear').addEventListener('click', () => {
            input.value = '';
            output.value = '';
            copy.disabled = true;
            status.textContent = '';
            input.focus();
        });
        function markStale() {
            status.textContent = output.value ? 'Source changed. Prepare the script again to update the result.' : '';
        }
        input.addEventListener('input', markStale);
        numbers.addEventListener('change', markStale);
        output.addEventListener('input', () => {
            copy.disabled = !output.value.trim();
            status.textContent = 'Prepared script edited.';
        });
        copy.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(output.value);
                status.textContent = 'Copied! Paste into your voice generator.';
            } catch (error) {
                output.focus();
                output.select();
                status.textContent = 'Automatic copy is unavailable. The script is selected; press Ctrl+C or Command+C to copy.';
            }
        });
    });
}());
