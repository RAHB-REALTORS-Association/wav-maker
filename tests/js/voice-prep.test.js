const { test } = require('node:test');
const assert = require('node:assert/strict');
const { prepareVoiceScript: prepare } = require('../../static/voice-prep.js');

const phone = 'nine zero five, five five five, zero one two three';
for (const source of ['(905) 555-0123', '905-555-0123', '905.555.0123', '905 555 0123', '9055550123']) {
    test(`North American phone: ${source}`, () => assert.equal(prepare(source), phone));
}
for (const marker of ['ext.', 'ext', 'extension', 'x', '#']) {
    test(`phone extension: ${marker}`, () => {
        assert.equal(prepare(`Call +1-905-555-0123 ${marker} 204.`),
            `Call one, ${phone}, extension two zero four.`);
    });
}
test('international phone preserves groups', () => {
    assert.equal(prepare('+44 20 7946 0958'), 'four four, two zero, seven nine four six, zero nine five eight');
});
test('websites in prose preserve sentence punctuation and line breaks', () => {
    assert.equal(prepare('Visit www.example.ca.\nOr (example.com/contact)!'),
        'Visit double you double you double you dot example dot ca.\nOr (example dot com slash contact)!');
});
test('URLs convert paths, queries, fragments, ports, and digits in one pass', () => {
    assert.equal(prepare('https://example.ca:8080/path-2?q=4&lang=en#top!'),
        'example dot ca colon eight zero eight zero slash path dash two question mark q equals four ampersand lang equals en hash top!');
    assert.equal(prepare('example.ca/9055550123'), 'example dot ca slash nine zero five five five five zero one two three');
});
test('email addresses include dots, underscores and plus tags', () => {
    assert.equal(prepare('Email first.last_name+info@example.ca.'),
        'Email first dot last underscore name plus info at example dot ca.');
});
test('ordinary prose, dates, prices and line breaks stay unchanged by default', () => {
    const source = 'Open at 9:30 on 2026-10-28. Tickets: $25.50.\nPress 2 for help.';
    assert.equal(prepare(source), source);
});
test('optional digit spelling keeps leading zeros', () => {
    assert.equal(prepare('Code 0042. Press 2.', true), 'Code zero zero four two. Press two.');
});
test('multiple tokens and extensions can share a script', () => {
    assert.equal(prepare('Call 9055550123 or email hello@example.ca.\nVisit example.ca.'),
        `Call ${phone} or email hello at example dot ca.\nVisit example dot ca.`);
});
test('does not convert a phone-shaped substring inside an identifier', () => {
    assert.equal(prepare('ID ABC9055550123XYZ /9055550123/'), 'ID ABC9055550123XYZ /9055550123/');
});
test('empty input and already prepared scripts are stable', () => {
    assert.equal(prepare(''), '');
    const result = prepare('Call 9055550123 or visit www.example.ca.');
    assert.equal(prepare(result), result);
});
